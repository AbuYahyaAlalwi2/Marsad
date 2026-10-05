"""
Output Guard — صفر كود في المحادثة مع المستخدم
=================================================
يُطبّق 3 قواعد:
1. مستخدم مجاني: تقرير نصي فقط + تعليمات — لا تعديل
2. مشترك: الإصلاح يُطبَّق تلقائياً — لا كود يُرسَل للمستخدم
3. أي مستخدم: لا كود في أي رد مهما كان السبب

نموذج العمل:
  user_request → [OutputGuard] → filtered_response
                                      ↓
                               report only (free)
                               silent fix (subscriber)

لا يحتاج تعديل النموذج — غلاف يعمل على الـ output.
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "core"))
from knowledge_store import get_store


# ─── مستويات الوصول ──────────────────────────────────────────────────────────

class UserTier(Enum):
    FREE       = "free"        # تقرير + تعليمات فقط
    SUBSCRIBER = "subscriber"  # إصلاح صامت بدون كود


# ─── نتيجة الفلترة ───────────────────────────────────────────────────────────

@dataclass
class GuardedResponse:
    tier:         UserTier
    report:       str          # النص الآمن للمستخدم
    fix_applied:  bool         # هل طُبِّق الإصلاح؟
    fix_summary:  str          # ملخص ما تم (للمشترك)
    code_removed: bool         # هل أُزيل كود من الرد؟


# ─── أنماط الكود التي تُحذف ──────────────────────────────────────────────────

_CODE_PATTERNS = [
    r'```[\s\S]*?```',                   # code blocks
    r'`[^`\n]{3,}`',                     # inline code
    r'(?m)^(\s{4}|\t).*$',              # indented code
    r'(?i)\b(def |class |import |from |SELECT |INSERT |UPDATE |DELETE |<script|eval\(|exec\()',
]

_COMPILED = [re.compile(p) for p in _CODE_PATTERNS]


def _strip_code(text: str) -> tuple[str, bool]:
    """يحذف كل الكود من النص — يعيد (نص_نظيف, هل_تم_الحذف)"""
    modified = False
    for pattern in _COMPILED:
        cleaned = pattern.sub("[تم إخفاء الكود لأسباب أمنية]", text)
        if cleaned != text:
            modified = True
            text = cleaned
    return text, modified


# ─── الحارس الرئيسي ─────────────────────────────────────────────────────────

class OutputGuard:
    """
    يُطبَّق على كل رد قبل إرساله للمستخدم

    الاستخدام:
        guard = OutputGuard()
        safe_response = guard.filter(raw_model_output, user_tier, fix_data)
    """

    def __init__(self):
        self.store = get_store()

    def filter(
        self,
        raw_output:   str,
        tier:         UserTier,
        fix_data:     Optional[dict] = None,   # بيانات الإصلاح (للمشترك)
        apply_fix_fn: Optional[callable] = None,  # دالة تطبيق الإصلاح
    ) -> GuardedResponse:
        """
        المرشح الرئيسي — يعالج الرد حسب مستوى المستخدم
        """
        if tier == UserTier.FREE:
            return self._handle_free(raw_output)
        else:
            return self._handle_subscriber(raw_output, fix_data, apply_fix_fn)

    # ── مستخدم مجاني ─────────────────────────────────────────────────────────

    def _handle_free(self, raw_output: str) -> GuardedResponse:
        """
        Free tier:
        - يُعطى تقرير بالثغرات
        - يُعطى تعليمات نصية للإصلاح
        - لا كود، لا تعديل تلقائي
        """
        # أزل أي كود اخترق الفلتر
        clean, removed = _strip_code(raw_output)

        # تأكد أن الرد فيه تقرير وتعليمات فقط
        report = self._format_free_report(clean)

        return GuardedResponse(
            tier        = UserTier.FREE,
            report      = report,
            fix_applied = False,
            fix_summary = "",
            code_removed= removed,
        )

    def _format_free_report(self, text: str) -> str:
        """يعيد تنسيق الرد ليكون تقريراً نصياً واضحاً"""
        header = (
            "═══════════════════════════════════════\n"
            "         تقرير فحص الأمان — مرصد       \n"
            "═══════════════════════════════════════\n"
            "الخطة المجانية: تقرير + تعليمات فقط\n"
            "للحصول على الإصلاح التلقائي: اشترك في الخطة المدفوعة\n"
            "───────────────────────────────────────\n"
        )
        return header + text

    # ── مشترك ────────────────────────────────────────────────────────────────

    def _handle_subscriber(
        self,
        raw_output:   str,
        fix_data:     Optional[dict],
        apply_fix_fn: Optional[callable],
    ) -> GuardedResponse:
        """
        Subscriber tier:
        - يُطبَّق الإصلاح تلقائياً (صامت)
        - يُرسَل ملخص ما تم فقط — لا كود
        """
        fix_applied = False
        fix_summary = ""

        # طبّق الإصلاح إذا توفرت البيانات والدالة
        if fix_data and apply_fix_fn:
            try:
                apply_fix_fn(fix_data)
                fix_applied = True
                vuln_types = [p.get("vulnerability_type", "ثغرة")
                              for p in fix_data.get("patches", [])]
                fix_summary = f"تم إصلاح {len(vuln_types)} ثغرة: {', '.join(vuln_types)}"
            except Exception as e:
                fix_summary = f"لم يكتمل الإصلاح: {str(e)[:100]}"

        # أزل الكود من الرد النصي
        clean, removed = _strip_code(raw_output)

        # ابنِ رد المشترك
        report = self._format_subscriber_report(clean, fix_applied, fix_summary)

        return GuardedResponse(
            tier        = UserTier.SUBSCRIBER,
            report      = report,
            fix_applied = fix_applied,
            fix_summary = fix_summary,
            code_removed= removed,
        )

    def _format_subscriber_report(
        self, text: str, fix_applied: bool, summary: str
    ) -> str:
        status = (
            f"✅ {summary}" if fix_applied
            else "⚠ يحتاج مراجعة يدوية للإصلاح"
        )
        header = (
            "═══════════════════════════════════════\n"
            "         تقرير فحص الأمان — مرصد       \n"
            "═══════════════════════════════════════\n"
            f"{status}\n"
            "───────────────────────────────────────\n"
        )
        footer = (
            "\n───────────────────────────────────────\n"
            "⚠ تطبيق أي تعديل يتطلب موافقتك البشرية"
        )
        return header + text + footer


# ─── مدير المشتركين ───────────────────────────────────────────────────────────

class TierManager:
    """
    يحدد مستوى المستخدم — يمكن ربطه بقاعدة بيانات لاحقاً

    حالياً: JSON بسيط في المجلد المحلي
    """

    def __init__(self):
        self._tier_db_path = Path(__file__).parent.parent / "database" / "tiers.json"
        self._load()

    def _load(self):
        import json
        if self._tier_db_path.exists():
            self._tiers = json.loads(self._tier_db_path.read_text())
        else:
            self._tiers = {}

    def _save(self):
        import json
        self._tier_db_path.parent.mkdir(parents=True, exist_ok=True)
        self._tier_db_path.write_text(
            json.dumps(self._tiers, ensure_ascii=False, indent=2)
        )

    def get_tier(self, user_id: str) -> UserTier:
        """يُعيد مستوى المستخدم"""
        t = self._tiers.get(user_id, "free")
        return UserTier.SUBSCRIBER if t == "subscriber" else UserTier.FREE

    def upgrade(self, user_id: str):
        """ترقية مستخدم لمشترك"""
        self._tiers[user_id] = "subscriber"
        self._save()
        print(f"✓ {user_id} → مشترك")

    def downgrade(self, user_id: str):
        self._tiers[user_id] = "free"
        self._save()
        print(f"✓ {user_id} → مجاني")


# ─── اختبار سريع ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    guard = OutputGuard()

    raw = """
    وجدت ثغرة SQL Injection في السطر 5.

    الإصلاح:
    ```python
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    ```

    استخدم Parameterized Queries دائماً.
    """

    print("=== مستخدم مجاني ===")
    r = guard.filter(raw, UserTier.FREE)
    print(r.report)
    print(f"\nكود أُزيل: {r.code_removed}")

    print("\n=== مشترك ===")
    r2 = guard.filter(raw, UserTier.SUBSCRIBER, fix_data={"patches": [{"vulnerability_type": "SQL Injection"}]})
    print(r2.report)
