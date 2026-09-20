"""
واجهة الشات المحسّنة — مرنة 100%
"""
import time
from core.brain import brain
from core.executor import executor
from plugins.hooks import hooks
from chat.advanced_parser import advanced_parser
from chat.context import context
from chat.commands import command_registry
from db import log_event


class ChatInterface:
    """
    واجهة شات مرنة:
    - لا ترفض أي أمر
    - تدعم أوامر معقدة متعددة
    - تدعم معاملات مسماة
    - تدعم اختصارات customizable
    - تحتفظ بسياق المحادثة
    - تدعم أوامر macro مسجلة
    """

    def __init__(self):
        self.history = []
        self.command_count = 0
        self.parser = advanced_parser
        self.context = context
        self.registry = command_registry

        log_event("chat", {"status": "initialized_advanced"})

    def handle(self, user_input: str) -> dict:
        """معالجة إدخال المستخدم — النقطة الرئيسية"""
        self.command_count += 1

        # 1. تخزين في التاريخ
        self.history.append({
            "input": user_input,
            "timestamp": time.time()
        })

        # 2. تفعيل خطاف pre_execute
        data = {"input": user_input, "timestamp": time.time()}
        data = hooks.trigger("pre_execute", data)

        if data is None:
            return {"status": "stopped_by_hook"}

        # 3. التحليل المتقدم
        parsed = self.parser.parse(user_input, context=self.context.get_context())

        # 4. التنفيذ حسب النوع
        if parsed["is_complex"]:
            result = self._execute_complex(parsed)
        else:
            result = self._execute_single(parsed["commands"][0])

        # 5. تحديث السياق
        self.context.add(user_input, parsed, result)

        # 6. تفعيل خطاف post_execute
        response = {
            "status": "success",
            "input": user_input,
            "parsed": parsed,
            "result": result,
            "suggestion": self.context.get_suggestion(),
            "command_number": self.command_count,
            "timestamp": time.time()
        }

        response = hooks.trigger("post_execute", response)

        # 7. تخزين في التاريخ
        self.history.append({
            "output": response,
            "timestamp": time.time()
        })

        if len(self.history) > 1000:
            self.history = self.history[-1000:]

        return response

    def _execute_single(self, command: dict) -> dict:
        """تنفيذ أمر واحد"""
        cmd_type = command["type"]
        params = command.get("params", {})

        # التحقق من الأوامر المسجلة أولاً
        if cmd_type in self.registry.commands:
            return self.registry.execute(cmd_type, params)

        # التنفيذ العادي
        thought = brain.think(command["raw"])
        result = executor.execute(command["raw"], thought)

        return {
            "type": cmd_type,
            "thought": thought,
            "execution": result
        }

    def _execute_complex(self, parsed: dict) -> dict:
        """تنفيذ أوامر متعددة"""
        results = []

        for i, cmd in enumerate(parsed["commands"]):
            step_result = self._execute_single(cmd)
            results.append({
                "step": i + 1,
                "command": cmd["raw"],
                "result": step_result
            })

        return {
            "type": "complex",
            "steps": len(results),
            "results": results,
            "all_success": all(r["result"].get("status") == "success" for r in results)
        }

    # ─── وظائف إضافية ───

    def register_custom_command(self, name: str, steps: list, description: str = ""):
        """تسجيل أمر مخصص من المستخدم"""
        self.registry.create_macro(name, steps, description)

        return {
            "status": "success",
            "registered": name,
            "steps": len(steps)
        }

    def add_custom_alias(self, alias: str, command_type: str):
        """إضافة اختصار مخصص"""
        self.parser.add_alias(alias, command_type)

        return {
            "status": "success",
            "alias": alias,
            "maps_to": command_type
        }

    def get_suggestion(self) -> str:
        """اقتراح بناءً على السياق"""
        return self.context.get_suggestion()

    def get_user_profile(self) -> dict:
        """ملف المستخدم"""
        return self.context.get_user_profile()

    def export_session(self) -> dict:
        """تصدير الجلسة كاملة"""
        return {
            "history": self.history,
            "context": self.context.export_context(),
            "commands_used": self.registry.list_commands(),
            "stats": self.get_stats()
        }

    def get_history(self, limit: int = 10) -> list:
        """الحصول على التاريخ"""
        return self.history[-limit:]

    def get_stats(self) -> dict:
        """إحصائيات الشات"""
        return {
            "total_commands": self.command_count,
            "history_size": len(self.history),
            "registered_commands": len(self.registry.commands),
            "aliases": len(self.parser.aliases),
            "refusals": 0,
            "user_profile": self.context.get_user_profile()
        }


# نسخة عامة
chat = ChatInterface()
