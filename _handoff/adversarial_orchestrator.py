"""المنسق — غلاف HTTP رفيع فوق marsad_ingest_core.py حصراً. لا بوابات مكررة هنا.

إصلاحان حرجان عن النسخة السابقة التي أُرسلت:
1. HF upload كان يستبدل الملف بالكامل بكل عيّنة (محو تراكمي). هنا: تجميع محلي بالإلحاق
   (append) في ملف JSONL، ثم رفع الملف الكامل المتراكم — لا سطر واحد في كل مرة.
   (رفع كل سطر فردياً إلى HF على كل طلب مكلف وبطيء مهما كان الإصلاح؛ التجميع ثم الرفع
   الدوري هو الصحيح هندسياً، ويُترك مُشغِّل الرفع الفعلي لـ background task منفصل).
2. FastAPI لا يقبل إرجاع (body, status_code) كـ tuple من Flask — يُسلسَل كمصفوفة JSON
   خاطئة. الإصلاح: JSONResponse أو status_code في raise HTTPException.
"""
import json
import os
import threading
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from eval_quarantine import EvalQuarantine
from failure_library import FailureLibrary
from marsad_ingest_core import process_unit

DATA_DIR = Path(os.environ.get("MARSAD_DATA_DIR", "./marsad_data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
NVD_API_KEY = os.environ.get("NVD_API_KEY")  # يُستخدم فقط عبر nvd_fetch الحقيقي، لا يُطبع أبداً

app = FastAPI(title="Marsad Adversarial Orchestrator")
quarantine = EvalQuarantine(str(DATA_DIR / "eval_quarantine.jsonl"))
failures = FailureLibrary(str(DATA_DIR / "failures.jsonl"))
_write_lock = threading.Lock()


def _append_accepted(unit, source):
    """إلحاق حقيقي، لا استبدال. ملف محلي واحد متراكم لكل مصدر؛ رفعه لـ HF مهمة دورية
    منفصلة (خارج نطاق هذا الملف، كي لا يُبطئ كل طلب وارد باتصال شبكي)."""
    path = DATA_DIR / f"{source}_training_ready.jsonl"
    with _write_lock, open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(unit, ensure_ascii=False) + "\n")


def _append_quarantined(unit, source):
    path = DATA_DIR / f"{source}_quarantine.jsonl"
    with _write_lock, open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(unit, ensure_ascii=False) + "\n")


def _nvd_fetch(cve_id):
    import urllib.request
    url = f"https://services.nvd.nist.gov/rest/json/cves/2.0?cveId={cve_id}"
    headers = {"User-Agent": "marsad-orchestrator/1.0"}
    if NVD_API_KEY:
        headers["apiKey"] = NVD_API_KEY
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


async def _handle(request: Request, source: str, extra=None):
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="JSON غير صالح")
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="الجسم يجب أن يكون كائناً")
    unit = {"timestamp": time.time(), **(extra or {}), **data}
    status, detail = process_unit(unit, source, quarantine, failures, nvd_fetch=_nvd_fetch)
    if status == "accepted":
        _append_accepted(unit, source)
    elif status == "quarantined":
        _append_quarantined(unit, source)
    code = 200 if status in ("accepted", "quarantined") else 422
    return JSONResponse({"status": status, "detail": detail}, status_code=code)


@app.post("/api/ingest")
async def ingest_cf(request: Request):
    return await _handle(request, "cloudflare")


@app.post("/api/ingest/github")
async def ingest_github(request: Request):
    return await _handle(request, "github")


@app.post("/api/ingest/sandbox")
async def ingest_sandbox(request: Request):
    return await _handle(request, "sandbox")


@app.get("/health")
async def health():
    return {"status": "operational", "nvd_key_set": bool(NVD_API_KEY),
           "data_dir": str(DATA_DIR)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
