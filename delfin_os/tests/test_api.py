import json, tempfile, threading, unittest, urllib.error, urllib.request
from delfin.agents.llm import FakeLLM
from delfin.api.server import serve
from delfin.app import build_app


class API(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = build_app(tempfile.mkdtemp(), llm=FakeLLM(lambda m: "أهلاً بك"))
        cls.srv, cls.loop = serve(cls.app, "127.0.0.1", 0)
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        k = cls.app.security.keys
        cls.admin = k.issue("admin", {"admin"})[1]
        cls.user1 = k.issue("u1", {"chat", "read"})[1]
        cls.user2 = k.issue("u2", {"chat", "read"})[1]
        cls.ro = k.issue("ro", {"read"})[1]

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        import asyncio
        asyncio.run_coroutine_threadsafe(cls.app.orchestrator.stop(), cls.loop).result(5)
        cls.loop.call_soon_threadsafe(cls.loop.stop)

    def call(self, method, path, key=None, body=None, raw=None):
        h = {"Content-Type": "application/json"}
        if key:
            h["Authorization"] = f"Bearer {key}"
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        req = urllib.request.Request(self.base + path, data=data, headers=h, method=method)
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.status, r.read().decode(), r.headers
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode(), e.headers

    def test_dashboard_public_without_data(self):
        st, body, h = self.call("GET", "/dashboard")
        self.assertEqual(st, 200)
        self.assertIn("default-src 'none'", h["Content-Security-Policy"])
        self.assertEqual(h["X-Content-Type-Options"], "nosniff")
        self.assertNotIn("dlf_", body)

    def test_auth_required(self):
        for path in ["/api/health", "/api/tasks", "/api/personas", "/api/usage"]:
            self.assertEqual(self.call("GET", path)[0], 401, path)
        self.assertEqual(self.call("GET", "/api/health", "dlf_deadbeef_" + "x" * 32)[0], 401)
        self.assertEqual(self.call("POST", "/api/chat", None, {})[0], 401)

    def test_scopes(self):
        self.assertEqual(self.call("POST", "/api/sessions", self.ro, {})[0], 403)
        self.assertEqual(self.call("GET", "/api/audit/verify", self.user1)[0], 403)
        self.assertEqual(self.call("POST", "/api/tasks", self.user1, {"kind": "github", "payload": {}})[0], 403)
        self.assertEqual(self.call("POST", "/api/tasks", self.user1, {"kind": "code", "payload": {}})[0], 403)
        self.assertEqual(self.call("POST", "/api/safety/unlock", self.user1, {"owner": "x"})[0], 403)

    def test_chat_and_tenancy(self):
        st, body, _ = self.call("POST", "/api/sessions", self.user1, {"persona": "support"})
        sid = json.loads(body)["session"]
        st, body, _ = self.call("POST", "/api/chat", self.user1, {"session": sid, "message": "مرحبا"})
        self.assertEqual(st, 200)
        self.assertEqual(json.loads(body)["result"]["reply"], "أهلاً بك")
        st, body, _ = self.call("POST", "/api/chat", self.user2, {"session": sid, "message": "مرحبا"})
        self.assertEqual(st, 422)                                                  # جلسة غيرك: مرفوض
        self.assertEqual(json.loads(self.call("GET", "/api/sessions", self.user2)[1]), [])
        t1 = json.loads(self.call("GET", "/api/tasks", self.user1)[1])
        self.assertTrue(all(t["owner"] != "x" for t in t1))
        tid = t1[0]["id"]
        self.assertEqual(self.call("GET", f"/api/tasks/{tid}", self.user2)[0], 404)  # مهمة غيرك: غير موجودة
        self.assertEqual(self.call("GET", f"/api/tasks/{tid}", self.admin)[0], 200)

    def test_input_hardening(self):
        self.assertEqual(self.call("POST", "/api/sessions", self.user1, raw=b"{bad")[0], 403)
        self.assertEqual(self.call("POST", "/api/sessions", self.user1, raw=b"[1,2]")[0], 403)
        self.assertEqual(self.call("POST", "/api/sessions", self.user1, raw=b"x" * 70000)[0], 403)
        self.assertEqual(self.call("GET", "/nope", self.admin)[0], 404)
        self.assertEqual(self.call("POST", "/api/sessions", self.user1, {"persona": "root"})[0], 500)

    def test_audit_and_health(self):
        st, body, _ = self.call("GET", "/api/audit/verify", self.admin)
        self.assertTrue(json.loads(body)["ok"])
        h = json.loads(self.call("GET", "/api/health", self.ro)[1])
        self.assertTrue(h["audit_ok"])
        self.assertFalse(h["constraints_tampered"])

    def test_zz_failed_auth_throttled_but_valid_key_unaffected(self):
        codes = [self.call("GET", "/api/health", "dlf_deadbeef_" + "x" * 32)[0] for _ in range(25)]
        self.assertIn(429, codes)                                                  # المحاولات الفاشلة تُخنق
        self.assertEqual(self.call("GET", "/api/health", self.admin)[0], 200)      # والمفتاح الصحيح يعمل

    def test_zz_key_lock_after_violations(self):
        k = self.app.security.keys.issue("bad", {"tasks", "read"})
        key, kid = k[1], k[0]
        for _ in range(6):
            self.call("POST", "/api/tasks", key, {"kind": "code", "payload": {"task": "rm -rf /"}})
        self.assertEqual(self.call("GET", "/api/health", key)[0], 403)             # المخالف وحده يُقفل
        self.assertEqual(self.call("GET", "/api/health", self.admin)[0], 200)
        self.app.security.behavior.unlock(kid)
        self.assertEqual(self.call("GET", "/api/health", key)[0], 200)


if __name__ == "__main__":
    unittest.main()
