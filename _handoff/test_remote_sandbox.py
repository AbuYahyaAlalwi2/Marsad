"""اختبار RemoteSandbox ضد خادم وهمي يطابق سلوك src/server.ts الفعلي (Deno) حرفياً."""
import json, threading, unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import sandbox_client as sx

TOKEN = "test-sandbox-token-123"


class Mock(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _send(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path == "/health":
            return self._send(200, {"status": "ok", "running": 0, "capacity": 4})
        self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/run":
            return self._send(404, {"error": "not found"})
        auth = self.headers.get("authorization", "")
        presented = auth[7:] if auth.startswith("Bearer ") else ""
        if presented != TOKEN:
            return self._send(401, {"error": "unauthorized"})
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n) or b"{}")
        if body.get("language") not in ("javascript", "typescript", "python"):
            return self._send(400, {"error": "language must be one of javascript, typescript, python"})
        code = body.get("code", "")
        if not isinstance(code, str) or not code:
            return self._send(400, {"error": "code is required"})
        if len(code) > 50000:
            return self._send(413, {"error": "code exceeds 50000 bytes"})
        replies = {
            "BUSY": (503, {"error": "sandbox is busy", "detail": "at most 4 runs at a time"}),
            "print(2+2)": (200, {"stdout": "4\n", "stderr": "", "exitCode": 0, "timedOut": False, "durationMs": 12}),
            "SLOW": (200, {"stdout": "", "stderr": "", "exitCode": 1, "timedOut": True, "durationMs": 10000}),
            "import os": (200, {"stdout": "", "stderr": "Traceback...\n", "exitCode": 1, "timedOut": False, "durationMs": 5}),
        }
        status, obj = replies.get(code, (200, {"stdout": "", "stderr": "", "exitCode": 0, "timedOut": False, "durationMs": 1}))
        self._send(status, obj)


class RemoteSandboxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), Mock)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def client(self, token=TOKEN):
        rs = sx.RemoteSandbox("https://placeholder", token)
        rs.url = f"http://127.0.0.1:{self.port}"   # الخادم الوهمي محلي بلا TLS
        return rs

    def test_rejects_http_and_empty_token(self):
        with self.assertRaises(ValueError):
            sx.RemoteSandbox("http://x", "t")
        with self.assertRaises(ValueError):
            sx.RemoteSandbox("https://x", "")

    def test_health(self):
        self.assertEqual(self.client().health(), {"status": "ok", "running": 0, "capacity": 4})

    def test_success(self):
        r = self.client().run_python("print(2+2)")
        self.assertEqual((r["status"], r["stdout"], r["exit"]), ("ok", "4\n", 0))

    def test_wrong_token(self):
        r = self.client("wrong").run_python("print(1)")
        self.assertEqual(r["status"], "refused")

    def test_busy(self):
        self.assertEqual(self.client().run_python("BUSY")["status"], "busy")

    def test_timeout(self):
        r = self.client().run_python("SLOW")
        self.assertEqual(r["status"], "timeout")

    def test_runtime_error(self):
        r = self.client().run_python("import os")
        self.assertEqual(r["status"], "error")
        self.assertIn("Traceback", r["stderr"])

    def test_unsupported_language(self):
        with self.assertRaises(ValueError):
            self.client()._call("ruby", "x", 5)

    def test_javascript_and_typescript_entrypoints(self):
        r1 = self.client().run_javascript("console.log(1)")
        r2 = self.client().run_typescript("console.log(1)")
        self.assertEqual((r1["status"], r2["status"]), ("ok", "ok"))


if __name__ == "__main__":
    unittest.main()
