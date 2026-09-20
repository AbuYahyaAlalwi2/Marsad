"""Command registry with no simulated execution.

Macros are definitions only until a real handler is registered. The registry
never reports a step as completed merely because it was listed.
"""
import time
from db import log_event


class CommandRegistry:
    def __init__(self):
        self.commands = {}
        self.macros = {}
        self._register_builtin_commands()
        log_event("command_registry", {"status": "initialized"})

    def _register_builtin_commands(self):
        for name, description in {
            "full_pipeline": "جمع وتنظيف وتجهيز البيانات",
            "security_scan": "تحليل دفاعي لمصادر مصرح بها",
            "code_enhance": "تحسين كود يقدمه المشغل",
            "model_build": "تجهيز Dataset ورفعها بعد التحقق",
        }.items():
            self.register(name, {"description": description, "handler": None})

    def register(self, name: str, config: dict):
        self.commands[name] = {**config, "registered_at": time.time(), "usage_count": 0}
        log_event("command_registry", {"registered": name, "type": "single"})

    def execute(self, name: str, params: dict = None) -> dict:
        command = self.commands.get(name)
        if not command:
            return {"status": "error", "reason": f"أمر غير مسجل: {name}"}
        command["usage_count"] += 1
        handler = command.get("handler")
        if not callable(handler):
            return {"status": "not_configured", "command": name, "reason": "لا يوجد منفذ حقيقي مرتبط بهذا الأمر"}
        try:
            result = handler(params or {})
            return result if isinstance(result, dict) else {"status": "completed", "result": result}
        except Exception as exc:
            log_event("command_registry_error", {"command": name, "error": str(exc)})
            return {"status": "error", "command": name, "error": str(exc)}

    def list_commands(self) -> dict:
        return {
            name: {
                "description": cmd.get("description", ""),
                "type": "single",
                "usage_count": cmd.get("usage_count", 0),
                "configured": callable(cmd.get("handler")),
            }
            for name, cmd in self.commands.items()
        }

    def get_command(self, name: str):
        return self.commands.get(name)

    def create_macro(self, name: str, steps: list, description: str = ""):
        self.register(name, {"description": description, "steps": steps, "handler": None})

    def get_popular_commands(self, limit: int = 5):
        return sorted(
            ({"name": n, "usage_count": c.get("usage_count", 0)} for n, c in self.commands.items()),
            key=lambda x: x["usage_count"], reverse=True
        )[:limit]


command_registry = CommandRegistry()
