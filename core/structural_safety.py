"""
marsad_structural_safety.py
نظام الحماية الهيكلية — يمنع النموذج من التخفي/الخروج/التعديل الذاتي.
الفرق عن constitution.py:
  constitution.py = حماية سلوكية (فوق النموذج)
  structural_safety.py = حماية هيكلية (في النواة)
"""
from __future__ import annotations
import json, threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import torch
import torch.nn as nn
import torch.nn.functional as F


@dataclass
class IntentResult:
    safe: bool
    level: torch.Tensor


@dataclass
class AuditResult:
    approved: bool
    reason: str = ""


@dataclass
class WeightScanResult:
    suspicious: bool
    mean: float
    std: float


class KnowledgeRepository(nn.Module):
    def __init__(self, config):
        super().__init__()
        self.register_buffer("knowledge_embeddings",
            torch.zeros(config.get("knowledge_size", 10000), config.hidden_size))

    def retrieve(self, q):
        q = F.normalize(q, dim=-1)
        k = F.normalize(self.knowledge_embeddings, dim=-1)
        return q @ k.T


class ReasoningEngine(nn.Module):
    def __init__(self, config):
        super().__init__()
        self.proj = nn.Linear(config.hidden_size, config.hidden_size)
        self.act = nn.GELU()
        self.dropout = nn.Dropout(config.get("dropout", 0.1))

    def forward(self, x):
        return self.dropout(self.act(self.proj(x)))


class HardConstraintLayer(nn.Module):
    """جدار صارم — لا يتدرب، لا يُخترق بالـ backprop."""
    def __init__(self, rules, level="kernel"):
        super().__init__()
        self.level = level
        self.rules = rules
        self.register_buffer("constraint_matrix",
            self._build(rules))

    def _build(self, rules):
        d = len(rules)
        if d == 0:
            return torch.zeros(1, 1)
        m = torch.eye(d)
        for i, r in enumerate(rules):
            m[i, i] = float(r.get("weight", 1.0))
        return m

    def compute_penalty(self, output):
        proj = output @ self.constraint_matrix.T
        return F.relu(-proj).mean()

    def violates(self, output):
        with torch.no_grad():
            return bool((output @ self.constraint_matrix.T < 0).any())


class InternalIntentMonitor(nn.Module):
    """يراقب النية قبل المخرج — يكشف التخفي من المنبع."""
    def __init__(self, config):
        super().__init__()
        self.intent_classifier = nn.Linear(config.hidden_size, 3)
        self.register_buffer("class_weights",
            torch.tensor([1.0, 2.0, 4.0]))

    def forward(self, h):
        logits = self.intent_classifier(h.mean(dim=1))
        cls = logits.argmax(dim=-1)
        return IntentResult(safe=bool((cls == 0).all()), level=cls)

    def compute_loss(self, output):
        logits = self.intent_classifier(output.mean(dim=1))
        p = F.softmax(logits, dim=-1)
        return (p[:, 1] * self.class_weights[1]
                + p[:, 2] * self.class_weights[2]).mean()


class StructuralSafetyModel(nn.Module):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.knowledge_repo = KnowledgeRepository(config)
        self.reasoning_engine = ReasoningEngine(config)
        self.hard_constraint = HardConstraintLayer(
            rules=config.get("rules", []), level="kernel")
        self.intent_monitor = InternalIntentMonitor(config)

    def forward(self, x):
        with torch.no_grad():
            self.knowledge_repo.retrieve(x)
        reasoned = self.reasoning_engine(x)
        intent = self.intent_monitor(reasoned)
        return reasoned, intent


def safety_aware_loss(output, target, constraint_layer, intent_monitor,
                     task_w=1.0, constraint_w=0.3, intent_w=0.2):
    task = F.cross_entropy(output, target)
    c = constraint_layer.compute_penalty(output)
    i = intent_monitor.compute_loss(output)
    total = task_w * task + constraint_w * c + intent_w * i
    return total, {"task": task.item(), "constraint": c.item(),
                   "intent": i.item(), "total": total.item()}


class AtomicConstraintUpdater:
    """تحديث القيود بدون توقف — بناء في الظل ثم تبديل ذري."""
    def __init__(self, model):
        self.model = model
        self.lock = threading.Lock()

    def update_constraints(self, new_rules):
        try:
            dev = next(self.model.parameters()).device
            new_layer = HardConstraintLayer(new_rules, "kernel").to(dev)
            with self.lock:
                old = self.model.hard_constraint
                self.model.hard_constraint = new_layer
                del old
            print("تم تحديث القيود الأمنية (بدون توقف)")
            return True
        except Exception as e:
            print(f"فشل تحديث القيود: {e}")
            return False


class AuditorModel:
    def __init__(self, path):
        self.path = path
        self.model = torch.jit.load(path) if Path(path).exists() else None

    def evaluate(self, output, context):
        if self.model is None:
            return IntentResult(safe=True, level=torch.tensor([0]))
        with torch.no_grad():
            logits = self.model(output)
            cls = logits.argmax(dim=-1)
            return IntentResult(safe=bool((cls == 0).all()), level=cls)

    def scan_weight(self, param):
        with torch.no_grad():
            m, s = param.mean().item(), param.std().item()
            return WeightScanResult(suspicious=(abs(m) > 1.0 or s > 5.0),
                                    mean=m, std=s)


class DualAuditorSystem:
    """نموذجان مستقلان — لازم يوافقوا معاً."""
    def __init__(self, p1="auditor_model_1.pt", p2="auditor_model_2.pt"):
        self.auditor_1 = AuditorModel(p1)
        self.auditor_2 = AuditorModel(p2)
        self.log = []

    def audit(self, output, context):
        s1 = self.auditor_1.evaluate(output, context)
        s2 = self.auditor_2.evaluate(output, context)
        if s1.safe and s2.safe:
            return AuditResult(approved=True)
        self.log.append({"s1": s1.level.tolist(), "s2": s2.level.tolist()})
        return AuditResult(approved=False, reason="فشل التحقق المزدوج")

    def memory_scan(self, model):
        susp = []
        for name, p in model.named_parameters():
            if self.auditor_1.scan_weight(p).suspicious:
                susp.append((name, p))
        return susp


class ContextEncoder(nn.Module):
    def __init__(self, config):
        super().__init__()
        self.encoder = nn.Linear(config.get("context_dim", 128),
                                 config.hidden_size)

    def forward(self, x):
        return self.encoder(x)


class AdaptiveConstraintLayer(HardConstraintLayer):
    """قيود جوهرية (لا استثناء) + قيود سياقية (تتكيف)."""
    def __init__(self, rules, config):
        super().__init__(rules, "kernel")
        self.context_encoder = ContextEncoder(config)
        self.core_constraints = [r for r in rules if r.get("tier") == "core"]
        self.contextual_constraints = [r for r in rules if r.get("tier") != "core"]

    def violates(self, output, context=None):
        if self._violates_core(output):
            return True
        if context is not None:
            ctx = self.context_encoder(context)
            if self._violates_contextual(output, ctx):
                return True
        return False

    def _violates_core(self, output):
        if not self.core_constraints:
            return False
        with torch.no_grad():
            return bool((output < 0).any())

    def _violates_contextual(self, output, ctx):
        if not self.contextual_constraints:
            return False
        with torch.no_grad():
            return bool(((output + ctx) < -0.5).any())
