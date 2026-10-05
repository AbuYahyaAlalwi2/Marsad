"""tool_calling.py — يجعل النموذج ينفذ، لا يدردش."""
from __future__ import annotations
import json, re, logging
from typing import Dict, Any, Callable, List
from pathlib import Path

logger = logging.getLogger(__name__)

TOOL_RE = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)


class ToolRegistry:
    """سجل الأدوات — يمكّن النموذج من التنفيذ."""
    def __init__(self):
        self._tools: Dict[str, Callable] = {}
        self._schemas: List[Dict] = []

    def register(self, name: str, schema: Dict, handler: Callable):
        self._tools[name] = handler
        self._schemas.append({"name": name, "schema": schema})

    def schemas(self) -> str:
        """يرجع وصف الأدوات كي يراها النموذج."""
        return json.dumps(self._schemas, ensure_ascii=False, indent=2)

    def execute(self, name: str, args: Dict) -> Any:
        if name not in self._tools:
            raise KeyError(f"Tool not found: {name}")
        return self._tools[name](**args)


registry = ToolRegistry()


# ─── الأدوات الأساسية ─────────────────────────────────────────
import os as _os
try:
    from core._handoff.sandbox_client import RemoteSandbox
    _tok_file = Path.home() / ".marsad_secrets" / "sandbox_token.txt"
    _token = _os.environ.get("MARSAD_SANDBOX_TOKEN", "")
    if not _token and _tok_file.exists():
        _token = _tok_file.read_text().strip()
    _sandbox = RemoteSandbox(
        "https://marsad-sandbox-production.up.railway.app", _token) if _token else None
except Exception:
    _sandbox = None


def _tool_run_python(code: str) -> Dict:
    """ينفذ Python في sandbox معزول (Deno+Pyodide على Railway)."""
    if _sandbox is None:
        return {"stdout": "", "stderr": "sandbox not configured",
                "returncode": -1, "isolated": False}
    r = _sandbox.run_python(code, timeout=10)
    return {
        "stdout": r.get("stdout", "")[:2000],
        "stderr": r.get("stderr", "")[:1000],
        "returncode": 0 if r.get("status") == "ok" else 1,
        "isolated": True,
    }


def _tool_run_shell(cmd: str) -> Dict:
    """معطل — sandbox بعيد لا يدعم shell، والتنفيذ المباشر خطر."""
    return {"stdout": "", "stderr": "run_shell disabled",
            "returncode": -1, "isolated": True}


def _tool_read_file(path: str) -> Dict:
    try:
        return {"content": Path(path).read_text()[:5000]}
    except Exception as e:
        return {"error": str(e)}


def _tool_write_file(path: str, content: str) -> Dict:
    try:
        Path(path).write_text(content); return {"status": "written"}
    except Exception as e:
        return {"error": str(e)}


def _tool_cve_lookup(cve: str = "", cve_id: str = "") -> Dict:
    from tools.cyber_senses import cve_lookup
    return cve_lookup(cve or cve_id)


def _tool_threat_summary(cve: str = "", cve_id: str = "") -> Dict:
    from tools.cyber_senses import threat_summary
    return threat_summary(cve or cve_id)


