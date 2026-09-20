"""
سياق المحادثة — ذاكرة قصيرة المدى
"""
import time
from collections import deque
from db import log_event


class ConversationContext:
    """
    سياق محادثة ذكي:
    - يحتفظ بآخر N أمر
    - يستخرج أنماط من السياق
    - يوفر اقتراحات بناءً على السياق
    """

    def __init__(self, max_history: int = 20):
        self.history = deque(maxlen=max_history)
        self.patterns = {}
        self.user_preferences = {}

        log_event("context", {"status": "initialized", "max_history": max_history})

    def add(self, user_input: str, parsed: dict, result: dict):
        """إضافة تفاعل للسياق"""
        entry = {
            "timestamp": time.time(),
            "input": user_input,
            "parsed": parsed,
            "result_summary": {
                "status": result.get("status"),
                "type": parsed.get("type") if isinstance(parsed, dict) else None
            }
        }

        self.history.append(entry)

        # تحديث الأنماط
        self._update_patterns(entry)

    def get_context(self, limit: int = 5) -> list:
        """الحصول على آخر N من السياق"""
        return list(self.history)[-limit:]

    def get_last_command_type(self) -> str:
        """نوع الأمر الأخير"""
        if self.history:
            last = self.history[-1]
            return last.get("parsed", {}).get("type", "unknown")
        return "unknown"

    def get_suggestion(self) -> str:
        """اقتراح بناءً على السياق"""
        if not self.history:
            return "ابدأ بأمر: اجمع، ولد، اصهر، حلل"

        last_type = self.get_last_command_type()

        suggestions = {
            "collect": "بعد الجمع: نظف، حلل، أو ولد",
            "clean": "بعد التنظيف: درّب، اصهر، أو انشر",
            "generate": "بعد التوليد: اختبر، نظف، أو اصهر",
            "merge": "بعد الصهر: انشر، اختبر، أو درّب",
            "train": "بعد التدريب: اصهر، اختبر، أو انشر",
            "unknown": "جرّب: اجمع من github، ولد كود python، اصهر النماذج"
        }

        return suggestions.get(last_type, suggestions["unknown"])

    def _update_patterns(self, entry: dict):
        """تحديث أنماط المستخدم"""
        cmd_type = entry.get("parsed", {}).get("type")

        if cmd_type:
            if cmd_type not in self.patterns:
                self.patterns[cmd_type] = 0
            self.patterns[cmd_type] += 1

    def get_user_profile(self) -> dict:
        """ملف تعريفي للمستخدم بناءً على السياق"""
        if not self.patterns:
            return {"type": "new_user"}

        most_used = max(self.patterns, key=self.patterns.get)

        profiles = {
            "collect": "جامع بيانات",
            "generate": "مولد أكواد",
            "merge": "صاهر نماذج",
            "train": "مدرب نماذج",
            "attack": "محلل أمني هجومي",
            "defend": "محلل أمني دفاعي"
        }

        return {
            "type": profiles.get(most_used, "مستخدم عام"),
            "most_used_command": most_used,
            "total_interactions": len(self.history),
            "patterns": self.patterns.copy()
        }

    def clear(self):
        """مسح السياق"""
        self.history.clear()
        self.patterns.clear()

    def export_context(self) -> dict:
        """تصدير السياق كاملاً"""
        return {
            "history": list(self.history),
            "patterns": self.patterns.copy(),
            "user_profile": self.get_user_profile()
        }


# نسخة عامة
context = ConversationContext()
