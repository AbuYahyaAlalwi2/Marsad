"""حَكَم v2 — مقياس تقريبي (وليس إثباتاً) لجودة إصلاح ثغرة.

الفرق عن تداخل الكلمات: الدرجة العالية تتطلب أن يحوي الجواب **كوداً** يطابق الأسطر المضافة فعلاً في
الإصلاح الحقيقي. حشو أسماء الثغرة والكلمات المفتاحية بلا كود لا يتجاوز 25 درجة.
لإثبات حقيقي يلزم تشغيل اختبارات المشروع على الرقعة، وهذا غير متوفر هنا."""
import difflib
import re

CWE_WORDS = {
    "CWE-79": ["xss", "cross-site scripting", "escape", "sanitiz"], "CWE-89": ["sql", "parameteri", "prepared", "bind"],
    "CWE-22": ["traversal", "normaliz", "realpath", "../"], "CWE-78": ["command injection", "shlex", "shell=", "subprocess"],
    "CWE-20": ["validat"], "CWE-502": ["deserializ", "pickle", "safe_load"], "CWE-352": ["csrf"],
    "CWE-918": ["ssrf"], "CWE-434": ["upload"], "CWE-190": ["overflow", "integer"], "CWE-476": ["null"],
    "CWE-787": ["bounds", "overflow", "buffer"], "CWE-125": ["bounds", "out-of-bounds", "buffer"],
    "CWE-416": ["use-after-free", "use after free"], "CWE-200": ["leak", "disclos", "expos"],
}
_FENCE = re.compile(r"```[a-zA-Z0-9_+\-./ ]*\n(.*?)```", re.S)


def _norm(line):
    return re.sub(r"\s+", " ", line.strip())


def _meaningful(line):
    n = _norm(line)
    return len(n) >= 4 and not re.fullmatch(r"[{}()\[\];,]*", n) and not n.startswith(("#", "//", "*", "/*"))


def added_lines(before, after):
    b = {_norm(x) for x in before.splitlines()}
    return [_norm(x) for x in after.splitlines() if _meaningful(x) and _norm(x) not in b]


_CODE_HINTS = re.compile(r"^(<\?php|<?|def |class |function |#include|import |from |public |private |const |let |var |fn |func )")

def code_lines(answer):
    blocks = _FENCE.findall(answer or "")
    if blocks:
        return [_norm(x) for blk in blocks for x in blk.splitlines() if _meaningful(x)]
    # fallback: كود عاري بدون backticks
    out = []
    for line in (answer or "").splitlines():
        n = _norm(line)
        if _meaningful(n) and _CODE_HINTS.match(n):
            out.append(n)
    return out


def judge(task, answer):
    answer = str(answer or "")
    if not answer.strip():
        return {"score": 0, "details": ["جواب فارغ"], "proxy": True}
    code = code_lines(answer)
    truth = added_lines(task.get("before") or "", task.get("after") or "")
    details = []
    if truth and code:
        hit = sum(1 for t in truth if max((difflib.SequenceMatcher(None, t, c).ratio() for c in code), default=0) >= 0.8)
        fix_pts = 60.0 * hit / len(truth)
        details.append(f"تطابق الإصلاح {hit}/{len(truth)}")
    else:
        fix_pts = 20.0 if code and not truth else 0.0
        details.append("لا كود" if not code else "لا أسطر مرجعية")
    cwe = (task.get("cwe") or "").upper()
    low = answer.lower()
    class_pts, max_pts = 0.0, 75.0
    if cwe:
        max_pts = 100.0
        words = CWE_WORDS.get(cwe, [])
        if cwe.lower() in low or any(w in low for w in words):
            class_pts = 25.0
            details.append("حدّد فئة الثغرة")
    form_pts = 15.0 if code and len(answer) <= 6000 else 0.0
    score = int(min(100.0, (fix_pts + class_pts + form_pts) / max_pts * 100.0))
    return {"score": score, "details": details, "proxy": True}
