"""
جسر الدستور — يربط الدستور بكل مكونات النظام.
"""
import logging
from functools import wraps
from core.constitution import constitution_guard

logger = logging.getLogger(__name__)


def guarded(func):
    """مزخرف يحمي أي دالة بقواعد الدستور."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        # استخرج الأمر من الوسائط
        command = ""
        for arg in args:
            if isinstance(arg, str):
                command = arg
                break
        if not command and kwargs:
            for v in kwargs.values():
                if isinstance(v, str):
                    command = v
                    break

        # افحص
        result = constitution_guard.check_command(command)
        if not result["allowed"]:
            logger.warning(f"الدستور منع أمراً: {command[:50]} — {result.get('article')}")
            return {
                "status": "blocked",
                "reason": result.get("reason"),
                "article": result.get("article"),
                "message": "الأمر مخالف للدستور",
            }

        return func(*args, **kwargs)
    return wrapper


def check_or_raise(command: str) -> bool:
    """افحص أمراً — يرمي استثناء إذا رُفض."""
    result = constitution_guard.check_command(command)
    if not result["allowed"]:
        raise PermissionError(
            f"الدستور رفض الأمر: {result.get('article', 'مادة غير محددة')}"
        )
    return True


def get_guard_stats() -> dict:
    """إحصائيات الحارس."""
    return constitution_guard.stats()
