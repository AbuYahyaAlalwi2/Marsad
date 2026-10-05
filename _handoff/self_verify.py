"""حلقة التحقق الذاتي: لا يُسلَّم كود للمستخدم قبل تنفيذه فعلياً والتأكد من نجاحه.
هذا نمط عام (self-verification / self-correction loop)، ليس حِكراً على أي شركة أو نموذج —
أي نظام وكيل له أداة تنفيذ يستطيع تطبيقه. مستقل تماماً، يعمل مع أي llm وأي sandbox
يطابقان الواجهة الدنيا الموضحة أدناه (duck typing، لا وراثة مطلوبة):

  llm.chat(messages: list[dict], **kw) -> {"content": str}
  sandbox.run_python(code: str, timeout: int) -> {"status": "ok"|"error"|"timeout"|..., "stdout": str, "stderr": str}
  (لتشغيل جافاسكربت/تايبسكربت مرر run_method="run_javascript" أو "run_typescript")
"""
import re

_FENCE = re.compile(r"```(?:python|javascript|typescript|js|ts)?\s*\n(.*?)```", re.S)

PROMPT = ("اكتب كوداً ينفّذ المهمة التالية. ضعه داخل كتلة ```LANGUAGE ... ``` واحدة فقط، "
          "بلا شرح خارج الكتلة. اطبع النتيجة بوضوح.\n\nالمهمة: {task}")

FIX_PROMPT = ("الكود السابق فشل عند التنفيذ الفعلي. صحّحه ولا تكرر نفس الخطأ.\n"
             "الكود:\n```\n{code}\n```\nرسالة الخطأ:\n{error}\n\nأعد الكود المصحَّح كاملاً داخل كتلة ```LANGUAGE ... ``` واحدة.")


def extract_code(text):
    m = _FENCE.search(text or "")
    return (m.group(1) if m else (text or "")).strip()


def verify_and_fix(llm, sandbox, task, language="python", max_attempts=3, timeout=10,
                   run_method=None, extra_system=None):
    """يعيد قاموساً: {"ok": bool, "code": str, "attempts": int, "run": dict, "history": list}
    - ok=True فقط إذا نفّذ الصندوق الكود فعلياً وأعاد status == "ok".
    - history يحوي كل محاولة (code, run) للتدقيق لاحقاً، حتى لو نجحت من أول مرة."""
    run_fn = getattr(sandbox, run_method or f"run_{language}")
    messages = [{"role": "user", "content": PROMPT.format(task=task).replace("LANGUAGE", language)}]
    if extra_system:
        messages.insert(0, {"role": "system", "content": extra_system})
    history = []
    code = ""
    for attempt in range(1, max_attempts + 1):
        out = llm.chat(messages, max_tokens=1200, temperature=0.2 if attempt == 1 else 0.0)
        code = extract_code(out["content"])
        if not code:
            history.append({"code": "", "run": {"status": "no_code", "stdout": "", "stderr": "لم يُستخرَج كود"}})
            messages.append({"role": "assistant", "content": out["content"]})
            messages.append({"role": "user", "content": "لم أجد كتلة كود صالحة. أعد المحاولة بكتلة ``` واحدة فقط."})
            continue
        run = run_fn(code, timeout)
        history.append({"code": code, "run": run})
        if run.get("status") == "ok":
            return {"ok": True, "code": code, "attempts": attempt, "run": run, "history": history}
        messages.append({"role": "assistant", "content": out["content"]})
        err = (run.get("stderr") or run.get("status") or "فشل غير معروف")[:1500]
        messages.append({"role": "user", "content": FIX_PROMPT.format(code=code, error=err).replace("LANGUAGE", language)})
    return {"ok": False, "code": code, "attempts": max_attempts, "run": history[-1]["run"] if history else None,
           "history": history}
