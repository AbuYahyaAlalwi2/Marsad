"""المكافأة ثنائية الطبقة — تحسين لرفع الاستدلال، لا الحل السطحي فقط.

مكافأة "نجح/فشل" وحدها تعلّم النموذج الوصول لإجابة صحيحة، لا فهم السبب. نموذج يحفظ
الأنماط دون فهم السببية يفشل أمام أي صياغة جديدة للمشكلة نفسها. هذه الوحدة تفصل
درجتين مستقلتين:
  1. correctness: هل الترقيع يعمل فعلياً (يُحسب خارجياً عبر sandbox_client/judge، يُمرَّر هنا).
  2. explanation: هل سبق الترقيعَ تفسيرٌ سببي حقيقي (لماذا تحدث الثغرة)، لا حشو كلمات مفتاحية،
     ولا نسخ حرفي من اسم CWE فقط.

مكافأة الاستدلال تُحتسب فقط إن ظهر التفسير قبل الكود (ترتيب يفرض "فهم أولاً")، وتحتوي
مصطلحات السبب الجذري الخاصة بفئة CWE، لا الكلمة المفتاحية وحدها."""
import re

_FENCE = re.compile(r"```")

# لكل CWE: مصطلحات "السبب الجذري" (لا اسم الثغرة نفسه) التي يجب أن يذكرها تفسير حقيقي.
ROOT_CAUSE_TERMS = {
    "CWE-89": ["تسلسل", "concatenat", "بلا تنقية", "دون معامَلة", "استعلام مبني من مدخل", "ثقة بمدخل"],
    "CWE-78": ["سطر أوامر", "shell", "تمرير مدخل", "دون تحقق", "تنفيذ أمر نظام"],
    "CWE-22": ["مسار نسبي", "../", "خروج من المجلد", "traversal", "مسار غير مُطبَّع"],
    "CWE-79": ["يُدرج في الصفحة", "دون تهريب", "escape", "html", "تنفيذ سكربت"],
    "CWE-502": ["إلغاء تسلسل", "deserializ", "بيانات غير موثوقة", "تنفيذ كود تعسفي"],
    "CWE-798": ["مكتوب في الكود", "hardcod", "بدلاً من متغير بيئة", "ثابت في المصدر"],
}
GENERIC_FILLER = ["هذه ثغرة خطيرة", "يجب إصلاح هذا فوراً", "من المهم الانتباه", "هذا أمر حسّاس"]


def correctness_score(test_passed, test_total):
    """0..1 — نسبة الاختبارات الفعلية الناجحة. يُستدعى بنتيجة تنفيذ حقيقي من sandbox_client/judge،
    لا حكماً ذاتياً من هذه الدالة."""
    if test_total <= 0:
        return 0.0
    return max(0.0, min(1.0, test_passed / test_total))


def explanation_score(response_text, cwe):
    """0..1 — جودة التفسير السببي قبل الكود. يعيد 0 فوراً إن غاب التفسير أو جاء بعد الكود."""
    text = response_text or ""
    m = _FENCE.search(text)
    before_code = text[:m.start()] if m else text
    if len(before_code.strip()) < 20:
        return 0.0  # لا تفسير يُذكر قبل الكود

    terms = ROOT_CAUSE_TERMS.get(cwe, [])
    if not terms:
        return 0.3 if len(before_code.strip()) >= 40 else 0.0  # CWE غير مغطّى: تقدير محافظ فقط

    hits = sum(1 for t in terms if t.lower() in before_code.lower())
    term_score = min(1.0, hits / 2)  # مصطلحان مطابقان كافيان لدرجة كاملة على هذا المحور

    filler_hits = sum(1 for f in GENERIC_FILLER if f in before_code)
    filler_penalty = min(0.4, filler_hits * 0.2)  # حشو عام بلا تقنية يُخصم، لا يُحتسب كتفسير

    return max(0.0, term_score - filler_penalty)


def combined_reward(test_passed, test_total, response_text, cwe,
                    w_correctness=0.7, w_explanation=0.3):
    """المجموع الموزون. correctness أولاً وأهم (0.7) — لا تفسير بديل عن حل خاطئ،
    لكن حلاً صحيحاً بلا فهم (explanation=0) يُحرم من 30% من المكافأة الكاملة."""
    c = correctness_score(test_passed, test_total)
    e = explanation_score(response_text, cwe)
    return {"correctness": round(c, 3), "explanation": round(e, 3),
           "total": round(w_correctness * c + w_explanation * e, 3)}
