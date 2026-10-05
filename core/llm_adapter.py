"""llm_adapter — يتحدث تلقائياً من HF عند فشل الاتصال."""
import json, os, socket, time, urllib.request
from pathlib import Path

HF_DATASET = "AbuYahya2/marsad-endpoints"
HF_FILE = "current.json"

def _read_hf_token():
    p = Path.home() / ".marsad_secrets" / "render.env"
    if not p.exists(): return os.environ.get("HF_TOKEN", "")
    for line in p.read_text().splitlines():
        if line.startswith("HUGGINGFACE_TOKEN="):
            return line.split("=", 1)[1].strip()
    return os.environ.get("HF_TOKEN", "")

def _fetch_remote_endpoint():
    tok = _read_hf_token()
    if not tok: return None
    url = f"https://huggingface.co/datasets/{HF_DATASET}/resolve/main/{HF_FILE}"
    try:
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {tok}"})
        with urllib.request.urlopen(req, timeout=15) as r:
            d = json.loads(r.read(2000))
            return d.get("url"), d.get("key"), d.get("model", "v2")
    except Exception:
        return None

class MarsadLLM:
    def __init__(self, base_url=None, api_key=None, model=None, timeout=180):
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key or ""
        self.model = model or "v2"
        self.timeout = timeout
        self._last_refresh = 0
        if not self.base_url:
            self._refresh_from_hf(force=True)

    def _refresh_from_hf(self, force=False):
        if not force and time.time() - self._last_refresh < 60:
            return False
        got = _fetch_remote_endpoint()
        if not got or not got[0]: return False
        self.base_url, self.api_key, self.model = got[0].rstrip("/"), got[1], got[2]
        self._last_refresh = time.time()
        return True

    def _post(self, path, body):
        url = self.base_url + path
        try:
            import httpx
            with httpx.Client(timeout=self.timeout, verify=False) as c:
                r = c.post(url, headers={"Authorization": f"Bearer {self.api_key}",
                                          "Content-Type": "application/json"}, json=body)
            return r.text, r.status_code
        except Exception as e:
            return f"[{type(e).__name__}: {str(e)[:150]}]", 0

    def chat(self, messages, max_tokens=1200, temperature=0.2, **kw):
        body = {"model": self.model, "messages": messages,
                "max_tokens": max_tokens, "temperature": temperature, **kw}
        text, code = self._post("/chat/completions", body)
        # إن فشل — جرّب تحديث URL من HF ثم أعد المحاولة
        if code != 200:
            if self._refresh_from_hf(force=True):
                text, code = self._post("/chat/completions", body)
        if code != 200:
            return {"content": "", "error": f"HTTP {code}: {text[:250]}"}
        try:
            d = json.loads(text)
            return {"content": d["choices"][0]["message"]["content"], "raw": d}
        except Exception as e:
            return {"content": "", "error": f"parse: {e}"}
