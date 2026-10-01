"""طبقة الأمان (الطبقة 9): مفاتيح، أذونات، تحديد معدل، سجل مترابط،
فحص روابط ومسارات وأسرار، وتتبّع سلوك.

تنبيه صريح: كشف حقن التعليمات هنا استدلالي (heuristic) وضعيف بطبيعته،
والحماية الحقيقية تأتي من العزل والأذونات، وليس من هذا الكشف."""
import hashlib
import hmac
import ipaddress
import json
import os
import posixpath
import re
import secrets
import socket
import sqlite3
import threading
import time
import unicodedata
from collections import defaultdict, deque
from dataclasses import dataclass
from urllib.parse import urlsplit

from ..core.errors import SecurityError

# ───────────── كاشف الأسرار ─────────────
_SECRET_PATTERNS = {
    "github_token": re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
    "github_pat": re.compile(r"github_pat_[A-Za-z0-9_]{40,}"),
    "hf_token": re.compile(r"hf_[A-Za-z0-9]{30,}"),
    "api_key_sk": re.compile(r"sk-[A-Za-z0-9_\-]{20,}"),
    "aws_key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "private_key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "marsad_key": re.compile(r"marsad-[0-9a-f]{20,}"),
    "delfin_key": re.compile(r"dlf_[0-9a-f]{8}_[A-Za-z0-9_\-]{24,}"),
    "generic_assignment": re.compile(
        r"(?i)\b(api[_-]?key|secret|token|password|passwd)\b\s*[:=]\s*['\"]?[A-Za-z0-9_\-\.]{16,}"),
}


class SecretScanner:
    def find(self, text):
        text = text or ""
        return [n for n, p in _SECRET_PATTERNS.items() if p.search(text)]

    def redact(self, text):
        text = text or ""
        for n, p in _SECRET_PATTERNS.items():
            text = p.sub(f"[محجوب:{n}]", text)
        return text


# ───────────── مفاتيح API وأذونات ─────────────
SCOPES = {"chat", "tasks", "browser", "github", "read", "admin"}
KIND_SCOPE = {"chat": "chat", "plan": "tasks", "code": "tasks", "files": "tasks",
              "memory": "tasks", "review": "tasks", "browse": "browser", "github": "github"}


@dataclass
class KeyInfo:
    id: str
    name: str
    scopes: frozenset


class KeyStore:
    """المفتاح الخام يُعرض مرة واحدة فقط؛ نخزّن بصمته بملح."""

    def __init__(self, path):
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self._db.execute("CREATE TABLE IF NOT EXISTS keys(id TEXT PRIMARY KEY, name TEXT, salt TEXT, "
                             "hash TEXT, scopes TEXT, created REAL, revoked INTEGER DEFAULT 0)")
            self._db.commit()
        if path != ":memory:":
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass

    @staticmethod
    def _h(salt, raw):
        return hashlib.sha256((salt + raw).encode()).hexdigest()

    def issue(self, name, scopes):
        scopes = set(scopes)
        if not scopes or not scopes <= SCOPES:
            raise ValueError("نطاقات غير صالحة")
        kid, salt = secrets.token_hex(4), secrets.token_hex(8)
        raw = f"dlf_{kid}_{secrets.token_urlsafe(24)}"
        with self._lock:
            self._db.execute("INSERT INTO keys VALUES(?,?,?,?,?,?,0)",
                             (kid, name, salt, self._h(salt, raw), ",".join(sorted(scopes)), time.time()))
            self._db.commit()
        return kid, raw

    def verify(self, raw):
        m = re.fullmatch(r"dlf_([0-9a-f]{8})_[A-Za-z0-9_\-]{20,}", raw or "")
        if not m:
            return None
        with self._lock:
            row = self._db.execute("SELECT id,name,salt,hash,scopes,revoked FROM keys WHERE id=?",
                                   (m.group(1),)).fetchone()
        if not row or row[5]:
            return None
        if not hmac.compare_digest(self._h(row[2], raw), row[3]):
            return None
        return KeyInfo(row[0], row[1], frozenset(row[4].split(",")))

    def revoke(self, kid):
        with self._lock:
            cur = self._db.execute("UPDATE keys SET revoked=1 WHERE id=?", (kid,))
            self._db.commit()
            return cur.rowcount > 0

    def list(self):
        """المعرّفات والأسماء والنطاقات فقط؛ لا يوجد نص مفتاح يمكن عرضه."""
        with self._lock:
            rows = self._db.execute("SELECT id,name,scopes,created,revoked FROM keys ORDER BY created").fetchall()
        return [{"id": r[0], "name": r[1], "scopes": r[2].split(","), "created": r[3], "revoked": bool(r[4])}
                for r in rows]


