"""محرك القواعد: من ينفّذ ماذا، متى نوقف، متى نعيد، متى نرفض."""
import json
from pathlib import Path

DEFAULT_RULES = {
    "routing": {"chat": "assistant", "plan": "planner", "code": "coder", "files": "filemanager",
                "memory": "memory", "browse": "browser", "review": "security", "github": "github"},
    "timeouts": {"default": 60, "code": 45, "browse": 40, "plan": 90, "chat": 120},
    "retry": {"default": {"max": 1, "base": 0.5}, "code": {"max": 0, "base": 0.0},
              "github": {"max": 0, "base": 0.0}, "browse": {"max": 1, "base": 1.0}},
    "priority": {"chat": 2, "plan": 3, "code": 4, "files": 3, "memory": 2,
                 "browse": 5, "review": 1, "github": 4},
    "max_steps": 8,
    "max_payload_chars": 20000,
}


def _merge(base, extra):
    for k, v in extra.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _merge(base[k], v)
        else:
            base[k] = v
    return base


class RulesEngine:
    def __init__(self, rules=None, path=None):
        r = json.loads(json.dumps(DEFAULT_RULES))
        if path and Path(path).exists():
            _merge(r, json.loads(Path(path).read_text("utf-8")))
        if rules:
            _merge(r, rules)
        self.r = r

    @property
    def max_steps(self):
        return int(self.r["max_steps"])

    def kinds(self):
        return set(self.r["routing"])

    def route(self, kind):
        return self.r["routing"].get(kind)

    def timeout(self, kind):
        t = self.r["timeouts"]
        return float(t.get(kind, t["default"]))

    def retry(self, kind):
        t = self.r["retry"]
        return t.get(kind, t["default"])

    def priority(self, kind):
        return int(self.r["priority"].get(kind, 5))

    def reject_reason(self, kind, payload):
        if kind not in self.r["routing"]:
            return "نوع مهمة غير معروف"
        if not isinstance(payload, dict):
            return "الحمولة يجب أن تكون كائناً"
        if len(json.dumps(payload, ensure_ascii=False, default=str)) > int(self.r["max_payload_chars"]):
            return "الحمولة أكبر من الحد المسموح"
        return None
