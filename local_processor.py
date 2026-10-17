"""
local_processor.py — معالج الملفات الضخمة بدون pandas/pyarrow
يعتمد فقط على csv, json, hashlib, huggingface_hub (مدمج أو خفيف)
"""
import os
import re
import csv
import json
import gzip
import time
import hashlib
from pathlib import Path
from typing import Iterator, Dict, Set

# ═══════════════════════════════════════════════════════════════════════════════
# 1. الإعدادات
# ═══════════════════════════════════════════════════════════════════════════════
INPUT_FILE = Path.home() / "Marsad" / "raw_dumps" / "train.csv.gz"
OUTPUT_DIR = Path.home() / "Marsad" / "processed_chunks"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ملف المفاتيح
ENV_FILE = Path("/data/data/com.termux/files/home/.marsad_secrets/all.env")

# تحميل المفاتيح
tokens = []
if ENV_FILE.exists():
    for line in ENV_FILE.read_text().splitlines():
        m = re.match(r"^(HF_TOKEN_\d+)=(.+)$", line.strip())
        if m:
            tokens.append(m.group(2).strip().strip('"').strip("'"))

if not tokens:
    raise ValueError("لا توجد مفاتيح Hugging Face متاحة!")

print(f"✅ تم تحميل {len(tokens)} مفاتيح Hugging Face")

# إعدادات الرفع
REPO_ID = "AbuYahya2/Marsad"
CHUNK_SIZE_MB = 200

# ═══════════════════════════════════════════════════════════════════════════════
# 2. بوابة الأمان
# ═══════════════════════════════════════════════════════════════════════════════
FORBIDDEN_PATTERNS = [
    r"hf_[a-zA-Z0-9]{30,}",
    r"ghp_[a-zA-Z0-9]{30,}",
    r"sk-or-[a-zA-Z0-9]{30,}",
    r"reverse.?shell",
    r"nc -e /bin",
    r"curl.*\|.*bash",
]

def safety_filter(code: str) -> bool:
    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, code, re.IGNORECASE):
            return False
    return True

# ═══════════════════════════════════════════════════════════════════════════════
# 3. إزالة التكرار
# ═══════════════════════════════════════════════════════════════════════════════
class Deduplicator:
    def __init__(self):
        self.seen_hashes: Set[str] = set()
    
    def is_duplicate(self, code: str) -> bool:
        code_hash = hashlib.sha256(code.encode()).hexdigest()
        if code_hash in self.seen_hashes:
            return True
        self.seen_hashes.add(code_hash)
        return False

