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
def _tool_run_python(code: str) -> Dict:
    import subprocess, sys
    r = subprocess.run([sys.executable, "-c", code],
                       capture_output=True, text=True, timeout=30)
    return {"stdout": r.stdout[:2000], "stderr": r.stderr[:1000],
            "returncode": r.returncode}


def _tool_run_shell(cmd: str) -> Dict:
    import subprocess
    r = subprocess.run(cmd, shell=True, capture_output=True,
                       text=True, timeout=30)
    return {"stdout": r.stdout[:2000], "stderr": r.stderr[:1000],
            "returncode": r.returncode}


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
