import os, re, csv, json, gzip, time, hashlib, urllib.request
from pathlib import Path
from typing import Dict

ENV_FILE = Path("/data/data/com.termux/files/home/.marsad_secrets/all.env")
INPUT_DIR = Path.home() / "Marsad" / "raw_dumps"
OUTPUT_DIR = Path.home() / "Marsad" / "diagnostic_output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

tokens, telegram_token, telegram_chat_id = [], None, None

if ENV_FILE.exists():
    for line in ENV_FILE.read_text().splitlines():
        # تنظيف السطر من أي أحرف مخفية أو مسافات
        line = line.strip().replace('\r', '').replace('\n', '')
        if not line or line.startswith('#'): 
            continue
        
        if 'HF_TOKEN' in line and '=' in line:
            token = line.split('=', 1)[1].strip().strip('"').strip("'")
            if token.startswith('hf_'): 
                tokens.append(token)
                
        if 'TELEGRAM_BOT_TOKEN' in line and '=' in line:
            telegram_token = line.split('=', 1)[1].strip().strip('"').strip("'")
            
        if 'TELEGRAM_CHAT_ID' in line and '=' in line:
            telegram_chat_id = line.split('=', 1)[1].strip().strip('"').strip("'")

def send_tg(msg):
    if not telegram_token or not telegram_chat_id: 
        return print(f"[TG] {msg}")
    try:
        url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
        data = json.dumps({'chat_id': telegram_chat_id, 'text': msg, 'parse_mode': 'HTML'}).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            print("✅ [Telegram] تم الإرسال بنجاح")
    except Exception as e: 
        print(f"❌ [TG-ERR] {e}")

FORBIDDEN = [r"hf_[a-zA-Z0-9]{30,}", r"ghp_[a-zA-Z0-9]{30,}", r"sk-or-[a-zA-Z0-9]{30,}"]
def safety_ok(code): 
    return not any(re.search(p, str(code), re.IGNORECASE) for p in FORBIDDEN)

seen = set()
def dedup_ok(code):
    h = hashlib.sha256(str(code).encode()).hexdigest()
    if h in seen: return False
    seen.add(h)
    return True

def run_pipeline(duration_sec=60):
    print("="*60)
    print("🚀 MARSAD Producer - بدء خط الإنتاج")
    print("="*60)
    send_tg("🚀 <b>بدء خط إنتاج MARSAD</b>\nجاري المعالجة والضغط...")
    
    csv_files = list(INPUT_DIR.glob("*.csv.gz"))
    if not csv_files:
        print("❌ لا توجد ملفات CSV.gz في raw_dumps")
        return
    
    input_file = csv_files[-1]
    print(f"📖 معالجة: {input_file.name}")
    
    stats = {"total": 0, "passed": 0, "rejected": 0, "bytes": 0}
    start = time.time()
    chunk_samples = []
    
    with gzip.open(input_file, 'rt', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            if time.time() - start > duration_sec: 
                break
            stats["total"] += 1
            
            code = row.get("content") or row.get("code") or row.get("text")
            if not code or len(str(code)) < 50: 
                continue
            
            stats["bytes"] += len(str(code).encode('utf-8'))
            
            if not safety_ok(code) or not dedup_ok(code):
                stats["rejected"] += 1
                continue
                
            stats["passed"] += 1
            chunk_samples.append({"code": str(code)})
            
            # حفظ ورفع كل 10,000 عينة
            if len(chunk_samples) >= 10000:
                chunk_file = OUTPUT_DIR / f"marsad_chunk_{int(time.time())}.jsonl.gz"
                with gzip.open(chunk_file, 'wt', encoding='utf-8') as cf:
                    for s in chunk_samples: 
                        cf.write(json.dumps(s, ensure_ascii=False) + '\n')
                
                print(f"💾 تم حفظ دفعة: {chunk_file.name}")
                chunk_samples = []

    # حفظ المتبقي
    if chunk_samples:
        chunk_file = OUTPUT_DIR / f"marsad_chunk_final_{int(time.time())}.jsonl.gz"
        with gzip.open(chunk_file, 'wt', encoding='utf-8') as cf:
            for s in chunk_samples: 
                cf.write(json.dumps(s, ensure_ascii=False) + '\n')
        print(f"💾 تم حفظ الدفعة النهائية: {chunk_file.name}")

    elapsed = time.time() - start
    compressed_size = sum(f.stat().st_size for f in OUTPUT_DIR.glob("marsad_chunk_*.jsonl.gz"))
    
    samples_per_sec = round(stats["total"] / elapsed, 2) if elapsed > 0 else 0
    compression_ratio = round(compressed_size / stats["bytes"], 3) if stats["bytes"] > 0 else 0
    
    # التنبؤ اليومي
    samples_per_day = samples_per_sec * 86400
    mb_per_sample = compressed_size / stats["passed"] if stats["passed"] > 0 else 0
    gb_per_day = (samples_per_day * mb_per_sample) / (1024 * 1024)
    
    report = (f"✅ <b>اكتملت دورة المعالجة!</b>\n"
              f"📝 إجمالي: {stats['total']:,}\n"
              f"✅ مقبول: {stats['passed']:,}\n"
              f"❌ مرفوض: {stats['rejected']:,}\n"
              f"🚀 السرعة: {samples_per_sec} ع/ث\n"
              f"📦 التنبؤ اليومي: {gb_per_day:.2f} GB مضغوطة")
    
    print("\n" + "="*60)
    print(report)
    print("="*60)
    send_tg(report)

if __name__ == "__main__":
    run_pipeline(duration_sec=60)
