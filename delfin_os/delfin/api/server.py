"""الواجهة البرمجية الداخلية (الطبقة 10). مصادقة إلزامية، نطاقات، حد معدل، سجل تدقيق،
وربط محلي افتراضياً. لا تُظهر تتبّع الأخطاء للعميل."""
import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from ..core.errors import SecurityError
from ..security.layer import KIND_SCOPE, require_scope
from .dashboard import HTML

MAX_BODY = 64 * 1024


def make_handler(app, loop):
    sec = app.security

    class H(BaseHTTPRequestHandler):
        server_version = "Delfin"
        sys_version = ""

        def log_message(self, *a):
            pass

        def _send(self, code, obj, ctype="application/json; charset=utf-8", extra=None):
            body = obj.encode() if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False, default=str).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _run(self, coro, timeout=300):
            return asyncio.run_coroutine_threadsafe(coro, loop).result(timeout)

        def _auth(self):
            """المفتاح الصحيح لا يتأثر بمحاولات الآخرين الفاشلة (لا قفل عنوان: يمنع حجب الخدمة خلف وكيل)."""
            ip = self.client_address[0]
            h = self.headers.get("Authorization", "")
            info = sec.keys.verify(h[7:]) if h.startswith("Bearer ") else None
            if not info:
                if not sec.fail_limiter.allow(f"ip:{ip}"):
                    self._send(429, {"error": "محاولات فاشلة كثيرة"})
                    return None
                sec.audit.append(f"ip:{ip}", "auth_failed", self.path[:80])
                self._send(401, {"error": "غير مصرّح"})
                return None
            if sec.behavior.is_locked(info.id):
                self._send(403, {"error": "المفتاح مقفل مؤقتاً بسبب مخالفات متكررة"})
                return None
            if not sec.limiter.allow(f"key:{info.id}"):
                self._send(429, {"error": "تجاوزت حد المعدل"})
                return None
            return info

        def _body(self):
            n = int(self.headers.get("Content-Length") or 0)
            if n > MAX_BODY:
                raise SecurityError("الطلب كبير")
            try:
                d = json.loads(self.rfile.read(n) or b"{}")
            except ValueError:
                raise SecurityError("JSON غير صالح")
            if not isinstance(d, dict):
                raise SecurityError("الجسم يجب أن يكون كائناً")
            return d

        def _guard(self, fn):
            try:
                fn()
            except SecurityError as e:
                self._send(403, {"error": str(e)})
            except Exception:
                sec.audit.append("server", "internal_error", self.path[:80])
                self._send(500, {"error": "خطأ داخلي"})

        def do_GET(self):
            self._guard(self._get)

        def do_POST(self):
            self._guard(self._post)

        def _get(self):
            u = urlsplit(self.path)
            if u.path == "/dashboard":
                return self._send(200, HTML, "text/html; charset=utf-8", {
                    "Content-Security-Policy": "default-src 'none'; script-src 'unsafe-inline'; "
                                               "style-src 'unsafe-inline'; connect-src 'self'"})
            info = self._auth()
            if not info:
                return
            q = parse_qs(u.query)
            if u.path == "/api/health":
                require_scope(info, "read")
                ok, n = sec.audit.verify()
                return self._send(200, {"state": app.state.get_system("state"), "agents": app.state.agents(),
                                        "tasks": app.state.counts(), "audit_ok": ok,
                                        "maintenance": app.safety.maintenance,
                                        "constraints_tampered": app.safety.store.tampered})
            if u.path == "/api/personas":
                require_scope(info, "read")
                return self._send(200, app.personas.names())
            if u.path == "/api/sessions":
                require_scope(info, "chat")
                return self._send(200, app.memory.list_sessions(info.id))
            if u.path == "/api/tasks":
                require_scope(info, "read")
                lim = int((q.get("limit") or ["50"])[0])
                owner = None if "admin" in info.scopes else info.id
                return self._send(200, app.state.list_tasks(lim, owner))
            if u.path.startswith("/api/tasks/"):
                require_scope(info, "read")
                owner = None if "admin" in info.scopes else info.id
                t = app.state.get_task(u.path.rsplit("/", 1)[1], owner)
                return self._send(200 if t else 404, t or {"error": "غير موجود"})
            if u.path == "/api/usage":
                require_scope(info, "read")
                return self._send(200, app.tokens.report(info.id))
            if u.path == "/api/audit/verify":
                require_scope(info, "admin")
                ok, n = sec.audit.verify()
                return self._send(200, {"ok": ok, "entries": n})
            self._send(404, {"error": "غير موجود"})

        def _post(self):
            u = urlsplit(self.path)
            info = self._auth()
            if not info:
                return
            d = self._body()
            if u.path == "/api/sessions":
                require_scope(info, "chat")
                persona = d.get("persona", "assistant")
                app.personas.get(persona)
                return self._send(201, {"session": app.memory.create_session(info.id, persona)})
            if u.path == "/api/chat":
                require_scope(info, "chat")
                r = self._run(app.orchestrator.submit("chat", {"session": d.get("session", ""),
                                                               "message": d.get("message", ""),
                                                               "persona": d.get("persona")}, info.id))
                return self._send(200 if r["status"] == "done" else 422, r)
            if u.path == "/api/tasks":
                kind = d.get("kind")
                if kind == "goal":
                    require_scope(info, "tasks")
                    return self._send(200, self._run(app.orchestrator.run_goal(str(d.get("goal", ""))[:2000], info.id)))
                if kind not in KIND_SCOPE:
                    raise SecurityError("نوع مهمة غير معروف")
                require_scope(info, KIND_SCOPE[kind])
                payload = d.get("payload", {})
                r = self._run(app.orchestrator.submit(kind, payload if isinstance(payload, dict) else {}, info.id))
                return self._send(200 if r["status"] == "done" else 422, r)
            if u.path == "/api/safety/unlock":
                require_scope(info, "admin")
                app.security.behavior.unlock(str(d.get("owner", "")))
                sec.audit.append(info.id, "unlock", str(d.get("owner", ""))[:40])
                return self._send(200, {"ok": True})
            self._send(404, {"error": "غير موجود"})

    return H


def serve(app, host="127.0.0.1", port=8787):
    loop = asyncio.new_event_loop()
    started = threading.Event()

    def run():
        asyncio.set_event_loop(loop)
        loop.run_until_complete(app.orchestrator.start())
        started.set()
        loop.run_forever()

    threading.Thread(target=run, daemon=True).start()
    started.wait()
    srv = ThreadingHTTPServer((host, port), make_handler(app, loop))
    srv.timeout = 1
    return srv, loop
