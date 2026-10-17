import os, re, json, gzip, time, hashlib
from pathlib import Path
from huggingface_hub import hf_hub_download

ENV_FILE = Path("/data/data/com.termux/files/home/.marsad_secrets/all.env")
OUTPUT_DIR = Path.home() / "Marsad" / "production_data"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# تحميل المفاتيح
tokens = []
if ENV_FILE.exists():
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip().replace('\r', '').replace('\n', '')
        if 'HF_TOKEN' in line and '=' in line:
            token = line.split('=', 1)[1].strip().strip('"').strip("'")
            if token.startswith('hf_'):
                tokens.append(token)

if not tokens:
    raise ValueError("لا توجد مفاتيح Hugging Face!")

print(f"✅ تم تحميل {len(tokens)} مفاتيح HF")

# بوابات الجودة
FORBIDDEN = [r"hf_[a-zA-Z0-9]{30,}", r"ghp_[a-zA-Z0-9]{30,}", r"sk-or-[a-zA-Z0-9]{30,}"]
def safety_ok(code):
    return not any(re.search(p, str(code), re.IGNORECASE) for p in FORBIDDEN)

seen = set()
def dedup_ok(code):
    h = hashlib.sha256(str(code).encode()).hexdigest()
    if h in seen: return False
    seen.add(h)
    return True

# مصادر JSONL المباشرة
SOURCES = [
    {
        "name": "python-code-200k",
        "repo": "nampdn-ai/python-code-200k",
        "filename": "data/train-00000-of-00001.jsonl",
        "token_idx": 0
    },
    {
        "name": "stackoverflow-python",
        "repo": "bigcode/stackoverflow-python",
        "filename": "data/train-00000-of-00001.jsonl",
        "token_idx": 1
    }
]

def download_and_process(source, max_samples=50000):
    print(f"\n📥 معالجة: {source['name']}")
    
    token = tokens[source["token_idx"] % len(tokens)]
    
    try:
        print(f"  ⬇️ جاري التحميل من {source['repo']}...")
        file_path = hf_hub_download(
            repo_id=source["repo"],
            filename=source["filename"],
            repo_type="dataset",
            token=token,
            cache_dir=str(Path.home() / "Marsad" / "cache")
        )
        print(f"  ✅ تم التحميل: {file_path}")
    except Exception as e:
        print(f"  ❌ فشل التحميل: {e}")
        return 0
    
    stats = {"total": 0, "passed": 0, "rejected": 0}
    chunk_samples = []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f):
            if stats["total"] >= max_samples:
                break
            
            stats["total"] += 1
            
            try:
                row = json.loads(line)
            except:
                continue
            
            # استخراج الكود
            code = None
            for field in ["code", "content", "text", "answer"]:
                if field in row:
                    code = row[field]
                    break
            
            if not code or len(str(code)) < 50:
                continue
            
            if not safety_ok(code) or not dedup_ok(code):
                stats["rejected"] += 1
                continue
            
            stats["passed"] += 1
            chunk_samples.append({"code": str(code), "source": source["name"]})
            
            # حفظ كل 10,000 عينة
            if len(chunk_samples) >= 10000:
                chunk_file = OUTPUT_DIR / f"prod_chunk_{int(time.time())}_{len(list(OUTPUT_DIR.glob('prod_chunk_*'))):04d}.jsonl.gz"
                with gzip.open(chunk_file, 'wt', encoding='utf-8') as cf:
                    for s in chunk_samples:
                        cf.write(json.dumps(s, ensure_ascii=False) + '\n')
                print(f"  💾 دفعة: {chunk_file.name} ({len(chunk_samples)} عينة)")
                chunk_samples = []
            
            if stats["total"] % 10000 == 0:
                print(f"   تمت معالجة {stats['total']:,} عينة...")
    
    # حفظ المتبقي
    if chunk_samples:
        chunk_file = OUTPUT_DIR / f"prod_chunk_final_{int(time.time())}.jsonl.gz"
        with gzip.open(chunk_file, 'wt', encoding='utf-8') as cf:
            for s in chunk_samples:
                cf.write(json.dumps(s, ensure_ascii=False) + '\n')
        print(f"  💾 دفعة نهائية: {chunk_file.name}")
    
    print(f"\n  📊 نتيجة {source['name']}:")
    print(f"    إجمالي: {stats['total']:,} | ✅ مقبول: {stats['passed']:,} | ❌ مرفوض: {stats['rejected']:,}")
    
    return stats["passed"]

def main():
    print("="*70)
    print("🚀 MARSAD Real Producer - خط الإنتاج الحقيقي")
    print("="*70)
    
    total_accepted = 0
    
    for source in SOURCES:
        accepted = download_and_process(source, max_samples=50000)
        total_accepted += accepted
    
    # حساب الحجم الكلي
    files = list(OUTPUT_DIR.glob("prod_chunk_*.jsonl.gz"))
    total_size = sum(f.stat().st_size for f in files)
    
    print(f"\n{'='*70}")
    print(f"📊 الملخص النهائي:")
    print(f"  ✅ إجمالي العينات المقبولة: {total_accepted:,}")
    print(f"  📦 عدد الملفات: {len(files)}")
    print(f"  💾 الحجم الكلي: {total_size / (1024*1024):.2f} MB ({total_size / (1024*1024*1024):.3f} GB)")
    print(f"{'='*70}")
    print("✅ اكتمل خط الإنتاج!")

if __name__ == "__main__":
    main()
