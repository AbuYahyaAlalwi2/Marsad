"""
بوابة الجودة — تطبّق بنود 18 و23-25 من دستور النظام:
كشف أسرار حقيقي (entropy + regex)، حجب PII، تحقق ترخيص، رفض التكرار
شبه المطابق، وفلتر جودة لغوية بسيط.
كل دالة تُرجع (مقبول: bool, سبب الرفض إن وُجد: str|None).
"""

import re
import math
import hashlib
from collections import Counter

# ---------------------------------------------------------------
# 1) كشف الأسرار — regex لأنماط معروفة + إنتروبيا للسلاسل المشبوهة
# ---------------------------------------------------------------
SECRET_PATTERNS = [
    r"AKIA[0-9A-Z]{16}",                      # AWS Access Key
    r"AIza[0-9A-Za-z\-_]{35}",                # Google API Key
    r"sk-[a-zA-Z0-9]{20,}",                   # OpenAI-style secret key
    r"ghp_[0-9A-Za-z]{36}",                   # GitHub personal token
    r"eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+",  # JWT
    r"-----BEGIN (RSA|EC|OPENSSH|DSA) PRIVATE KEY-----",
]
_SECRET_RE = re.compile("|".join(SECRET_PATTERNS))
_KEYWORD_RE = re.compile(r"(password|secret[_-]?key|private[_-]?key|access[_-]?token)\s*[:=]", re.I)


def _shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    counts = Counter(s)
    length = len(s)
    return -sum((c / length) * math.log2(c / length) for c in counts.values())


def contains_secret(text: str) -> bool:
    if _SECRET_RE.search(text) or _KEYWORD_RE.search(text):
        return True
    # فحص إنتروبيا على أي سلسلة متصلة طولها > 20 حرف بدون فراغات
    for token in re.findall(r"[A-Za-z0-9+/=_\-]{20,}", text):
        if _shannon_entropy(token) > 4.0:
            return True
    return False


# ---------------------------------------------------------------
# 2) كشف PII بسيط
# ---------------------------------------------------------------
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(r"(?:\+?9665|05)\d{8}\b")  # نمط جوال سعودي مبسّط
_SAUDI_ID_RE = re.compile(r"\b[12]\d{9}\b")       # نمط هوية/إقامة مبسّط


def contains_pii(text: str) -> bool:
    return bool(_EMAIL_RE.search(text) or _PHONE_RE.search(text) or _SAUDI_ID_RE.search(text))


# ---------------------------------------------------------------
# 3) الترخيص — allowlist صريحة، الافتراضي رفض
# ---------------------------------------------------------------
ALLOWED_LICENSES = {"mit", "apache-2.0", "bsd-2-clause", "bsd-3-clause", "cc0-1.0", "cc-by-4.0"}


def license_allowed(license_str: str | None) -> bool:
    if not license_str:
        return False  # لا ترخيص معروف → رفض افتراضي (بند 1 من الدستور)
    return license_str.strip().lower() in ALLOWED_LICENSES


# ---------------------------------------------------------------
# 4) دمج التطابق الحرفي (SHA-256) + تشابه شبه مطابق مبسّط (Jaccard على shingles)
# ---------------------------------------------------------------
def sha256_of(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def _shingles(text: str, k: int = 5) -> set:
    words = text.split()
    return {" ".join(words[i:i + k]) for i in range(max(0, len(words) - k + 1))}


def near_duplicate(text_a: str, text_b: str, threshold: float = 0.85) -> bool:
    """تقريب خفيف الوزن للتشابه شبه المطابق. لأحجام أكبر، استبدل بـ MinHash (datasketch)."""
    sa, sb = _shingles(text_a), _shingles(text_b)
    if not sa or not sb:
        return False
    inter = len(sa & sb)
    union = len(sa | sb)
    return (inter / union) >= threshold if union else False


# ---------------------------------------------------------------
# 5) فلتر جودة بسيط (طول أدنى + نسبة أحرف قابلة للطباعة)
# ---------------------------------------------------------------
def basic_quality_ok(text: str, min_len: int = 20) -> bool:
    if len(text.strip()) < min_len:
        return False
    printable_ratio = sum(1 for c in text if c.isprintable()) / max(1, len(text))
    return printable_ratio > 0.9


# ---------------------------------------------------------------
# نقطة الدخول الموحّدة — بوابة الجودة النهائية (بند 23)
# ---------------------------------------------------------------
def run_quality_gate(text: str, license_str: str | None, existing_samples: list[str] | None = None) -> tuple[bool, str | None]:
    if not basic_quality_ok(text):
        return False, "quality_too_short_or_garbled"
    if contains_secret(text):
        return False, "possible_secret_detected"
    if contains_pii(text):
        return False, "pii_detected"
    if not license_allowed(license_str):
        return False, "license_missing_or_disallowed"
    for existing in (existing_samples or []):
        if near_duplicate(text, existing):
            return False, "near_duplicate"
    return True, None
