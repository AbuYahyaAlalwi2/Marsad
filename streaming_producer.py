import os, re, json, gzip, hashlib
from pathlib import Path
from huggingface_hub import HfApi
from datasets import load_dataset

# 1) تحميل المفاتيح من متغيرات البيئة (يشتغل بأي مكان: Termux/Kaggle/GH Actions)
TOKENS = [v.strip() for k, v in os.environ.items()
          if k.startswith("HF_TOKEN") and v.strip().startswith("hf_")]

if not TOKENS:
    print("❌ لا توجد مفاتيح HF_TOKEN* بمتغيرات البيئة. صدّرها أولاً (export) أو شغّل عبر systemd/secrets.")
    exit(1)

print(f"✅ تم تحميل {len(TOKENS)} مفاتيح Hugging Face")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")
REPO_ID = "AbuYahya2/Marsad"
OUTPUT_DIR = Path.home() / "Marsad" / "production_data"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def send_tg(msg):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        import requests
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                      json={'chat_id': TELEGRAM_CHAT_ID, 'text': msg, 'parse_mode': 'HTML'}, timeout=5)
    except Exception:
        pass

FORBIDDEN = [r"hf_[a-zA-Z0-9]{30,}", r"ghp_[a-zA-Z0-9]{30,}", r"sk-or-[a-zA-Z0-9]{30,}"]
def safety_ok(code):
    return not any(re.search(p, str(code), re.IGNORECASE) for p in FORBIDDEN)

seen = set()
def dedup_ok(code):
    h = hashlib.sha256(str(code).encode()).hexdigest()
    if h in seen:
        return False
    seen.add(h)
    return True

def process_streaming(repo_id, config_name, max_samples=5000):
    print(f"\n{'='*70}\n📥 {repo_id} (config: {config_name})\n{'='*70}")
    try:
        ds = load_dataset(repo_id, name=config_name, split="train",
                           streaming=True, token=TOKENS[0], trust_remote_code=False)
        print("✅ اتصال ناجح")
    except Exception as e:
        print(f"❌ فشل الاتصال: {e}")
        return 0

    stats = {"total": 0, "passed": 0}
    chunk, chunk_n = [], 0

    for item in ds:
        if stats["total"] >= max_samples:
            break
        stats["total"] += 1
        code = item.get("content") or item.get("code") or item.get("text") or item.get("solutions")
        if not code or len(str(code)) < 50:
            continue
        if not safety_ok(code) or not dedup_ok(code):
            continue
        stats["passed"] += 1
        chunk.append({"code": str(code), "source": repo_id})

        if len(chunk) >= 1000:
            chunk_n += 1
            f = OUTPUT_DIR / f"marsad_stream_{repo_id.replace('/','_')}_{chunk_n:04d}.jsonl.gz"
            with gzip.open(f, 'wt', encoding='utf-8') as fh:
                for s in chunk:
                    fh.write(json.dumps(s, ensure_ascii=False) + '\n')
            print(f"  💾 دفعة #{chunk_n}: {len(chunk)} عينة → {f.name}")
            try:
                HfApi(token=TOKENS[0]).upload_file(path_or_fileobj=str(f), path_in_repo=f"chunks/{f.name}",
                                                     repo_id=REPO_ID, repo_type="dataset")
                print("  ✅ رُفعت لـ HF")
            except Exception as e:
                print(f"  ⚠️ فشل الرفع: {e}")
            chunk = []

    if chunk:
        chunk_n += 1
        f = OUTPUT_DIR / f"marsad_stream_{repo_id.replace('/','_')}_final_{chunk_n:04d}.jsonl.gz"
        with gzip.open(f, 'wt', encoding='utf-8') as fh:
            for s in chunk:
                fh.write(json.dumps(s, ensure_ascii=False) + '\n')

    print(f"  📊 {repo_id}: {stats['total']} إجمالي | {stats['passed']} مقبول")
    return stats["passed"]

def main():
    print(f"🚀 بدء بـ {len(TOKENS)} مفاتيح")
    # نبدأ بـ codeparrot/apps فقط أول مرة لأنه أقل عرضة للـ gating من starcoderdata
    targets = [("codeparrot/apps", "all")]
    total = 0
    for repo_id, cfg in targets:
        total += process_streaming(repo_id, cfg, max_samples=5000)

    files = list(OUTPUT_DIR.glob("*.jsonl.gz"))
    size = sum(f.stat().st_size for f in files)
    report = f"📊 عينات مقبولة: {total} | ملفات: {len(files)} | حجم: {size/1024/1024:.2f} MB"
    print(f"\n{'='*70}\n{report}\n{'='*70}")
    send_tg(report)

if __name__ == "__main__":
    main()