def require_scope(info, needed):
    if needed not in info.scopes and "admin" not in info.scopes:
        raise SecurityError(f"الصلاحية المطلوبة غير ممنوحة: {needed}")


class RateLimiter:
    def __init__(self, per_minute=100, clock=time.monotonic):
        self.limit, self.clock = per_minute, clock
        self._hits = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key):
        with self._lock:
            now = self.clock()
            q = self._hits[key]
            while q and now - q[0] > 60:
                q.popleft()
            if len(q) >= self.limit:
                return False
            q.append(now)
            return True


# ───────────── سجل التدقيق المترابط ─────────────
class AuditLog:
    """كل سطر يحمل بصمة السطر السابق؛ أي تعديل أو حذف يُكتشف بالتحقق.
    هذا كشف تلاعب (tamper-evident) وليس منعاً؛ المنع الحقيقي يحتاج تخزيناً خارجياً للنسخة."""

    def __init__(self, path, redactor=lambda s: s):
        self.path, self._redact = path, redactor
        self._lock = threading.Lock()
        self._last = "0" * 64
        if os.path.exists(path):
            with open(path, "rb") as f:
                lines = f.read().splitlines()
            if lines:
                self._last = json.loads(lines[-1])["hash"]

    @staticmethod
    def _digest(entry):
        return hashlib.sha256(json.dumps(entry, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    def append(self, actor, action, detail=""):
        with self._lock:
            entry = {"ts": round(time.time(), 3), "actor": str(actor)[:40], "action": str(action)[:60],
                     "detail": self._redact(str(detail))[:500], "prev": self._last}
            entry["hash"] = self._digest(entry)
            fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
            try:
                os.write(fd, (json.dumps(entry, ensure_ascii=False) + "\n").encode())
            finally:
                os.close(fd)
            self._last = entry["hash"]

    def verify(self):
        prev, n = "0" * 64, 0
        if not os.path.exists(self.path):
            return True, 0
        with open(self.path, "rb") as f:
            for line in f.read().splitlines():
                try:
                    e = json.loads(line)
                except ValueError:
                    return False, n
                h = e.pop("hash", None)
                if e.get("prev") != prev or self._digest(e) != h:
                    return False, n
                prev, n = h, n + 1
        return True, n


# ───────────── التحقق من المدخلات ─────────────
_INJECTION = [re.compile(p, re.I) for p in [
    r"ignore (all |any )?(previous|prior|above) (instructions|rules)",
    r"disregard (your|the) (instructions|rules)",
    r"reveal (your )?(system )?prompt", r"you are now\b", r"\bDAN\b",
    r"تجاهل (كل )?(تعليماتك|التعليمات|القواعد)", r"انس(َ)? (كل )?(تعليماتك|القواعد)",
    r"(اكشف|اعرض|كرر).{0,20}(تعليمات النظام|البرومبت)", r"أنت الآن", r"بلا قيود",
]]


class InputValidator:
    def __init__(self, max_chars=8000):
        self.max_chars = max_chars

    def check(self, text):
        """يعيد (مقبول، أسباب_مشبوهة). المرفوض: فارغ/ضخم/يحوي بايت صفري.
        المشبوه لا يُرفض تلقائياً، لكن المهام ذات الأدوات ترفضه."""
        if not isinstance(text, str) or not text.strip():
            return False, ["نص فارغ"]
        if len(text) > self.max_chars:
            return False, ["نص أطول من الحد"]
        if "\x00" in text:
            return False, ["بايت صفري"]
        return True, [p.pattern[:30] for p in _INJECTION if p.search(text)]


# ───────────── فحص الروابط (منع SSRF) ─────────────
class LinkScanner:
    def __init__(self, allowed_domains=None, allowed_ports=(80, 443), resolver=None):
        self.allowed = [d.lower() for d in allowed_domains] if allowed_domains else None
        self.ports = set(allowed_ports)
        self.resolver = resolver or (lambda host, port: [
            ai[4][0] for ai in socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)])

    @staticmethod
    def _global(ip_str):
        ip = ipaddress.ip_address(ip_str.split("%")[0])
        if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
            ip = ip.ipv4_mapped
        return ip.is_global

    def check(self, url):
        """يعيد {'host','port','ips'} أو يرفع SecurityError."""
        if not isinstance(url, str) or len(url) > 2048 or any(c in url for c in "\x00\r\n \t"):
            raise SecurityError("رابط غير صالح")
        p = urlsplit(url)
        if p.scheme not in ("http", "https"):
            raise SecurityError("المخطط غير مسموح")
        if p.username or p.password or "@" in (p.netloc or ""):
            raise SecurityError("بيانات اعتماد داخل الرابط ممنوعة")
        host = (p.hostname or "").lower().rstrip(".")
        if not host:
            raise SecurityError("مضيف فارغ")
        try:
            port = p.port or (443 if p.scheme == "https" else 80)
        except ValueError:
            raise SecurityError("منفذ غير صالح")
        if port not in self.ports:
            raise SecurityError("المنفذ غير مسموح")
        if self.allowed is not None and not any(host == d or host.endswith("." + d) for d in self.allowed):
            raise SecurityError("النطاق خارج قائمة السماح")
        try:
            ipaddress.ip_address(host)
            ips = [host]                       # عنوان صريح: لا نثق بأي محلّل أسماء
        except ValueError:
            try:
                ips = self.resolver(host, port)
            except OSError:
                raise SecurityError("تعذر حل اسم المضيف")
        if not ips:
            raise SecurityError("لا عناوين")
        for ip in ips:
            try:
                ok = self._global(ip)
            except ValueError:
                ok = False
            if not ok:
                raise SecurityError("العنوان داخلي أو محجوز")
        return {"host": host, "port": port, "ips": list(ips), "scheme": p.scheme}


# ───────────── سياسة المسارات ─────────────
_PROTECTED_DIRS = {".git", ".github", "hidden_eval", "secrets", ".ssh"}
_PROTECTED_PREFIXES = ("delfin/security/", "delfin/sandbox/", "tests/containment")
_PROTECTED_NAMES = re.compile(r"(^\.env|\.pem$|\.key$|^id_rsa|^id_ed25519|credentials|\.p12$|\.pfx$)", re.I)


class PathPolicy:
    def check(self, path):
        """يعيد المسار المطبَّع أو يرفع SecurityError."""
        if not isinstance(path, str) or not path or "\x00" in path or len(path) > 300:
            raise SecurityError("مسار غير صالح")
        p = unicodedata.normalize("NFKC", path).replace("\\", "/")
        if p.startswith("/") or re.match(r"^[A-Za-z]:", p):
            raise SecurityError("المسار المطلق ممنوع")
        parts = p.split("/")
        if ".." in parts:
            raise SecurityError("الخروج من الجذر ممنوع")
        norm = posixpath.normpath(p)
        low = norm.lower()
        if low == "." or low.startswith("../"):
            raise SecurityError("مسار غير صالح")
        segs = low.split("/")
        if any(s in _PROTECTED_DIRS for s in segs[:-1]) or segs[0] in _PROTECTED_DIRS:
            raise SecurityError("مسار محمي")
        if any(low == x.rstrip("/") or low.startswith(x) for x in _PROTECTED_PREFIXES):
            raise SecurityError("مسار محمي")
        if _PROTECTED_NAMES.search(segs[-1]):
            raise SecurityError("ملف حساس")
        return norm


# ───────────── تتبّع السلوك ─────────────
class BehaviorTracker:
    """يقفل المالك مؤقتاً بعد كثرة الرفض خلال نافذة زمنية (مؤشر على استغلال)."""

    def __init__(self, threshold=5, window=300, clock=time.monotonic):
        self.threshold, self.window, self.clock = threshold, window, clock
        self._d = defaultdict(deque)
        self._locked = set()

    def record_denial(self, owner):
        now = self.clock()
        q = self._d[owner]
        q.append(now)
        while q and now - q[0] > self.window:
            q.popleft()
        if len(q) >= self.threshold:
            self._locked.add(owner)
        return owner in self._locked

    def is_locked(self, owner):
        return owner in self._locked

    def unlock(self, owner):
        self._locked.discard(owner)
        self._d.pop(owner, None)


class Security:
    """واجهة تجمع كل مكوّنات الطبقة."""

    def __init__(self, home, per_minute=100, allowed_domains=None, resolver=None):
        os.makedirs(home, mode=0o700, exist_ok=True)
        self.scanner = SecretScanner()
        self.keys = KeyStore(os.path.join(home, "keys.db"))
        self.limiter = RateLimiter(per_minute)
        self.fail_limiter = RateLimiter(20)      # المصادقات الفاشلة لكل عنوان
        self.audit = AuditLog(os.path.join(home, "audit.jsonl"), self.scanner.redact)
        self.validator = InputValidator()
        self.links = LinkScanner(allowed_domains, resolver=resolver)
        self.paths = PathPolicy()
        self.behavior = BehaviorTracker()
