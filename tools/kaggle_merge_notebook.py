# ═══════════════════════════════════════════════════════════════
# Kaggle Notebook — Marsad Merge v3
# ═══════════════════════════════════════════════════════════════
# استخدمه كلصقة واحدة في خلية Kaggle واحدة.
# لا يحتاج MoE. لا يحتاج --lazy-unpickle (غير موجود).
# يستخدم التحميل الكسول المدمج في mergekit.
# ═══════════════════════════════════════════════════════════════

import os, yaml, time, subprocess, sys, threading
from pathlib import Path
from kaggle_secrets import UserSecretsClient
from huggingface_hub import HfApi, create_repo, whoami

# ─── 1. المصادقة ───────────────────────────────────────────────
HF_TOKEN = UserSecretsClient().get_secret("HF_TOKEN")
os.environ["HF_TOKEN"] = HF_TOKEN
os.environ["HUGGING_FACE_HUB_TOKEN"] = HF_TOKEN
me = whoami(token=HF_TOKEN)
USER, REPO = me["name"], f"{me['name']}/deepseek-marsad-v3"
api = HfApi(token=HF_TOKEN)
print(f"✅ {USER} → {REPO}")

create_repo(repo_id=REPO, token=HF_TOKEN, repo_type="model", exist_ok=True)

# ─── 2. Config (dense، ليس MoE) ────────────────────────────────
config = {
  "merge_method": "ties",
  "base_model": "deepseek-ai/DeepSeek-R1-Distill-Llama-8B",
  "models": [
    {"model": "deepseek-ai/DeepSeek-R1-Distill-Llama-8B",
     "parameters": {"weight": 0.35, "density": 0.5}},
    {"model": "arcee-ai/Llama-3.1-SuperNova-Lite",
     "parameters": {"weight": 0.30, "density": 0.5}},
    {"model": "FuseAI/FuseChat-Llama-3.1-8B-Instruct",
     "parameters": {"weight": 0.25, "density": 0.5}},
    {"model": "richardyoung/Llama-3.1-8B-Instruct-abliterated-obliteratus",
     "parameters": {"weight": 0.10, "density": 0.5}},
  ],
  "parameters": {"normalize": True},
  "dtype": "bfloat16",
}
Path("merge_config.yaml").write_text(yaml.safe_dump(config))
print("✅ Config ready")

# ─── 3. تثبيت mergekit ─────────────────────────────────────────
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "mergekit"], check=True)
print("✅ mergekit installed")

# ─── 4. Watcher — يرفع كل shard فور اكتماله ────────────────────
MERGED = Path("./merged"); MERGED.mkdir(exist_ok=True)
uploaded, stop_flag = set(), threading.Event()

def watch_and_upload():
    """يرفع كل ملف shard جديد فور استقرار حجمه."""
    while not stop_flag.is_set():
        try:
            for f in MERGED.iterdir():
                if not f.is_file() or f.name in uploaded: continue
                if f.suffix == ".tmp" or f.stat().st_size == 0: continue
                s1 = f.stat().st_size; time.sleep(3)
                if s1 != f.stat().st_size: continue   # لا يزال يُكتب
                mb = s1 // (1024*1024)
                print(f"📤 {f.name} ({mb} MB)")
                try:
                    api.upload_file(path_or_fileobj=str(f),
                                    path_in_repo=f.name, repo_id=REPO,
                                    repo_type="model", token=HF_TOKEN)
                    uploaded.add(f.name)
                    print(f"   ✅ {f.name}")
                except Exception as e:
                    print(f"   ⚠️ {f.name}: {e}")
        except Exception as e:
            print(f"watcher: {e}")
        time.sleep(15)

w = threading.Thread(target=watch_and_upload, daemon=True); w.start()
print("✅ Watcher started")

# ─── 5. الصهر — التحميل الكسول مدمج تلقائياً ───────────────────
# ملاحظة: --allow-crimes موجود | --lazy-unpickle غير موجود
print("⏳ Merging (18-25 min)...")
r = subprocess.run(
    [sys.executable, "-m", "mergekit.scripts.run_yaml",
     "merge_config.yaml", "./merged",
     "--copy-tokenizer", "--allow-crimes",
     "--out-shard-size", "2B"],
    capture_output=True, text=True)

if r.returncode != 0:
    print("STDOUT:", r.stdout[-2000:]); print("STDERR:", r.stderr[-2000:])
    raise RuntimeError("Merge failed")
print("✅ Merge completed")

# ─── 6. إغلاق Watcher ورفع المتبقي ─────────────────────────────
time.sleep(120); stop_flag.set(); w.join(timeout=30)
for f in MERGED.iterdir():
    if f.is_file() and f.name not in uploaded:
        try:
            api.upload_file(path_or_fileobj=str(f), path_in_repo=f.name,
                            repo_id=REPO, repo_type="model", token=HF_TOKEN)
            print(f"✅ final: {f.name}")
        except Exception as e:
            print(f"⚠️ final {f.name}: {e}")

print(f"\n🔗 https://huggingface.co/{REPO}")
