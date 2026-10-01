"""بناء مهام التحدي من CVEfixes: دوال نقية قابلة للاختبار.
أصلحت: (1) float('HIGH') كان يوقف البناء، (2) أول 300 صف قد تكون من فئة واحدة،
(3) لا قيمة افتراضية صامتة للخطورة، (4) فصل ثابت لمجموعة تقييم محجوزة."""
import hashlib
import re

SEVERITY_WORDS = {"LOW": 2.0, "MEDIUM": 5.0, "MODERATE": 5.0, "HIGH": 8.0, "CRITICAL": 9.5}
CVSS_COLUMNS = ("cvss3_base_score", "cvss2_base_score", "cvss", "severity")


def parse_cvss(row):
    """يعيد (الدرجة 0..10، اسم العمود) أو None إن لم تتوفر خطورة موثوقة."""
    for col in CVSS_COLUMNS:
        v = row.get(col)
        if v is None or v == "":
            continue
        try:
            f = float(v)
            if 0.0 <= f <= 10.0:
                return f, col
        except (TypeError, ValueError):
            w = str(v).strip().upper()
            if w in SEVERITY_WORDS:
                return SEVERITY_WORDS[w], col
    return None


def split_for(cve, eval_ratio=5):
    """كل CVE يقع دائماً في نفس المجموعة (1 من كل 5 للتقييم): لا تسرّب بين التدريب والتقييم."""
    return "eval" if int(hashlib.sha256(cve.encode()).hexdigest(), 16) % eval_ratio == 0 else "train"


def build_tasks(rows, limit=300, max_code=5000):
    tasks, seen, stats = [], set(), {"skipped_no_cvss": 0, "skipped_bad": 0, "skipped_dup": 0}
    for row in rows:
        cve = str(row.get("cve_id") or "").strip().upper()
        before, after = str(row.get("code_before") or ""), str(row.get("code_after") or "")
        if not re.fullmatch(r"CVE-\d{4}-\d{4,}", cve) or not before.strip() or before.strip() == after.strip():
            stats["skipped_bad"] += 1
            continue
        if cve in seen:
            stats["skipped_dup"] += 1
            continue
        c = parse_cvss(row)
        if c is None:
            stats["skipped_no_cvss"] += 1
            continue
        seen.add(cve)
        tasks.append({"id": f"cve-{cve}", "cve": cve, "language": str(row.get("language") or ""),
                      "before": before[:max_code], "after": after[:max_code], "commit": str(row.get("hash") or ""),
                      "cvss": c[0], "cvss_column": c[1], "cwe": str(row.get("cwe_id") or "").strip().upper(),
                      "split": split_for(cve)})
        if len(tasks) >= limit:
            break
    stats["built"] = len(tasks)
    return tasks, stats
