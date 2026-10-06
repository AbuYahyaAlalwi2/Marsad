import os, sys, json, time, hashlib
from pathlib import Path
from fastapi import FastAPI, Request
from huggingface_hub import HfApi

# ─── استيراد البوابات الموحدة من _handoff/ (لا تكرار) ────────────────────────
HANDOFF_DIR = Path(__file__).parent / "_handoff"
sys.path.insert(0, str(HANDOFF_DIR))

try:
    from completeness_gate import CompletenessGate
    from ground_truth_gate import GroundTruthGate
    from eval_quarantine import EvalQuarantine
except ImportError as e:
    print(f"❌ فشل استيراد البوابات الأصلية: {e}")
    sys.exit(1)

# ─── إعدادات البيئة الآمنة (قراءة من متغيرات Railway فقط) ────────────────────
HF_TOKEN = os.environ.get("HF_TOKEN")
NVD_API_KEY = os.environ.get("NVD_API_KEY")
REPO_ID = "AbuYahyaAlalwi2/marsad-security-dataset-v1"
CHECKPOINT_FILE = Path("orchestrator_checkpoint.json")

app = FastAPI(title="Marsad Unified Orchestrator")

# ─── تهيئة البوابات الأصلية ─────────────────────────────────────────────────
completeness_gate = CompletenessGate()
ground_truth_gate = GroundTruthGate()
eval_quarantine = EvalQuarantine()
hf_api = HfApi(token=HF_TOKEN) if HF_TOKEN else None

# ── دالة الحجز بالهاش الثابت (Hash-Based Stability) ─────────────────────────
def hash_based_reserve(sample_id: str, rate: float = 0.12) -> bool:
    h = int(hashlib.sha256(sample_id.encode()).hexdigest(), 16)
    return (h % 100) < int(rate * 100)

# ── بروتوكول الاستئناف الذاتي ──────────────────────────────────────────────
def load_checkpoint():
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE, 'r') as f: return json.load(f)
    return {"last_processed": 0}

def save_checkpoint(state):
    with open(CHECKPOINT_FILE, 'w') as f: json.dump(state, f)

checkpoint = load_checkpoint()

# ─── المعالجة المركزية الموحدة ─────────────────────────────────────────────
async def process_real_unit(unit: dict, source: str):
    is_complete, reason = completeness_gate.validate_unit(unit)
    if not is_complete:
        print(f"   ❌ رفض اكتمال [{source}]: {reason}")
        return False
    
    cve_id = unit.get("cve_id", "").strip()
    if cve_id:
        is_verified, nvd_data = ground_truth_gate.verify_cve(cve_id)
        if not is_verified:
            print(f"   ❌ رفض حقيقة [{source}]: CVE غير مثبت {cve_id}")
            return False
        unit.update({"_truth_gate": "NVD_VERIFIED", **nvd_data})
    else:
        unit["_truth_gate"] = "SANDBOX_NO_CVE"
    
    sample_id = unit.get("id") or hashlib.sha256(json.dumps(unit, sort_keys=True).encode()).hexdigest()
    if hash_based_reserve(sample_id):
        print(f"   🔒 حجز للتقييم [{source}] (Hash-Based)")
        return True 
    
    if hf_api:
        try:
            content_line = json.dumps(unit, ensure_ascii=False) + "\n"
            hf_api.upload_file(
                path_or_fileobj=content_line.encode(),
                path_in_repo=f"data/{source}_training_ready.jsonl",
                repo_id=REPO_ID, repo_type="dataset"
            )
            print(f"   ✅ رفع تدريب [{source}] → HF")
        except Exception as e:
            print(f"   ⚠️ فشل رفع HF [{source}]: {e}")
            return False
    
    return True

# ── نقاط الاستقبال ─────────────────────────────────────────────────────────
@app.post("/api/ingest")
async def ingest_from_cf(request: Request):
    try:
        data = await request.json()
        if not data or "payload" not in data:
            return {"status": "rejected", "reason": "empty_payload"}, 400
        
        unit = {"timestamp": time.time(), "source": data.get("agent_id", "cf_worker"), **data["payload"]}
        success = await process_real_unit(unit, "cloudflare")
        checkpoint["last_processed"] += 1; save_checkpoint(checkpoint)
        return {"status": "accepted" if success else "filtered"}, 200
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500

@app.get("/health")
async def health_check():
    return {
        "status": "operational", 
        "gates_loaded": True, 
        "hf_connected": hf_api is not None,
        "nvd_key_set": bool(NVD_API_KEY)
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    print(f" بدء المنسق الموحد (Handoff Gates) على المنفذ {port}")
    print(f"   • بوابة الاكتمال: نشطة")
    print(f"   • بوابة الحقيقة (NVD): {'✅' if NVD_API_KEY else '❌'}")
    print(f"   • حارس التقييم المحجوز: نشط")
    uvicorn.run(app, host="0.0.0.0", port=port)
