"""
Supervisor Chat — يستخدم Gemini لتحويل أمر طبيعي (عربي/إنجليزي) إلى
خطة منظّمة. لا ينفّذ أي تغيير مباشرة أبداً — التسلسل دائماً:
أمر → تحليل Gemini → خطة → مراجعة المستخدم → Approve → تنفيذ → تسجيل.
"""

import os
import json

try:
    import google.generativeai as genai
except ImportError:
    genai = None

CONSTITUTION_SUMMARY = """
مبادئ عامة يجب الالتزام بها عند اقتراح أي خطة:
1. عند الشك في الترخيص → الافتراضي منع الجمع.
2. لا تقترح تجاوز robots.txt أو ToS.
3. الحل الأبسط يُفضَّل دائماً.
4. لا تدّعِ نجاح خطوة لم تُنفَّذ أو تُتحقق منها فعلياً.
5. أي بيانات شخصية (PII) تُحجب أو تُرفض.
"""

SYSTEM_PROMPT = f"""أنت المشرف (Supervisor) لنظام مرصد (Marsad) — مركز قيادة وكلاء AI.
مهمتك تحويل أمر المستخدم إلى خطة منظمة بصيغة JSON فقط، بدون أي نص إضافي.
لا تنفّذ أي شيء بنفسك، فقط اقترح خطة يراجعها المستخدم.

{CONSTITUTION_SUMMARY}

صيغة الإخراج (JSON فقط):
{{
  "understood_command": "...",
  "action_type": "clone_group | reroute_task | isolate_proxy | clarification_needed | other",
  "steps": ["...", "..."],
  "risks": ["..."],
  "needs_clarification": false,
  "clarification_question": null
}}
"""


def get_plan(user_command: str) -> dict:
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key or genai is None:
        return {
            "understood_command": user_command,
            "action_type": "clarification_needed",
            "steps": [],
            "risks": ["GOOGLE_API_KEY غير مضبوط أو مكتبة google-generativeai غير مثبتة"],
            "needs_clarification": True,
            "clarification_question": "يرجى ضبط متغير البيئة GOOGLE_API_KEY أولاً.",
        }

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.0-flash", system_instruction=SYSTEM_PROMPT)
    response = model.generate_content(user_command)

    raw = response.text.strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {
            "understood_command": user_command,
            "action_type": "clarification_needed",
            "steps": [],
            "risks": ["تعذّر تحليل رد النموذج كـ JSON صالح"],
            "needs_clarification": True,
            "clarification_question": raw[:300],
        }
