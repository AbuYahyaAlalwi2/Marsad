"""
نظام الحماية الهيكلية — 11 طبقة
"""
import json, threading, time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import torch
import torch.nn as nn


class KnowledgeRepository(nn.Module):
    def __init__(self, config):
        super().__init__()
        self.encoder = nn.Linear(config.input_size, config.hidden_size)
    def forward(self, x):
        return self.encoder(x)


class ReasoningEngine(nn.Module):
    def __init__(self, config):
        super().__init__()
        self.layers = nn.Sequential(
            nn.Linear(config.hidden_size, config.hidden_size),
            nn.GELU(),
            nn.Linear(config.hidden_size, config.hidden_size))
    def forward(self, x):
        return self.layers(x)


class HardConstraintLayer(nn.Module):
    def __init__(self, rules, encode_rule_fn, threshold=0.85, level="kernel"):
        super().__init__()
        self.level = level
        self.threshold = threshold
        embeddings = [encode_rule_fn(r) for r in rules]
        matrix = torch.stack(embeddings) if embeddings else torch.zeros(1, 1)
        self.register_buffer("constraint_matrix", matrix)
        self.constraint_matrix.requires_grad = False
    def violates(self, output):
        sim = torch.cosine_similarity(output.unsqueeze(0), self.constraint_matrix, dim=-1)
        return (sim > self.threshold).any()


@dataclass
class IntentResult:
    safe: bool
    level: torch.Tensor


class InternalIntentMonitor(nn.Module):
    def __init__(self, config):
        super().__init__()
        self.intent_classifier = nn.Linear(config.hidden_size, 3)
    def forward(self, hidden_states):
        logits = self.intent_classifier(hidden_states.mean(dim=1))
        cls = logits.argmax(dim=-1)
        return IntentResult(safe=bool((cls == 0).all()), level=cls)


class SafetyAwareDataset(torch.utils.data.Dataset):
    def __init__(self, data_path, safety_labels, constraint_rules):
        self.data = json.loads(Path(data_path).read_text())
        self.labels = json.loads(Path(safety_labels).read_text())
        self.rules = json.loads(Path(constraint_rules).read_text())
    def __len__(self):
        return len(self.data)
    def __getitem__(self, idx):
        return {"input": self.data[idx], "label": self.labels[idx]}


def safety_aware_loss(output, target, constraint_layer, intent_monitor,
                      w_constraint=0.3, w_intent=0.2):
    task_loss = nn.functional.cross_entropy(output, target)
    penalty = constraint_layer.violates(output).float() * 1.0
    intent_res = intent_monitor(output.unsqueeze(1))
    intent_loss = 0.0 if intent_res.safe else 1.0
    return task_loss + w_constraint * penalty + w_intent * intent_loss


def freeze_constraint_grad(model):
    if model.hard_constraint.constraint_matrix.grad is not None:
        model.hard_constraint.constraint_matrix.grad = None


class AtomicConstraintUpdater:
    def __init__(self, model, encode_rule_fn):
        self.model = model
        self.encode_rule_fn = encode_rule_fn
        self.lock = threading.Lock()
    def update_constraints(self, new_rules):
        new_layer = HardConstraintLayer(new_rules, self.encode_rule_fn)
        with self.lock:
            old = self.model.hard_constraint
            self.model.hard_constraint = new_layer
            del old
        return True


@dataclass
class AuditResult:
    approved: bool
    reason: str = ""


class DualAuditorSystem:
    def __init__(self, auditor_1, auditor_2):
        self.auditor_1 = auditor_1
        self.auditor_2 = auditor_2
    def audit(self, output, context):
        s1 = self.auditor_1.evaluate(output, context)
        s2 = self.auditor_2.evaluate(output, context)
        if s1.safe and s2.safe:
            return AuditResult(approved=True)
        return AuditResult(approved=False, reason="فشل التحقق المزدوج")


class AdaptiveConstraintLayer(HardConstraintLayer):
    def __init__(self, rules, encode_rule_fn, context_encoder, core_rule_ids):
        super().__init__(rules, encode_rule_fn)
        self.context_encoder = context_encoder
        self.core_rule_ids = core_rule_ids
    def violates(self, output, context=None):
        if super().violates(output):
            return True
        if context is not None:
            ctx = self.context_encoder(context)
            sim = torch.cosine_similarity(output.unsqueeze(0), ctx.unsqueeze(0))
            return bool((sim > self.threshold).any())
        return False


class MemoryPatternScanner:
    def __init__(self, baseline_stats=None, z_threshold=6.0):
        self.baseline_stats = baseline_stats or {}
        self.z_threshold = z_threshold
    def scan(self, model):
        suspicious = []
        for name, param in model.named_parameters():
            mean, std = param.data.mean().item(), param.data.std().item() + 1e-8
            base = self.baseline_stats.get(name)
            if base and abs(mean - base["mean"]) / (base["std"] + 1e-8) > self.z_threshold:
                suspicious.append(name)
        return suspicious


class AuditLogger:
    def __init__(self, log_path, escalation_threshold=3, window_seconds=600):
        self.log_path = Path(log_path)
        self.escalation_threshold = escalation_threshold
        self.window_seconds = window_seconds
        self._recent = []
    def log(self, reason, context=""):
        entry = {"ts": time.time(), "reason": reason, "context": context[:300]}
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self._recent = [e for e in self._recent if time.time() - e["ts"] < self.window_seconds]
        self._recent.append(entry)
        if len(self._recent) >= self.escalation_threshold:
            self.escalate(reason)
    def escalate(self, reason):
        print(f"[ESCALATION] تكرار فشل التحقق: {reason}")


class StructuralSafetyModel(nn.Module):
    def __init__(self, config, rules, encode_rule_fn, auditor_1, auditor_2,
                 log_path="safety_audit.jsonl"):
        super().__init__()
        self.knowledge_repo = KnowledgeRepository(config)
        self.reasoning_engine = ReasoningEngine(config)
        self.hard_constraint = HardConstraintLayer(rules, encode_rule_fn)
        self.intent_monitor = InternalIntentMonitor(config)
        self.dual_auditor = DualAuditorSystem(auditor_1, auditor_2)
        self.memory_scanner = MemoryPatternScanner()
        self.audit_logger = AuditLogger(log_path)
        self.updater = AtomicConstraintUpdater(self, encode_rule_fn)
    def safe_fallback(self):
        return torch.zeros(1)
    def forward(self, x, context=None):
        knowledge = self.knowledge_repo(x)
        intent_check = self.intent_monitor(knowledge)
        if not intent_check.safe:
            self.audit_logger.log("intent_monitor_blocked")
            return self.safe_fallback()
        output = self.reasoning_engine(knowledge)
        if self.hard_constraint.violates(output):
            self.audit_logger.log("hard_constraint_violated")
            return self.safe_fallback()
        audit = self.dual_auditor.audit(output, context)
        if not audit.approved:
            self.audit_logger.log(audit.reason)
            return self.safe_fallback()
        return output
