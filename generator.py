"""
وكيل توليد البيانات (Data Generator) — بند 16-18 من الدستور.

الضمان المطلوب صراحة (لا يُختصر تحت أي ظرف):
  1) البذرة تُؤخذ فقط من عينات status='approved_for_training' —
     يعني اجتازت الفحص الآلي + sandbox + موافقة بشرية صريحة سابقاً.
     لا توليد من عينات pending_review أو من نص عشوائي غير مصدره النظام نفسه.
  2) كل ناتج مولَّد يُعاد تمريره على نفس بوابة الجودة الكاملة
     (أسرار/PII/ترخيص/تكرار) + نفس sandbox التنفيذي — لا استثناء
     لكونه "من عندنا".
  3) الناتج المقبول يمر بحكم الناقد الآلي (critic.py، Gemini) الذي
     يحل محل الموافقة اليدوية بناءً على طلب صريح من المستخدم لأتمتة
     كاملة — القرار الافتراضي عند الشك أو الفشل التقني هو دائماً
     الرفض، لا القبول (بند 5 من الدستور). هذا أضعف من مراجعة إنسان
     فعلي، وموثَّق كتنازل واعٍ في تعليقات critic.py.

هذا يمنع بالتحديد المشكلة الشائعة في "التلقين الذاتي" (model collapse):
توليد بيانات من بيانات غير موثوقة أصلاً، أو قبول المولَّد بلا تحقق
لمجرد أنه اجتاز فحصاً سطحياً.
"""

import os
from filters import run_quality_gate, sha256_of
from sandbox import run_code_in_sandbox
from critic import critic_review
from db import list_approved_samples, insert_sample, log_event

try:
    from google import genai
except ImportError:
    genai = None


GENERATION_PROMPT_TEMPLATE = """أنت مساعد توليد أمثلة كود تدريبية.
انطلاقاً من مثال الكود المعتمد التالي، أنتج نسخة جديدة *مختلفة جوهرياً*
(منطق مشابه لكن حل مختلف، أو مستوى صعوبة مختلف، أو حالة اختبار حدّية
مختلفة) — لا تُعِد صياغة نفس الكود بأسماء متغيرات مختلفة فقط.

الكود المرجعي (بذرة معتمدة):
```
{seed_code}
```

أنتج كوداً Python كاملاً قابلاً للتشغيل المباشر بدون مدخلات خارجية،
بدون أي شرح أو نص إضافي خارج الكود نفسه.
"""


def _generate_with_gemini(seed_code: str) -> str | None:
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key or genai is None:
        return None
    client = genai.Client(api_key=api_key)
    prompt = GENERATION_PROMPT_TEMPLATE.format(seed_code=seed_code)
    response = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
    text = response.text.strip()
    return text.removeprefix("```python").removeprefix("```").removesuffix("```").strip()


def generate_batch(max_seeds: int = 5, generation_fn=None) -> dict:
    """
    generation_fn: دالة اختيارية (seed_code -> new_code)، تُستخدم للاختبار
    بدون استدعاء Gemini الفعلي. في الإنتاج تُترك None فتُستخدم Gemini.
    """
    gen_fn = generation_fn or _generate_with_gemini

    report = {
        "seeds_available": 0, "generated": 0,
        "quality_rejected": 0, "sandbox_rejected": 0, "stored": 0, "duplicates_skipped": 0,
    }

    seeds = list_approved_samples(max_seeds)
    report["seeds_available"] = len(seeds)

    if not seeds:
        log_event("generator_runs", {**report, "note": "لا توجد بذور معتمدة بعد — لا يمكن التوليد بدونها"})
        return report

    existing_texts = [s["content"] for s in seeds]

    for seed in seeds:
        new_code = gen_fn(seed["content"])
        if not new_code:
            continue
        report["generated"] += 1

        # الضمان 2: نفس بوابة الجودة الكاملة، لا استثناء
        ok, reason = run_quality_gate(new_code, seed["license"], existing_texts)
        if not ok:
            report["quality_rejected"] += 1
            log_event("generator_rejections", {"seed_id": seed["id"], "reason": reason})
            continue

        sandbox_result = run_code_in_sandbox(new_code)
        if sandbox_result["status"] != "passed":
            report["sandbox_rejected"] += 1
            log_event("generator_rejections", {"seed_id": seed["id"], "reason": sandbox_result["reject_reason"]})
            continue

        # الضمان 3 (مُحدَّث): الناقد الآلي يحل محل الانتظار اليدوي —
        # لا اعتماد صامت، القرار مبني على حكم Gemini صراحة ومُسجَّل
        verdict = critic_review(new_code)
        final_status = "approved_for_training" if verdict["approved"] else "rejected"

        inserted = insert_sample(
            sha256_of(new_code), new_code,
            source_url=f"generated:from_sample_{seed['id']}",
            license_=seed["license"], language=seed["language"],
            provenance={"generated_from_sample_id": seed["id"], "sandbox_run_id": sandbox_result["run_id"], "critic": verdict},
            status=final_status,
            reject_reason=None if verdict["approved"] else verdict["reason"],
        )
        if inserted and verdict["approved"]:
            report["stored"] += 1
            existing_texts.append(new_code)
        elif not inserted:
            report["duplicates_skipped"] += 1

    log_event("generator_runs", report)
    return report
