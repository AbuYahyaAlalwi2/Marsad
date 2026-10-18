#!/usr/bin/env python3
"""وكيل حقن الأخطاء بالـLLM + خادم localhost. الـLLM يقترح فقط؛ القبول يقرّره المنقّب بالاختبارات الأصلية (بلا ثقة بالنموذج).
GET /health ; POST /inject {"function_src": "...", "file": "...", "seed": n} -> {"buggy_src": "...", "description": "..."}"""
import ast, json, re, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SYSTEM = ("You create realistic, subtle logic bugs for a DEFENSIVE bug-fixing dataset. "
          "Given ONE Python function, return JSON: {\"buggy_src\": <the whole function with exactly one small realistic logic bug>, "
          "\"description\": <one sentence describing the bug>}. Rules: keep the same name, signature and decorators; change behavior only "
          "(off-by-one, wrong comparison/boolean operator, missing edge case, swapped arguments, wrong default, missing None/empty check, wrong return value). "
          "No security payloads, no exploit code, no new imports, no comments revealing the bug. Output JSON only.")
BAD = re.compile(r"\b(os\.system|subprocess|eval\(|exec\(|__import__|socket|requests\.|urllib)\b")


def parse_reply(txt, func_src):
    """يُرجع (buggy_src, description) أو None إذا كان الرد غير صالح."""
    m = re.search(r"\{.*\}", txt, re.S)
    if not m:
        return None
    try:
        j = json.loads(m.group(0))
        b, desc = j["buggy_src"], str(j.get("description", ""))[:300]
    except Exception:
        return None
    if not isinstance(b, str) or len(b) > 20000 or BAD.search(b) and not BAD.search(func_src):
        return None
    try:
        t0, t1 = ast.parse(func_src.strip("\n")), ast.parse(b.strip("\n"))
        f0, f1 = t0.body[0], t1.body[0]
        if len(t1.body) != 1 or not isinstance(f1, type(f0)) or f0.name != f1.name:
            return None
        if ast.unparse(f0) == ast.unparse(f1):
            return None
    except Exception:
        return None
    return b, desc


def inject(gw, func_src, file="", seed=0):
    import textwrap
    src = textwrap.dedent(func_src)
    txt = gw.chat([{"role": "system", "content": SYSTEM}, {"role": "user", "content": f"File: {file}\n\n```python\n{src}\n```"}],
                  temperature=0.6 + 0.1 * (seed % 4), json_mode=True)
    return parse_reply(txt, src)


def serve(gw, port=0, host="127.0.0.1"):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass

        def _send(self, code, obj):
            b = json.dumps(obj).encode(); self.send_response(code); self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

        def do_GET(self):
            self._send(200, {"ok": gw.available(), "stats": gw.stats})

        def do_POST(self):
            try:
                n = int(self.headers.get("Content-Length", 0))
                if n > 100_000:
                    return self._send(413, {"error": "too large"})
                q = json.loads(self.rfile.read(n))
                r = inject(gw, q["function_src"], q.get("file", ""), int(q.get("seed", 0)))
                self._send(200, {"buggy_src": r[0], "description": r[1]} if r else {"error": "invalid"})
            except Exception as e:
                self._send(502, {"error": str(e)[:200]})
    srv = ThreadingHTTPServer((host, port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]
