"""
وكيل جمع أسئلة/أجوبة من Stack Exchange API الرسمي (api.stackexchange.com).

مهم — الفرق عن الفكرة المرفوضة سابقاً:
هذا لا يسجّل حسابات ولا يطرح أسئلة وهمية ولا ينتحل تفاعلاً بشرياً.
هو فقط **قراءة** من API رسمي عام مصمم صراحة لهذا الغرض. محتوى
Stack Exchange مرخّص بالكامل CC BY-SA 4.0 — الترخيص يُسجَّل مع كل
عينة (بند 8 من الدستور: توثيق المصدر والترخيص إلزامي).

⚠️ إفصاح صريح: لم أستطع اختبار هذا الملف حياً (استدعاء API فعلي)
داخل بيئة التطوير الحالية — الشبكة المتاحة لي هنا مقصورة على سجلات
حزم برمجية (pypi, npm, github...) ولا تشمل api.stackexchange.com.
اختبرته بمحاكاة رد JSON بصيغة الـ API الرسمية الموثّقة (schema)،
لا باستدعاء فعلي. اختبر أنت أول دفعة صغيرة (max_questions=3) وراجع
التقرير قبل تشغيله على نطاق أوسع — نفس مبدأ "لا ادّعاء نجاح غير
محقق" ينطبق عليّ هنا أيضاً.
"""

import time
import re
import requests

from filters import run_quality_gate, sha256_of
from db import insert_sample, log_event, list_recent_samples

SE_API = "https://api.stackexchange.com/2.3"
LICENSE = "cc-by-sa-4.0"

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_CODE_BLOCK_RE = re.compile(r"<pre><code>(.*?)</code></pre>", re.DOTALL)


def _strip_html(html: str) -> str:
    """تحويل مبسّط من HTML إلى نص عادي — يحافظ على كتل الكود، يزيل بقية الوسوم."""
    text = html
    text = text.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&").replace("&quot;", '"')
    text = _HTML_TAG_RE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def fetch_questions(site: str = "stackoverflow", tag: str = "python", max_questions: int = 10,
                     api_key: str | None = None) -> list[dict]:
    params = {
        "order": "desc", "sort": "votes", "site": site, "tagged": tag,
        "pagesize": max_questions, "filter": "withbody",
    }
    if api_key:
        params["key"] = api_key
    resp = requests.get(f"{SE_API}/questions", params=params, timeout=15)
    if resp.status_code != 200:
        log_event("se_collector_errors", {"stage": "fetch_questions", "status": resp.status_code, "body": resp.text[:300]})
        return []
    return resp.json().get("items", [])


def fetch_accepted_answer(question_id: int, site: str, api_key: str | None = None) -> dict | None:
    params = {"order": "desc", "sort": "votes", "site": site, "filter": "withbody"}
    if api_key:
        params["key"] = api_key
    resp = requests.get(f"{SE_API}/questions/{question_id}/answers", params=params, timeout=15)
    if resp.status_code != 200:
        log_event("se_collector_errors", {"stage": "fetch_answers", "status": resp.status_code, "qid": question_id})
        return None
    items = resp.json().get("items", [])
    accepted = [a for a in items if a.get("is_accepted")]
    return (accepted or items or [None])[0]


def collect_batch(site: str = "stackoverflow", tag: str = "python", max_questions: int = 10,
                   api_key: str | None = None) -> dict:
    """
    دورة جمع كاملة: سؤال + الجواب المقبول (أو الأعلى تصويتاً)، تُدمج
    كنص واحد، تمرّ ببوابة الجودة، تُخزَّن بحالة pending_review.
    لا تحقق sandbox هنا — المحتوى نص سؤال/جواب، ليس بالضرورة كوداً
    قابلاً للتنفيذ المستقل (قد يحتوي مقتطفات جزئية فقط).
    """
    report = {"questions_fetched": 0, "no_answer": 0, "quality_rejected": 0, "stored": 0, "duplicates_skipped": 0}
    existing_texts = [s["content"] for s in list_recent_samples(300)]

    questions = fetch_questions(site, tag, max_questions, api_key)

    for q in questions:
        report["questions_fetched"] += 1
        answer = fetch_accepted_answer(q["question_id"], site, api_key)
        if not answer:
            report["no_answer"] += 1
            continue

        question_text = _strip_html(q.get("body", ""))
        answer_text = _strip_html(answer.get("body", ""))
        combined = f"سؤال: {q.get('title', '')}\n{question_text}\n\nالجواب:\n{answer_text}"

        ok, reason = run_quality_gate(combined, LICENSE, existing_texts)
        if not ok:
            report["quality_rejected"] += 1
            log_event("se_collector_rejections", {"question_id": q["question_id"], "reason": reason})
            continue

        inserted = insert_sample(
            sha256_of(combined), combined,
            source_url=q.get("link", ""), license_=LICENSE, language="text/qa",
            provenance={"site": site, "tag": tag, "question_id": q["question_id"], "score": q.get("score")},
            status="pending_review",
        )
        if inserted:
            report["stored"] += 1
            existing_texts.append(combined)
        else:
            report["duplicates_skipped"] += 1

        time.sleep(0.5)  # معدل تصفح محدود

    log_event("se_collector_runs", report)
    return report
