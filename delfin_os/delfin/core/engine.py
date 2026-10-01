"""المحرك (الطبقة 1): خط المعالجة. كل إجراء يمر هنا فقط، وتمرّ كل مهمة ببوابة السلامة قبل الوكيل."""
import asyncio

from ..safety.layers import Action
from .errors import BudgetExceeded, ResourceExhausted, SecurityError
from .recovery import CircuitBreaker, retry_async

NO_PIPELINE_STEP_KINDS = {"github"}      # لا يُنفَّذ ضمن خطة يولّدها النموذج أبداً


class CoreEngine:
    def __init__(self, state, bus, rules, plugins, resources, safety, validator):
        self.state, self.bus, self.rules = state, bus, rules
        self.plugins, self.resources, self.safety, self.validator = plugins, resources, safety, validator
        self._breakers = {}

    def _breaker(self, name):
        return self._breakers.setdefault(name, CircuitBreaker())

    def classify(self, kind, payload):
        if kind == "plan":
            return "agentic"
        return "multi-step" if isinstance(payload, dict) and isinstance(payload.get("steps"), list) else "simple"

    async def _finish(self, tid, status, kind, owner, result=None, error=None):
        self.state.update_task(tid, status, result=result, error=error)
        await self.bus.publish(f"task.{status}", {"task": tid, "kind": kind, "owner": owner})
        return {"task_id": tid, "status": status, "result": result, "error": error}

    async def execute(self, kind, payload, owner, priority=None):
        tid = self.state.create_task(kind, owner, payload)
        priority = self.rules.priority(kind) if priority is None else priority
        reason = self.rules.reject_reason(kind, payload)
        if reason:
            return await self._finish(tid, "rejected", kind, owner, error=reason)
        # التحقق من النص المُدخل (يُستخرج من الحمولة)
        text = " ".join(str(v) for v in payload.values() if isinstance(v, str))[:8000]
        suspicious = ()
        if text.strip():
            ok, sus = self.validator.check(text)
            if not ok:
                return await self._finish(tid, "rejected", kind, owner, error="مدخل مرفوض: " + "، ".join(sus))
            suspicious = tuple(sus)
        verdict = await asyncio.to_thread(self.safety.review, Action(kind, payload, owner, suspicious))
        if not verdict.allowed:
            return await self._finish(tid, "rejected", kind, owner, error=f"{verdict.layer}: {verdict.reason}")
        name = self.rules.route(kind)
        try:
            agent = self.plugins.get(name)
        except KeyError:
            return await self._finish(tid, "rejected", kind, owner, error="الوكيل غير محمّل")
        br = self._breaker(name)
        if not br.allow():
            return await self._finish(tid, "failed", kind, owner, error="الدائرة مفتوحة مؤقتاً")
        try:
            self.resources.check(name, priority)
        except ResourceExhausted as e:
            return await self._finish(tid, "rejected", kind, owner, error=str(e))
        self.state.update_task(tid, "running")
        self.state.upsert_agent(name, "busy", getattr(agent, "version", ""))
        await self.bus.publish("task.started", {"task": tid, "kind": kind, "owner": owner})
        rp, ctx = self.rules.retry(kind), {"task_id": tid, "owner": owner, "kind": kind}
        try:
            result = await asyncio.wait_for(
                retry_async(lambda: agent.handle(kind, payload, ctx), rp["max"], rp["base"]),
                self.rules.timeout(kind))
            if isinstance(result, dict) and "_tokens_used" in result:
                self.resources.add_tokens(result.pop("_tokens_used"))
            br.record(True)
            return await self._finish(tid, "done", kind, owner, result=result)
        except asyncio.TimeoutError:
            br.record(False)
            return await self._finish(tid, "timeout", kind, owner, error="انتهت المهلة")
        except (SecurityError, BudgetExceeded) as e:
            self.safety.audit.append(owner, f"agent_denied:{kind}", str(e))
            if self.safety.behavior.record_denial(owner):
                self.safety.escalator.escalate("high", f"المالك {owner} أُقفل بسبب مخالفات متكررة")
            return await self._finish(tid, "rejected", kind, owner, error=str(e))
        except Exception as e:
            br.record(False)
            return await self._finish(tid, "failed", kind, owner, error=f"{type(e).__name__}: {str(e)[:200]}")
        finally:
            self.state.upsert_agent(name, "idle", getattr(agent, "version", ""))

    async def run_steps(self, steps, owner):
        if len(steps) > self.rules.max_steps:
            raise SecurityError("عدد الخطوات أكبر من المسموح")
        results, prev = [], None
        for s in steps:
            kind = s.get("kind")
            if kind in NO_PIPELINE_STEP_KINDS or kind not in self.rules.kinds():
                results.append({"status": "rejected", "error": "نوع خطوة غير مسموح في الخطط"})
                break
            payload = dict(s.get("payload", {}))
            if prev is not None:
                payload["prev"] = str(prev.get("result"))[:2000]
            r = await self.execute(kind, payload, owner)
            results.append(r)
            if r["status"] != "done":
                break
            prev = r
        return results