def _tool_gen_pdf(cve: str, client: str = "الفرقدان") -> Dict:
    from tools.cyber_senses import threat_summary
    from tools.report_pdf import build_vulnerability_report
    v = threat_summary(cve)
    p = build_vulnerability_report(v, client_name=client)
    return {"pdf": p, "size_kb": Path(p).stat().st_size // 1024}


def _tool_http_get(url: str) -> Dict:
    import httpx
    try:
        r = httpx.get(url, timeout=15, follow_redirects=True)
        return {"status": r.status_code, "body": r.text[:2000]}
    except Exception as e:
        return {"error": str(e)}


# ─── تسجيل كل الأدوات ─────────────────────────────────────────
registry.register("run_python", {
    "description": "ينفذ كود Python ويرجع stdout",
    "params": {"code": "string"}
}, _tool_run_python)

registry.register("run_shell", {
    "description": "ينفذ أمر bash",
    "params": {"cmd": "string"}
}, _tool_run_shell)

registry.register("read_file", {
    "description": "يقرأ ملف",
    "params": {"path": "string"}
}, _tool_read_file)

registry.register("write_file", {
    "description": "يكتب ملف",
    "params": {"path": "string", "content": "string"}
}, _tool_write_file)

registry.register("cve_lookup", {
    "description": "يجلب بيانات CVE من NVD",
    "params": {"cve": "string"}
}, _tool_cve_lookup)

registry.register("threat_summary", {
    "description": "ملخص كامل لثغرة (NVD + CISA + ExploitDB)",
    "params": {"cve": "string"}
}, _tool_threat_summary)

registry.register("generate_pdf_report", {
    "description": "يولّد تقرير PDF لثغرة",
    "params": {"cve": "string", "client": "string"}
}, _tool_gen_pdf)

registry.register("http_get", {
    "description": "يجلب صفحة ويب",
    "params": {"url": "string"}
}, _tool_http_get)


# ─── الحلقة الرئيسية ──────────────────────────────────────────
def parse_and_execute(model_output: str) -> List[Dict]:
    """يستخرج tool_calls من مخرجات النموذج وينفذها."""
    results = []
    for m in TOOL_RE.finditer(model_output):
        try:
            call = json.loads(m.group(1))
            name = call.get("name")
            args = call.get("arguments", {})
            print(f"🔧 executing: {name}({args})")
            result = registry.execute(name, args)
            results.append({"tool": name, "result": result})
        except Exception as e:
            results.append({"tool": "?", "error": str(e)})
    return results


SYSTEM_PROMPT = """أنت Marsad CyberAgent — نموذج سيبراني ينفذ ولا يدردش.

لديك هذه الأدوات:
{tools}

عندما تحتاج أداة، أخرج:
<tool_call>{{"name": "run_python", "arguments": {{"code": "print(2+2)"}}}}</tool_call>

ستستلم نتيجة الأداة في الرسالة التالية. أكمل بناءً عليها.
"""


def build_prompt(user_request: str) -> str:
    return SYSTEM_PROMPT.format(tools=registry.schemas()) + f"\n\n[طلب]\n{user_request}"


if __name__ == "__main__":
    print("Tools registered:", len(registry._tools))
    for t in registry._tools:
        print(f"  - {t}")

# ═══ verify_and_fix + ربط self_verify ═══
_default_llm = None

def set_llm_for_tools(llm):
    """يُستدعى من agent_loop مرة واحدة لتمرير النموذج الحقيقي."""
    global _default_llm
    _default_llm = llm

def _load_self_verify():
    for path in ("core._handoff.self_verify", "_handoff.self_verify", "self_verify"):
        try:
            return __import__(path, fromlist=["verify_and_fix"]).verify_and_fix
        except Exception:
            continue
    raise ImportError("self_verify not found in any known path")

class _LLMAdapter:
    def __init__(self, inner): self.inner = inner
    def chat(self, messages, max_tokens=1200, temperature=0.2):
        for m in ("chat", "generate", "complete", "invoke", "__call__"):
            fn = getattr(self.inner, m, None)
            if callable(fn):
                try:
                    r = fn(messages, max_tokens=max_tokens, temperature=temperature)
                except TypeError:
                    r = fn(messages)
                if isinstance(r, dict) and "content" in r:
                    return r
                return {"content": str(getattr(r, "content", r))}
        raise RuntimeError("LLM adapter: no callable method")

def _tool_verify_and_fix(task: str, language: str = "python", max_attempts: int = 3):
    if _sandbox is None:
        return {"ok": False, "error": "sandbox not configured"}
    if _default_llm is None:
        return {"ok": False, "error": "call set_llm_for_tools(llm) before using this tool"}
    vf = _load_self_verify()
    return vf(_LLMAdapter(_default_llm), _sandbox, task,
              language=language, max_attempts=max_attempts, timeout=15)

registry.register("verify_and_fix", {
    "description": "يولّد كوداً، ينفّذه في sandbox، ويصلحه ذاتياً حتى النجاح",
    "params": {"task": "string",
               "language": "python|javascript|typescript",
               "max_attempts": "int (افتراضي 3)"}
}, _tool_verify_and_fix)

registry._tools.pop("run_shell", None)
registry._schemas = [s for s in registry._schemas if s["name"] != "run_shell"]
