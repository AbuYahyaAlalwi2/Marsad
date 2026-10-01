"""وكيل الملفات: محصور في مساحة العمل، ويمنع المسارات الحساسة ومرور الروابط الرمزية."""
import os

from ..core.errors import SecurityError
from .base import Agent


class FileManagerAgent(Agent):
    name = "filemanager"
    MAX_READ, MAX_WRITE = 1_000_000, 200_000

    def __init__(self, root, paths, scanner):
        os.makedirs(root, exist_ok=True)
        self.root, self.paths, self.scanner = os.path.realpath(root), paths, scanner

    def _resolve(self, rel):
        norm = self.paths.check(rel)
        target = os.path.realpath(os.path.join(self.root, norm))
        if os.path.commonpath([self.root, target]) != self.root:
            raise SecurityError("المسار خارج مساحة العمل")
        return target

    async def handle(self, kind, payload, ctx):
        op = payload.get("op")
        if op == "list":
            d = self.root if payload.get("path") in (None, "", ".") else self._resolve(payload["path"])
            return {"entries": sorted(e for e in os.listdir(d) if not e.startswith("."))[:200]}
        if op == "read":
            p = self._resolve(payload.get("path", ""))
            with open(p, "rb") as f:
                data = f.read(self.MAX_READ + 1)
            if len(data) > self.MAX_READ:
                raise SecurityError("الملف أكبر من الحد")
            return {"content": self.scanner.redact(data.decode("utf-8", "replace"))}
        if op == "write":
            content = str(payload.get("content", ""))
            if len(content.encode()) > self.MAX_WRITE:
                raise SecurityError("المحتوى أكبر من الحد")
            if self.scanner.find(content):
                raise SecurityError("المحتوى يحمل سراً")
            p = self._resolve(payload.get("path", ""))
            if os.path.islink(p):
                raise SecurityError("الكتابة فوق رابط رمزي ممنوعة")
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                f.write(content)
            return {"written": len(content)}
        if op == "search":
            q, hits = str(payload.get("query", ""))[:100], []
            if not q:
                raise SecurityError("استعلام فارغ")
            for dp, dn, fn in os.walk(self.root):
                dn[:] = [d for d in dn if not d.startswith(".")]
                for n in fn:
                    fp = os.path.join(dp, n)
                    rel = os.path.relpath(fp, self.root)
                    try:
                        self.paths.check(rel)
                        if os.path.islink(fp) or os.path.getsize(fp) > self.MAX_READ:
                            continue
                        if q in open(fp, encoding="utf-8", errors="replace").read():
                            hits.append(rel)
                    except (SecurityError, OSError):
                        continue
            return {"matches": hits[:50]}
        raise SecurityError("عملية ملفات غير معروفة")
