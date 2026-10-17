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
        line = line.strip()
        if not line or line.startswith('#'): continue
        if 'HF_TOKEN' in line and '=' in line:
            token = line.split('=', 1)[1].strip().strip('"').strip("'")
            if token.startswith('hf_'): tokens.append(token)
        if 'TELEGRAM_BOT_TOKEN' in line and '=' in line:
            telegram_token = line.split('=', 1)[1].strip().strip('"').strip("'")
        if 'TELEGRAM_CHAT_ID' in line and '=' in line:
            telegram_chat_id = line.split('=', 1)[1].strip().strip('"').strip("'")

def send_tg(msg):
    if not telegram_token or not telegram_chat_id: return print(f"[TG] {msg}")
    try:
        url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
        data = json.dumps({'chat_id': telegram_chat_id, 'text': msg, 'parse_mode': 'HTML'}).encode('utf-8')
        urllib.request.urlopen(urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'}), timeout=10)
    except Exception as e: print(f"[TG-ERR] {e}")

FORBIDDEN = [r"hf_[a-zA-Z0-9]{30,}", r"ghp_[a-zA-Z0-9]{30,}", r"sk-or-[a-zA-Z0-9]{30,}"]
def safety_ok(code): return not any(re.search(p, code, re.IGNORECASE) for p in FORBIDDEN)

seen = set()
def dedup_ok(code):
    h = hashlib.sha256(code.encode()).hexdigest()
    if h in seen: return False
    seen.add(h)
    return True

def test_processing(duration_sec=60):
    print(f"\n️ اختبار المعالجة الحقيقية (لمدة {duration_sec} ثانية)")
    send_tg("️ <b>بدء اختبار المعالجة على بيانات حقيقية</b>")
    
    csv_files = list(INPUT_DIR.glob("*.csv.gz"))
    if not csv_files:
        print("❌ لا توجد ملفات CSV.gz. يرجى تشغيل خطوة التحضير أولاً.")
        return {"status": "no_data"}
    
    input_file = csv_files[-1]
    print(f"📖 استخدام: {input_file.name}")
    
    stats = {"total": 0, "passed_safety": 0, "passed_dedup": 0, "rejected_safety": 0, "rejected_duplicate": 0, "bytes_processed": 0}
    start = time.time()
    chunk_samples = []
    
    with gzip.open(input_file, 'rt', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            if time.time() - start > duration_sec: break
            stats["total"] += 1
            
            code = row.get("content") or row.get("code") or row.get("text")
            if not code or len(str(code)) < 50: continue
            
            stats["bytes_processed"] += len(str(code).encode('utf-8'))
            
            if not safety_ok(str(code)):
                stats["rejected_safety"] += 1
                continue
            stats["passed_safety"] += 1
            
            if not dedup_ok(str(code)):
                stats["rejected_duplicate"] += 1
                continue
            stats["passed_dedup"] += 1
            
            chunk_samples.append({"code": str(code)})
            if len(chunk_samples) >= 5000:
                chunk_file = OUTPUT_DIR / f"real_test_chunk_{int(time.time())}.jsonl.gz"
                with gzip.open(chunk_file, 'wt', encoding='utf-8') as cf:
                    for s in chunk_samples: cf.write(json.dumps(s, ensure_ascii=False) + '\n')
                chunk_samples = []
    
    if chunk_samples:
        chunk_file = OUTPUT_DIR / f"real_test_chunk_{int(time.time())}.jsonl.gz"
        with gzip.open(chunk_file, 'wt', encoding='utf-8') as cf:
            for s in chunk_samples: cf.write(json.dumps(s, ensure_ascii=False) + '\n')
    
    elapsed = time.time() - start
    compressed_size = sum(f.stat().st_size for f in OUTPUT_DIR.glob("real_test_chunk_*.jsonl.gz"))
    
    result = {
        **stats, "elapsed_sec": round(elapsed, 2),
        "samples_per_sec": round(stats["total"] / elapsed, 2) if elapsed > 0 else 0,
        "compressed_bytes": compressed_size,
        "compression_ratio": round(compressed_size / stats["bytes_processed"], 3) if stats["bytes_processed"] > 0 else 0,
    }
    
    print(f"\n📊 نتيجة المعالجة الحقيقية:")
    print(f"  إجمالي: {stats['total']:,} | ✅ أمان: {stats['passed_safety']:,} | ✅ فريد: {stats['passed_dedup']:,}")
    print(f"  ⏱️ الوقت: {elapsed:.2f} ث | 🚀 السرعة: {result['samples_per_sec']} ع/ث")
    print(f"  📦 مضغوط: {compressed_size/(1024*1024):.2f} MB | 🗜️ ضغط: {result['compression_ratio']*100:.1f}%")
    
    send_tg(f" <b>نتيجة المعالجة الحقيقية:</b>\n"
            f"📝 إجمالي: {stats['total']:,}\n✅ فريد: {stats['passed_dedup']:,}\n"
            f"⏱️ الوقت: {elapsed:.2f} ث\n🚀 السرعة: {result['samples_per_sec']} ع/ث\n"
            f"📦 مضغوط: {compressed_size/(1024*1024):.2f} MB\n🗜️ ضغط: {result['compression_ratio']*100:.1f}%")
    return result

def predict_daily(process_result: Dict):
    if process_result.get("status") == "no_data": return
    samples_per_sec = process_result["samples_per_sec"]
    samples_per_day = samples_per_sec * 86400
    compressed_mb_per_sample = process_result["compressed_bytes"] / process_result["passed_dedup"] if process_result["passed_dedup"] > 0 else 0
    compressed_mb_per_day = (samples_per_day * compressed_mb_per_sample) / (1024 * 1024)
    
    report = f"🔮 <b>التنبؤ اليومي (24 ساعة):</b>\n" \
             f"• العينات/يوم: {samples_per_day:,.0f}\n" \
             f"• الحجم المضغوط/يوم: {compressed_mb_per_day:,.2f} MB ({compressed_mb_per_day/1024:,.2f} GB)\n\n"
    
    if compressed_mb_per_day >= 20000: report += "✅ <b>ممتاز!</b> يتجاوز هدف 20 جيجا"
    elif compressed_mb_per_day >= 10000: report += "️ <b>جيد</b> - يحقق 50% من الهدف"
    elif compressed_mb_per_day >= 1000: report += "⚠️ <b>متوسط</b> - يحتاج توسيع المصادر"
    else: report += "❌ <b>ضعيف</b> - يحتاج إعادة تصميم"
    
    print(f"\n{report}")
    send_tg(report)

if __name__ == "__main__":
    print("="*60 + "\n🧪 MARSAD Diagnostic Test (مصحح)\n" + "="*60)
    send_tg("🚀 <b>بدء الاختبار التشخيصي المصحح</b>")
    process_result = test_processing(duration_sec=60)
    predict_daily(process_result)
    send_tg("✅ <b>اكتمل الاختبار</b>")
    print("\n✅ اكتمل الاختبار")
