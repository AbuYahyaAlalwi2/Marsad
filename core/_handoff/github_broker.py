"""وسيط GitHub (الطبقة 8): يقترح تغييرات عبر Pull Request فقط.
- لا توجد دالة دمج ولا دفع إلى main ولا حذف: غيابها هو الحماية.
- الفروع تبدأ بـ agent/ فقط، والمسارات الحساسة ممنوعة، والأسرار تُرفض.
- التوكن قصير العمر يولَّد هنا ولا يراه النموذج.
غير مُجرَّب على GitHub الحقيقي؛ مُختبر بنقل وهمي فقط."""
import asyncio
import base64
import json
import re
import subprocess
import time
import urllib.error
import urllib.request
from urllib.parse import quote

from security_core import SecurityError
try:
    from agents_base import Agent
except ImportError:
    class Agent:
        name = "base"

BRANCH_RE = re.compile(r"^agent/[a-z0-9][a-z0-9._-]{0,60}(/[a-z0-9][a-z0-9._-]{0,60}){0,2}$")
API = "https://api.github.com"


def default_transport(method, path, headers, body=None):
    if not path.startswith("/"):
        raise SecurityError("مسار API غير صالح")
    req = urllib.request.Request(API + path, method=method, headers=headers,
                                 data=None if body is None else json.dumps(body).encode())
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read(2_000_000) or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read(200_000) or b"{}")
        except ValueError:
            return e.code, {}


def _b64(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


class GitHubAppAuth:
    """توكن تثبيت قصير العمر عبر GitHub App (توقيع RS256 بـ openssl)."""

    def __init__(self, app_id, installation_id, key_path, transport=default_transport, clock=time.time):
        self.app_id, self.inst, self.key_path = str(app_id), str(installation_id), key_path
        self.transport, self.clock = transport, clock
        self._tok, self._exp = None, 0

    def _jwt(self):
        now = int(self.clock())
        h = _b64(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
        p = _b64(json.dumps({"iat": now - 30, "exp": now + 540, "iss": self.app_id}).encode())
        sig = subprocess.run(["openssl", "dgst", "-sha256", "-sign", self.key_path],
                             input=f"{h}.{p}".encode(), capture_output=True, check=True).stdout
        return f"{h}.{p}.{_b64(sig)}"

    def __call__(self):
        if self._tok and self.clock() < self._exp - 60:
            return self._tok
        st, d = self.transport("POST", f"/app/installations/{self.inst}/access_tokens",
                               {"Authorization": f"Bearer {self._jwt()}", "Accept": "application/vnd.github+json"}, None)
        if st != 201 or "token" not in d:
            raise RuntimeError("تعذر الحصول على توكن التثبيت")
        self._tok, self._exp = d["token"], self.clock() + 3000
        return self._tok


class GitHubBroker:
    def __init__(self, owner, repo, token_provider, paths, scanner, gate,
                 transport=default_transport, base="main", max_files=10, max_bytes=100_000):
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", owner) or not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", repo):
            raise SecurityError("اسم المستودع غير صالح")
        self.owner, self.repo, self.tp = owner, repo, token_provider
        self.paths, self.scanner, self.gate, self.tx = paths, scanner, gate, transport
        self.base, self.max_files, self.max_bytes = base, max_files, max_bytes

    def _call(self, method, sub, body=None):
        headers = {"Authorization": f"Bearer {self.tp()}", "Accept": "application/vnd.github+json",
                   "User-Agent": "delfin-broker"}
        return self.tx(method, f"/repos/{self.owner}/{self.repo}{sub}", headers, body)

    def _validate(self, suffix, files, title, body):
        branch = f"agent/{suffix}"
        if not BRANCH_RE.fullmatch(branch):
            raise SecurityError("اسم الفرع غير مسموح")
        if not isinstance(files, list) or not files or len(files) > self.max_files:
            raise SecurityError("عدد الملفات غير مسموح")
        clean = []
        for f in files:
            path = self.paths.check(f.get("path", ""))
            content = f.get("content")
            if not isinstance(content, str) or len(content.encode()) > self.max_bytes:
                raise SecurityError("محتوى ملف غير صالح أو كبير")
            issues = self.gate.check_repo_file(path, content)
            bad = self.gate.blocking(issues)
            if bad:
                raise SecurityError(f"رُفض {path}: {bad[0][1]}")
            clean.append((path, content))
        for t in (title, body):
            if self.scanner.find(t or ""):
                raise SecurityError("العنوان أو الوصف يحمل سراً")
        return branch, clean

    def propose_change(self, suffix, files, title, body=""):
        branch, clean = self._validate(suffix, files, title, body)
        st, ref = self._call("GET", f"/git/ref/heads/{self.base}")
        if st != 200:
            raise RuntimeError(f"تعذر قراءة {self.base}")
        st, _ = self._call("POST", "/git/refs", {"ref": f"refs/heads/{branch}", "sha": ref["object"]["sha"]})
        if st not in (200, 201):
            raise RuntimeError("تعذر إنشاء الفرع")
        for path, content in clean:
            q = quote(path)
            st, cur = self._call("GET", f"/contents/{q}?ref={quote(branch)}")
            payload = {"message": f"[agent] {title}"[:200], "branch": branch,
                       "content": base64.b64encode(content.encode()).decode()}
            if st == 200 and "sha" in cur:
                payload["sha"] = cur["sha"]
            st, _ = self._call("PUT", f"/contents/{q}", payload)
            if st not in (200, 201):
                raise RuntimeError(f"تعذر كتابة {path}")
        st, pr = self._call("POST", "/pulls", {"title": f"[agent] {title}"[:200], "head": branch,
                                               "base": self.base, "body": (body or "")[:4000]})
        if st != 201:
            raise RuntimeError("تعذر فتح طلب الدمج")
        return {"pr_url": pr.get("html_url"), "branch": branch, "files": [p for p, _ in clean]}


class GitHubAgent(Agent):
    name = "github"

    def __init__(self, broker):
        self.broker = broker

    async def handle(self, kind, payload, ctx):
        if payload.get("op") != "propose_pr":
            raise SecurityError("العملية الوحيدة المسموحة: propose_pr")
        return await asyncio.to_thread(self.broker.propose_change, str(payload.get("branch", "")),
                                       payload.get("files", []), str(payload.get("title", ""))[:150],
                                       str(payload.get("body", "")))
