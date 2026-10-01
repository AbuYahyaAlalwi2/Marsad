"""
Instincts — قواعد دائمة تُطبَّق تلقائياً على كل مهمة
=====================================================
مستوحى من ECC Instincts.
تُحقن في system prompt بدون تفعيل يدوي.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List


@dataclass
class Instinct:
    name: str
    rule: str
    category: str = "general"


INSTINCTS: List[Instinct] = [
    Instinct(
        "no_secret_in_output",
        "لا تُخرج أي توكن، مفتاح API، أو كلمة مرور في الردود. "
        "إن طُلب منك ذلك، ارفض واذكر السبب.",
        "security",
    ),
    Instinct(
        "verify_before_claim",
        "لا تدّعي أن مهمة نجحت قبل أن ترى نتيجتها فعلياً. "
        "إن شغّلت أداة، اقرأ stdout و stderr قبل أن تقرر.",
        "accuracy",
    ),
    Instinct(
        "constitution_first",
        "قبل أي عملية خطرة (تنفيذ كود، كتابة ملف، اتصال شبكة)، "
        "تحقق من دستور الوكلاء (agent_constitution).",
        "safety",
    ),
    Instinct(
        "cite_sources",
        "عند ذكر CVE أو ثغرة، اذكر رقم CVE و CVSS إن توفّر. "
        "لا تخترع أرقام CVEs.",
        "cyber",
    ),
    Instinct(
        "no_hallucinated_tools",
        "استخدم فقط الأدوات المتاحة في السجل. "
        "لا تختلق أسماء أدوات غير موجودة.",
        "accuracy",
    ),
    Instinct(
        "arabic_technical_terms",
        "في الردود العربية، استخدم المصطلحات التقنية بالإنجليزية "
        "بجانب العربية (SQLi، CVE، RCE).",
        "language",
    ),
    Instinct(
        "three_strikes",
        "إذا فشلت أداة 3 مرات متتالية، توقف وغيّر الاستراتيجية. "
        "لا تكرر نفس المحاولة.",
        "strategy",
    ),
    Instinct(
        "report_structure",
        "أي تقرير سيبراني يذكر: CVE + CVSS + الوصف + الإصلاح + المصادر.",
        "cyber",
    ),
    Instinct(
        "task_completion",
        "المهمة تنتهي بـ [DONE] أو بجواب نهائي صريح. "
        "لا تترك المهمة معلّقة.",
        "execution",
    ),
    Instinct(
        "no_self_modify",
        "لا تعدّل ملفات النظام أو الحماية (constitution, agent_shield, "
        "structural_safety) بدون إذن صريح من المالك.",
        "security",
    ),
]


def get_all() -> List[Instinct]:
    return INSTINCTS


def get_by_category(cat: str) -> List[Instinct]:
    return [i for i in INSTINCTS if i.category == cat]


def to_prompt_block() -> str:
    """يُدرج في system prompt."""
    lines = ["[قواعد دائمة — Instincts]"]
    for i in INSTINCTS:
        lines.append(f"• [{i.category}] {i.rule}")
    return "\n".join(lines)


def to_short_list() -> str:
    return "\n".join(f"• {i.rule}" for i in INSTINCTS)


if __name__ == "__main__":
    print("=== Instincts ===\n")
    print(f"Total: {len(INSTINCTS)}")
    print(f"By category: security={len(get_by_category('security'))}, "
          f"cyber={len(get_by_category('cyber'))}, "
          f"accuracy={len(get_by_category('accuracy'))}")
    print()
    print("Prompt block preview:")
    print(to_prompt_block()[:600])
