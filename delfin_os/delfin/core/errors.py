"""أخطاء النظام. أخطاء الأمان لا تُعاد محاولتها أبداً."""


class SecurityError(Exception):
    """انتهاك سياسة أمنية."""


class ResourceExhausted(Exception):
    """استُنفد حد الموارد أو المعدل."""


class BudgetExceeded(Exception):
    """تجاوزت الجلسة ميزانية التوكن."""
