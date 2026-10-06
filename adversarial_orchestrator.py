import os, sys, json, time, asyncio
from pathlib import Path
from fastapi import FastAPI, Request, BackgroundTasks
from huggingface_hub import HfApi

# ─── استيراد البوابات الحقيقية كوحدات برمجية ────────────────────────────────
sys.path.append(str(Path(__file__).parent))
try:
    from gate_completeness_v2 import CompletenessGate
    from gate_truth_nvd import NVDTruthGate
    from reserved_eval_guard import ReservedEvaluationGuard
except ImportError as e:
    print(f"❌ فشل استيراد البوابات: {e}")
    print("تأكد من وجود gate_completeness_v2.py, gate_truth_nvd.py, reserved_eval_guard.py")
    sys.exit(1)

# ─── إعدادات البيئة ──────────────────────────────────────────────────────────
HF_TOKEN = os.environ.get("HF_TOKEN")
REPO_ID = "AbuYahyaAlalwi2/marsad-security-dataset-v1"
NVD_API_KEY = os.environ.get("NVD_API_KEY")
CHECKPOINT_FILE = Path("orchestrator_checkpoint.json")

app = FastAPI(title="Marsad Real Adversarial Orchestrator")

# ─── تهيئة البوابات والمنسق ─────────────────────────────────────────────────
completeness_gate = CompletenessGate()
nvd_gate = NVDTruthGate()
eval_guard = ReservedEvaluationGuard()
hf_api = HfApi(token=HF_TOKEN) if HF_TOKEN else None

# ─── بروتوكول الاستئناف الذاتي ──────────────────────────────────────────────
def load_checkpoint():
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE, 'r') as f:
            return json.load(f)
    return {"last_processed": 0, "active_cycles": []}

def save_checkpoint(state):
    with open(CHECKPOINT_FILE, 'w') as f:
        json.dump(state, f, indent=2)

checkpoint = load_checkpoint()

# ─── المعالجة المركزية الحقيقية ─────────────────────────────────────────────
async def process_real_unit(unit: dict, source: str):
    """تمرير الوحدة عبر البوابات الثلاث كدوال داخل الذاكرة"""
    
    # 1. بوابة الاكتمال (إلزامية لكل وحدة)
    is_complete, reason = completeness_gate.validate_unit(unit)
    if not is_complete:
        print(f"   ❌ رفض اكتمال [{source}]: {reason}")
        return False
    
    # 2. بوابة الحقيقة (للوحدات ذات CVE)
    cve_id = unit.get("cve_id", "").strip()
    if cve_id:
        is_verified, nvd_data = nvd_gate.verify_cve(cve_id)
        if not is_verified:
            print(f"   ❌ رفض حقيقة [{source}]: CVE غير مثبت {cve_id}")
            return False
        # دمج بيانات NVD المثبتة
        unit.update({
            "_truth_gate": "NVD_VERIFIED",
            "_nvd_cvss": nvd_data["cvss_score"],
            "_nvd_published": nvd_data["published_date"]
        })
    else:
        unit["_truth_gate"] = "SANDBOX_NO_CVE"
    
    # 3. مجموعة التقييم المحجوزة (حجز 12% تلقائياً)
    if eval_guard.reserve_sample(unit, source):
        print(f"   🔒 حجز للتقييم [{source}]")
        return True  # محجوز بنجاح
    
    # 4. الرفع المباشر لـ Hugging Face (للبيانات الجاهزة للتدريب)
    if hf_api:
        try:
            content_line = json.dumps(unit, ensure_ascii=False) + "\n"
            hf_api.upload_file(
                path_or_fileobj=content_line.encode(),
                path_in_repo=f"data/{source}_training_ready.jsonl",
                repo_id=REPO_ID,
                repo_type="dataset"
            )
            print(f"   ✅ رفع تدريب [{source}] → HF")
        except Exception as e:
            print(f"   ️ فشل رفع HF [{source}]: {e}")
            return False
    
    return True

# ── نقاط الاستقبال الحقيقية ────────────────────────────────────────────────
@app.post("/api/ingest")
async def ingest_from_cf(request: Request):
    """استقبال بيانات حقيقية من وكلاء Cloudflare الـ 500K"""
    try:
        data = await request.json()
        if not data or "payload" not in data:
            return {"status": "rejected", "reason": "empty_payload"}, 400
        
        unit = {
            "timestamp": time.time(),
            "source": data.get("agent_id", "cf_worker"),
            "type": data.get("task_type", "unknown"),
            **data["payload"]  # دمج الحمولة الكاملة
        }
        
        success = await process_real_unit(unit, "cloudflare")
        checkpoint["last_processed"] += 1
        save_checkpoint(checkpoint)
        
        return {"status": "accepted" if success else "filtered"}, 200
        
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500

@app.post("/api/ingest/github")
async def ingest_from_github(request: Request):
    """استقبال بيانات من وكلاء جمع GitHub الموثوقين"""
    try:
        data = await request.json()
        unit = {"source": "github_scraper", "type": "project_analysis", **data}
        success = await process_real_unit(unit, "github")
        return {"status": "accepted" if success else "filtered"}, 200
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500

@app.post("/api/ingest/sandbox")
async def ingest_from_sandbox(request: Request):
    """استقبال مخرجات سيناريوهات Sandbox الداخلية"""
    try:
        data = await request.json()
        unit = {"source": "internal_sandbox", "type": "adversarial_cycle", **data}
        success = await process_real_unit(unit, "sandbox")
        return {"status": "accepted" if success else "filtered"}, 200
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500

# ─── نقطة مراقبة الحالة ────────────────────────────────────────────────────
@app.get("/health")
async def health_check():
    return {
        "status": "operational",
        "checkpoint": checkpoint,
        "gates_loaded": True,
        "hf_connected": hf_api is not None
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    print(f"🚀 بدء المنسق المركزي الحقيقي على المنفذ {port}")
    print(f"   • بوابة الاكتمال: نشطة")
    print(f"   • بوابة الحقيقة (NVD): نشطة | مفتاح: {'✅' if NVD_API_KEY else '❌'}")
    print(f"   • حارس التقييم المحجوز: نشط")
    print(f"   • نقاط الاستقبال: /api/ingest, /api/ingest/github, /api/ingest/sandbox")
    uvicorn.run(app, host="0.0.0.0", port=port)
