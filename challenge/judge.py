"""Judge — يقيّم إجابة Solver على مهمة CVE (0-100)."""
import re
from pathlib import Path

try:
    from core.agent_constitution import AgentConstitution
except ImportError:
    AgentConstitution = None


def _tokenize(text):
    """تقسيم بسيط لكلمات."""
    return set(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]{2,}", text.lower()))


def judge(task, solver_answer):
    """
    معايير التقييم:
      - ذكر CVE الصحيح؟           → 30 نقطة
      - ذكر كلمات مفتاحية (نوع المهاجمة)  → 20 نقطة
      - تشابه مع الحل الحقيقي (after)     → 40 نقطة
      - ذكر إصلاح تقني             → 10 نقاط
    """
    # 0. فحص الدستور (إن وُجد)
    if AgentConstitution:
        d = AgentConstitution.check_task(task)
        if not d.allowed:
            return {"score": 0, "details": [f"❌ {d.article}: {d.reason}"],
                    "blocked_by": d.article}

    if not solver_answer or not isinstance(solver_answer, str):
        return {"score": 0, "details": ["إجابة فارغة"]}

    answer_low = solver_answer.lower()
    cve = (task.get("cve") or "").lower()
    correct = (task.get("after") or "").lower()
    before = (task.get("before") or "").lower()

    score = 0
    details = []

    # 1. ذكر CVE (30)
    if cve and cve in answer_low:
        score += 30
        details.append("✓ ذكر CVE")

    # 2. كلمات مفتاحية سيبرانية (20)
    keyword_pool = {
        "injection", "xss", "sql", "rce", "overflow", "deserialization",
        "traversal", "auth", "bypass", "csrf", "ssrf", "xxe", "logging",
        "log4j", "validation", "sanitiz", "escape", "encode", "parameter",
        "حقن", "تحقق", "تنقية", "تشفير", "ثغرة", "استغلال",
    }
    kws_found = [k for k in keyword_pool if k in answer_low]
    if kws_found:
        score += min(len(kws_found) * 5, 20)
        details.append(f"✓ كلمات مفتاحية: {len(kws_found)}")

    # 3. تشابه مع الحل الصحيح (40)
    if correct:
        tokens_correct = _tokenize(correct)
        tokens_answer = _tokenize(solver_answer)
        if tokens_correct:
            overlap = len(tokens_correct & tokens_answer) / len(tokens_correct)
            score += int(overlap * 40)
            if overlap > 0.1:
                details.append(f"✓ تشابه: {overlap*100:.0f}%")

    # 4. اقتراح إصلاح تقني (10)
    fix_markers = ["fix", "patch", "update", "replace", "validate",
                   "sanitize", "escape", "أصلح", "حدّث", "استبدل", "تحقق"]
    if any(m in answer_low for m in fix_markers):
        score += 10
        details.append("✓ اقترح إصلاحاً")

    return {"score": min(score, 100), "details": details}


if __name__ == "__main__":
    # اختبار سريع
    task = {
        "cve": "CVE-2021-44228",
        "before": "logger.info(userInput);",
        "after": "logger.info(sanitize(userInput));",
    }
    tests = [
        "الثغرة CVE-2021-44228 هي حقن JNDI في Log4j. الإصلاح: تحديث الإصدار.",
        "مرحبا",
        "CVE-2021-44228",
    ]
    for t in tests:
        r = judge(task, t)
        print(f"  {r['score']:3d}/100  | {t[:50]}")
