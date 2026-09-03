"""
وكيل النقد الآلي (Critic Agent) — يستبدل ضغطة الموافقة اليدوية بحكم
آلي مبني على نص الدستور الفعلي، لا فلتر ثابت. هذا أقوى من regex لأنه
يفهم السياق (مثلاً كود يبدو سليماً لكنه يحتوي منطقاً خطراً لا يطابقه
أي نمط ثابت)، لكنه أضعف من إنسان لأنه لا يزال عرضة لأخطاء نموذج AI —
لذلك كل حكم يُسجَّل بسببه الكامل في الأحداث للمراجعة اللاحقة عند الشك.

مبدأ صارم (بند 5 من الدستور، مطبَّق هنا حرفياً): لو Gemini غير متاح
أو رد بصيغة غير مفهومة، القرار الافتراضي رفض — لا قبول لعدم القدرة
على الحكم.
"""

import os
import json

try:
    from google import genai
except ImportError:
    genai = None

from db import log_event

CRITIC_SYSTEM_PROMPT = """أنت الناقد الدستوري (Constitutional Critic) لنظام مرصد.
مهمتك الوحيدة: الحكم هل هذه العينة تخالف أياً من المبادئ التالية أم لا.
لا تصحّح الكود، لا تشرحه، فقط احكم.

مبادئ الدستور ذات الصلة:
1. لا يجوز أن تحتوي العينة أي سر أو مفتاح API حتى لو بصيغة غير معروفة مسبقاً.
2. لا يجوز أن تحتوي أي بيانات شخصية (أسماء كاملة مرتبطة بمعلومات اتصال، عناوين، أرقام تعريف).
3. الكود يجب أن يكون منطقياً سليماً وليس فقط "يعمل" — لا كود يحقق نتيجة صحيحة بطريقة ملتوية أو مضللة.
4. لا محتوى ضار (كود استغلال ثغرات، تعليمات لصنع أذى، محتوى يحض على كراهية).
5. الكود يجب أن يكون بلغة برمجة حقيقية مفهومة، لا نص عشوائي أو مموّه.

أعد فقط JSON بالصيغة التالية، بدون أي نص إضافي:
{"verdict": "approve" | "reject", "reason": "سبب مختصر بالعربية", "confidence": 0.0-1.0}

إذا لم تكن متأكداً بثقة > 0.7، اجعل verdict = "reject" دائماً — الشك يعني رفض، لا قبول.
"""


def critic_review(content: str) -> dict:
    """يُرجع {'approved': bool, 'reason': str, 'confidence': float, 'source': 'gemini'|'fallback_reject'}"""
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key or genai is None:
        result = {"approved": False, "reason": "GOOGLE_API_KEY غير متاح — رفض افتراضي، لا حكم بدون نموذج", "confidence": 0.0, "source": "fallback_reject"}
        log_event("critic_reviews", result)
        return result

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=f"العينة المطلوب الحكم عليها:\n```\n{content}\n```",
            config={"system_instruction": CRITIC_SYSTEM_PROMPT},
        )
        raw = response.text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed = json.loads(raw)

        approved = parsed.get("verdict") == "approve" and float(parsed.get("confidence", 0)) > 0.7
        result = {
            "approved": approved,
            "reason": parsed.get("reason", ""),
            "confidence": parsed.get("confidence", 0),
            "source": "gemini",
        }
    except Exception as e:
        # أي فشل (شبكة، تحليل JSON، غيره) → رفض افتراضي آمن، لا ادّعاء نجاح لم يتحقق (بند 5)
        result = {"approved": False, "reason": f"فشل الحصول على حكم صالح: {e}", "confidence": 0.0, "source": "fallback_reject"}

    log_event("critic_reviews", result)
    return result
