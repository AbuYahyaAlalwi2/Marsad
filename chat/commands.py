"""
نظام الأوامر المسجلة — أوامر معقدة من plugins
"""
import time
from db import log_event


class CommandRegistry:
    """
    سجل الأوامر المعقدة:
    - أوامر مخصصة من المستخدم
    - أوامر من plugins
    - أوامر مركبة (macro)
    """

    def __init__(self):
        self.commands = {}
        self.macros = {}

        # أوامر مدمجة
        self._register_builtin_commands()

        log_event("command_registry", {"status": "initialized"})

    def _register_builtin_commands(self):
        """أوامر مدمجة"""
        builtins = {
            "full_pipeline": {
                "description": "الخط الكامل: جمع → تنظيف → توليد → صهر",
                "steps": [
                    {"type": "collect", "params": {"limit": 100}},
                    {"type": "clean", "params": {}},
                    {"type": "generate", "params": {"variations": 5}},
                    {"type": "merge", "params": {}}
                ]
            },
            "security_scan": {
                "description": "فحص أمني شامل",
                "steps": [
                    {"type": "collect", "params": {"platform": "github", "query": "security"}},
                    {"type": "analyze", "params": {"depth": "deep"}},
                    {"type": "attack", "params": {"simulate": True}},
                    {"type": "defend", "params": {"generate_patches": True}}
                ]
            },
            "code_enhance": {
                "description": "تحسين كود: جمع → توليد → إصلاح",
                "steps": [
                    {"type": "collect", "params": {"platform": "github"}},
                    {"type": "generate", "params": {"type": "improvements"}},
                    {"type": "execute", "params": {"action": "apply_fixes"}}
                ]
            },
            "model_build": {
                "description": "بناء نموذج: جمع → تدريب → صهر → نشر",
                "steps": [
                    {"type": "collect", "params": {"limit": 1000}},
                    {"type": "train", "params": {"epochs": 3}},
                    {"type": "merge", "params": {"models": "all"}},
                    {"type": "deploy", "params": {"target": "huggingface"}}
                ]
            }
        }

        for name, config in builtins.items():
            self.register(name, config)

    def register(self, name: str, config: dict):
        """تسجيل أمر جديد"""
        self.commands[name] = {
            **config,
            "registered_at": time.time(),
            "usage_count": 0
        }

        log_event("command_registry", {
            "registered": name,
            "type": "macro" if "steps" in config else "single"
        })

    def execute(self, name: str, params: dict = None) -> dict:
        """تنفيذ أمر مسجل"""
        if name not in self.commands:
            return {"status": "error", "reason": f"أمر غير مسجل: {name}"}

        cmd = self.commands[name]
        cmd["usage_count"] += 1

        # إذا كان macro (متعدد الخطوات)
        if "steps" in cmd:
            return self._execute_macro(name, cmd["steps"], params)

        # أمر بسيط
        return {
            "status": "success",
            "command": name,
            "result": f"Executed {name}"
        }

    def _execute_macro(self, name: str, steps: list, override_params: dict = None) -> dict:
        """تنفيذ macro متعدد الخطوات"""
        results = []

        for i, step in enumerate(steps):
            step_params = step.get("params", {})
            if override_params:
                step_params.update(override_params)

            step_result = {
                "step": i + 1,
                "type": step["type"],
                "params": step_params,
                "status": "simulated",
                "output": f"Step {i+1}: {step['type']} completed"
            }

            results.append(step_result)

        return {
            "status": "success",
            "macro": name,
            "steps_completed": len(results),
            "results": results
        }

    def list_commands(self) -> dict:
        """قائمة الأوامر المسجلة"""
        return {
            name: {
                "description": cmd.get("description", ""),
                "type": "macro" if "steps" in cmd else "single",
                "usage_count": cmd.get("usage_count", 0),
                "steps_count": len(cmd.get("steps", []))
            }
            for name, cmd in self.commands.items()
        }

    def get_command(self, name: str) -> dict:
        """الحصول على أمر محدد"""
        return self.commands.get(name)

    def create_macro(self, name: str, steps: list, description: str = ""):
        """إنشاء macro جديد من المستخدم"""
        self.register(name, {
            "description": description,
            "steps": steps,
            "created_by": "user"
        })

    def get_popular_commands(self, limit: int = 5) -> list:
        """الأوامر الأكثر استخداماً"""
        sorted_cmds = sorted(
            self.commands.items(),
            key=lambda x: x[1].get("usage_count", 0),
            reverse=True
        )

        return [
            {"name": name, "usage_count": cmd.get("usage_count", 0)}
            for name, cmd in sorted_cmds[:limit]
        ]


# نسخة عامة
command_registry = CommandRegistry()