# ═══════════════════════════════════════════════════════════════════════════════
# 4. المعالج التدفقي (يقرأ CSV.gz سطر بسطر)
# ═══════════════════════════════════════════════════════════════════════════════
class StreamProcessor:
    def __init__(self, input_file: Path):
        self.input_file = input_file
        self.deduplicator = Deduplicator()
        self.stats = {
            "total_read": 0,
            "passed_safety": 0,
            "passed_dedup": 0,
            "rejected_safety": 0,
            "rejected_duplicate": 0,
        }
    
    def process_file(self) -> Iterator[Dict]:
        print(f"\n📖 بدء قراءة الملف: {self.input_file.name}")
        
        # فتح الملف المضغوط
        with gzip.open(self.input_file, 'rt', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                self.stats["total_read"] += 1
                
                # استخراج الكود
                code = None
                for key in ["content", "code", "text"]:
                    if key in row and row[key]:
                        code = row[key]
                        break
                
                if not code or len(code) < 50:
                    continue
                
                # بوابة الأمان
                if not safety_filter(code):
                    self.stats["rejected_safety"] += 1
                    continue
                
                self.stats["passed_safety"] += 1
                
                # بوابة إزالة التكرار
                if self.deduplicator.is_duplicate(code):
                    self.stats["rejected_duplicate"] += 1
                    continue
                
                self.stats["passed_dedup"] += 1
                
                yield {
                    "code": code,
                    "source": self.input_file.stem,
                }
                
                if self.stats["total_read"] % 10000 == 0:
                    print(f"  ⏳ تمت معالجة {self.stats['total_read']:,} عينة...")

# ═══════════════════════════════════════════════════════════════════════════════
# 5. حفظ الدفعات كـ JSONL مضغوط
# ═══════════════════════════════════════════════════════════════════════════════
def save_chunk(samples: list, chunk_num: int) -> Path:
    chunk_file = OUTPUT_DIR / f"chunk_{chunk_num:04d}.jsonl.gz"
    
    with gzip.open(chunk_file, 'wt', encoding='utf-8') as f:
        for sample in samples:
            f.write(json.dumps(sample, ensure_ascii=False) + '\n')
    
    return chunk_file

# ═══════════════════════════════════════════════════════════════════════════════
# 6. مدير الرفع
# ═══════════════════════════════════════════════════════════════════════════════
class UploadManager:
    def __init__(self, tokens: list, repo_id: str):
        self.tokens = tokens
        self.current_token_idx = 0
        self.repo_id = repo_id
        
        # محاولة استيراد huggingface_hub
        try:
            from huggingface_hub import HfApi
            self.api = HfApi(token=self.tokens[0])
            self.hf_available = True
        except ImportError:
            print("⚠️ huggingface_hub غير مثبت. سيتم حفظ الملفات محلياً فقط.")
            self.hf_available = False
            self.api = None
    
    def rotate_token(self):
        if not self.hf_available:
            return
        self.current_token_idx = (self.current_token_idx + 1) % len(self.tokens)
        from huggingface_hub import HfApi
        self.api = HfApi(token=self.tokens[self.current_token_idx])
        print(f"🔄 تم تبديل المفتاح")
    
    def upload_file(self, file_path: Path, max_retries: int = 5) -> bool:
        if not self.hf_available:
            print(f"💾 تم الحفظ محلياً: {file_path}")
            return True
        
        for attempt in range(max_retries):
            try:
                print(f"📤 جاري الرفع: {file_path.name}")
                
                self.api.upload_file(
                    path_or_fileobj=str(file_path),
                    path_in_repo=f"processed/{file_path.name}",
                    repo_id=self.repo_id,
                    repo_type="dataset",
                    commit_message=f"Auto-upload {file_path.name}",
                )
                
                print(f"✅ تم الرفع بنجاح")
                return True
            
            except Exception as e:
                print(f"⚠️ فشل: {str(e)[:50]}")
                self.rotate_token()
                time.sleep(2)
        
        return False

# ═══════════════════════════════════════════════════════════════════════════════
# 7. التنفيذ الرئيسي
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    print("=" * 70)
    print("🏭 MARSAD Local Processor (بدون pandas/pyarrow)")
    print("=" * 70)
    
    if not INPUT_FILE.exists():
        print(f"❌ الملف غير موجود: {INPUT_FILE}")
        print("💡 قم بتحويل Parquet إلى CSV.gz أولاً على Kaggle")
        return
    
    file_size_mb = INPUT_FILE.stat().st_size / (1024 * 1024)
    print(f"📦 حجم الملف: {file_size_mb:.2f} MB")
    
    processor = StreamProcessor(INPUT_FILE)
    uploader = UploadManager(tokens, REPO_ID)
    
    current_chunk = []
    chunk_num = 0
    chunk_size_bytes = 0
    
    print("\n🚀 بدء المعالجة...")
    
    for sample in processor.process_file():
        current_chunk.append(sample)
        chunk_size_bytes += len(sample["code"].encode('utf-8'))
        
        if chunk_size_bytes >= CHUNK_SIZE_MB * 1024 * 1024:
            chunk_num += 1
            print(f"\n💾 حفظ الدفعة {chunk_num} ({len(current_chunk)} عينة)...")
            
            chunk_file = save_chunk(current_chunk, chunk_num)
            uploader.upload_file(chunk_file)
            
            current_chunk = []
            chunk_size_bytes = 0
    
    if current_chunk:
        chunk_num += 1
        print(f"\n💾 حفظ الدفعة النهائية {chunk_num}...")
        chunk_file = save_chunk(current_chunk, chunk_num)
        uploader.upload_file(chunk_file)
    
    print("\n" + "=" * 70)
    print("📊 الإحصائيات النهائية:")
    print("=" * 70)
    stats = processor.stats
    
    print(f"  إجمالي العينات: {stats['total_read']:,}")
    print(f"  ✅ اجتازت الأمان: {stats['passed_safety']:,}")
    print(f"  ✅ اجتازت إزالة التكرار: {stats['passed_dedup']:,}")
    print(f"  ❌ رُفضت (أمان): {stats['rejected_safety']:,}")
    print(f"  ❌ رُفضت (تكرار): {stats['rejected_duplicate']:,}")
    print(f"  📦 عدد الدفعات: {chunk_num}")
    
    print("\n✅ اكتملت المعالجة!")

if __name__ == "__main__":
    main()
