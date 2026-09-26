"""
core/orchestrator_v2.py — طبقة تنسيق الوكلاء (Agents Orchestration Layer)
تدمج أنماط OpenAI Agents SDK: handoffs + guardrails + tracing
مصممة لتعمل فوق control_plane.py دون تعديله.

المعمارية:
  Coordinator → Agent(s) → Tools → Guardrails → Trace
  - Handoffs: نقل المهمة بين الوكلاء
  - Guardrails: فحص قبل/بعد التنفيذ
  - Tracing: تسجيل كامل لكل خطوة
"""
from __future__ import annotations
import time
import uuid
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class AgentStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    HANDOFF = "handoff"
    DONE = "done"
    BLOCKED = "blocked"
    FAILED = "failed"


@dataclass
class TraceStep:
    step_id: str
    agent: str
    action: str
    input_summary: str
    output_summary: str
    duration_ms: float
    status: AgentStatus
    ts: float = field(default_factory=time.time)


@dataclass
class AgentResult:
    agent: str
    output: Any
    status: AgentStatus
    handoff_to: Optional[str] = None
    trace: List[TraceStep] = field(default_factory=list)


class Tracer:
    """تسجيل كامل لكل خطوة — بديل OpenTelemetry خفيف."""
    def __init__(self):
        self.steps: List[TraceStep] = []

    def log(self, agent: str, action: str, inp: Any, out: Any,
            dur_ms: float, status: AgentStatus):
        self.steps.append(TraceStep(
            step_id=uuid.uuid4().hex[:8],
            agent=agent, action=action,
            input_summary=str(inp)[:120],
            output_summary=str(out)[:120],
            duration_ms=dur_ms, status=status,
        ))

    def dump(self) -> List[Dict[str, Any]]:
        return [s.__dict__ for s in self.steps]


class Guardrail:
    """قاعدة فحص قبل أو بعد التنفيذ."""
    def __init__(self, name: str, check: Callable[[Any], bool],
                 phase: str = "pre", reason: str = ""):
        self.name = name
        self.check = check
        self.phase = phase  # "pre" | "post"
        self.reason = reason


class Agent:
    """وكيل واحد — يلف دالة + guardrails + أدوات."""
    def __init__(self, name: str, handler: Callable,
                 description: str = "",
                 guardrails: Optional[List[Guardrail]] = None,
                 handoffs: Optional[Dict[str, str]] = None):
        self.name = name
        self.handler = handler
        self.description = description
        self.guardrails = guardrails or []
        self.handoffs = handoffs or {}  # {"condition": "target_agent"}

    def run(self, task: Any, context: Optional[Dict] = None,
            tracer: Optional[Tracer] = None) -> AgentResult:
        tracer = tracer or Tracer()
        t0 = time.time()

        # pre-guardrails
        for g in self.guardrails:
            if g.phase == "pre":
                try:
                    if not g.check(task):
                        tracer.log(self.name, f"guardrail:{g.name}",
                                   task, "BLOCKED",
                                   (time.time()-t0)*1000, AgentStatus.BLOCKED)
                        return AgentResult(self.name, None,
                                           AgentStatus.BLOCKED,
                                           trace=tracer.steps)
                except Exception as e:
                    logger.warning(f"guardrail {g.name} failed: {e}")

        # تنفيذ
        try:
            output = self.handler(task, context or {})
            status = AgentStatus.DONE
        except Exception as e:
            output = {"error": str(e)}
            status = AgentStatus.FAILED

        # post-guardrails
        for g in self.guardrails:
            if g.phase == "post":
                try:
                    if not g.check(output):
                        status = AgentStatus.BLOCKED
                        output = {"blocked_by": g.name,
                                  "reason": g.reason or "post-guardrail"}
                        break
                except Exception:
                    pass

        dur = (time.time() - t0) * 1000
        tracer.log(self.name, "run", task, output, dur, status)

        return AgentResult(self.name, output, status, trace=tracer.steps)


class Orchestrator:
    """
    المنسق الأعلى — يستقبل مهمة، يختار الوكيل، يدير الـ handoffs.
    """
    def __init__(self):
        self.agents: Dict[str, Agent] = {}
        self.tracer = Tracer()
        self.max_handoffs = 5

    def register(self, agent: Agent) -> None:
        if agent.name in self.agents:
            raise ValueError(f"Agent exists: {agent.name}")
        self.agents[agent.name] = agent

    def dispatch(self, task: Any, start_agent: str,
                 context: Optional[Dict] = None) -> AgentResult:
        if start_agent not in self.agents:
            raise KeyError(f"Unknown agent: {start_agent}")

        ctx = context or {}
        current = self.agents[start_agent]
        result = current.run(task, ctx, self.tracer)
        handoffs = 0

        while result.status == AgentStatus.DONE and result.handoff_to \
                and handoffs < self.max_handoffs:
            nxt = result.handoff_to
            if nxt not in self.agents:
                break
            ctx["from_agent"] = current.name
            ctx["prev_output"] = result.output
            current = self.agents[nxt]
            result = current.run(task, ctx, self.tracer)
            result.handoff_to = None
            handoffs += 1

        return result

    def trace_dump(self) -> List[Dict[str, Any]]:
        return self.tracer.dump()


# ─── تسجيل تلقائي مع Constitution + StructuralSafety ──────────

def _load_guardrails():
    """يجرب يستورد الحماية السلوكية والهيكلية إن وُجدت."""
    guards = []
    try:
        from core.constitution import constitution_guard
        def const_check(task):
            r = constitution_guard.check_command(str(task))
            return r.get("allowed", True)
        guards.append(Guardrail("constitution", const_check, "pre",
                                "مخالفة الدستور"))
    except Exception:
        pass

    try:
        from core.structural_safety import HardConstraintLayer
        # placeholder: يفحص لاحقاً عند ربط النموذج
        def struct_check(_task):
            return True
        guards.append(Guardrail("structural", struct_check, "pre",
                                "قيد هيكلي"))
    except Exception:
        pass

    return guards


_default_orch: Optional[Orchestrator] = None


def get_orchestrator() -> Orchestrator:
    global _default_orch
    if _default_orch is None:
        _default_orch = Orchestrator()
        guards = _load_guardrails()
        # وكيل النظام الأساسي
        def _default_handler(task, ctx):
            return {"echo": task, "ctx": list(ctx.keys())}
        _default_orch.register(Agent(
            "default", _default_handler,
            "وكيل النظام الافتراضي", guardrails=guards))
    return _default_orch
