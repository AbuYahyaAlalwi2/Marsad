"""
diagnostic_test_1h.py — اختبار تشخيصي لمدة ساعة واحدة
"""
import os, re, csv, json, gzip, time, hashlib, urllib.request
from pathlib import Path
from datetime import datetime
from typing import Dict

ENV_FILE = Path("/data/data/com.termux/files/home/.marsad_secrets/all.env")
INPUT_DIR = Path.home() / "Marsad" / "raw_dumps"
OUTPUT_DIR = Path.home() / "Marsad" / "diagnostic_output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

tokens = []
telegram_token = None
telegram_chat_id = None

if ENV_FILE.exists():
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if 'HF_TOKEN' in line and '=' in line:
            parts = line.split('=', 1)
            if len(parts) == 2:
                token = parts[1].strip().strip('"').strip("'")
                if token.startswith('hf_'):
                    tokens.append(token)
        if 'TELEGRAM_BOT_TOKEN' in line and '=' in line:
            telegram_token = line.split('=', 1)[1].strip().strip('"').strip("'")
        if 'TELEGRAM_CHAT_ID' in line and '=' in line:
            telegram_chat_id = line.split('=', 1)[1].strip().strip('"').strip("'")

def send_telegram(message: str):
    if not telegram_token or not telegram_chat_id:
        print(f"[TG-SKIP] {message}")
        return
    try:
        url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
        data = json.dumps({'chat_id': telegram_chat_id, 'text': message, 'parse_mode': 'HTML'}).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            pass
    except Exception as e:
        print(f"[TG-ERROR] {e}")

FORBIDDEN = [r"hf_[a-zA-Z0-9]{30,}", r"ghp_[a-zA-Z0-9]{30,}", r"sk-or-[a-zA-Z0-9]{30,}"]

def safety_ok(code: str) -> bool:
    return not any(re.search(p, code, re.IGNORECASE) for p in FORBIDDEN)

seen_hashes = set()
def dedup_ok(code: str) -> bool:
    h = hashlib.sha256(code.encode()).hexdigest()
    if h in seen_hashes:
        return False
    seen_hashes.add(h)
    return True

def test_hf_download():
    print("\n📥 اختبار 1: سرعة السحب من Hugging Face")
    send_telegram("🧪 <b>بدء الاختبار التشخيصي</b>\n\n📥 الاختبار 1: سرعة السحب من HF")
    
    start = time.time()
    
    try:
        from huggingface_hub import hf_hub_download
        file_path = hf_hub_download(
            repo_id="bigcode/the-stack-v2",
            filename="data/python/train-00000-of-00100.parquet",
            repo_type="dataset",
            cache_dir=str(OUTPUT_DIR / "cache")
        )
        elapsed = time.time() - start
        size_mb = Path(file_path).stat().st_size / (1024 * 1024)
        speed_mbps = size_mb / elapsed if elapsed > 0 else 0
        
        result = {
            "status": "success",
            "size_mb": round(size_mb, 2),
            "elapsed_sec": round(elapsed, 2),
            "speed_mbps": round(speed_mbps, 2),
        }
        print(f"  ✅ تم السحب: {size_mb:.2f} MB في {elapsed:.2f} ثانية ({speed_mbps:.2f} MB/s)")
        send_telegram(f"✅ <b>نتيجة السحب:</b>\n📦 الحجم: {size_mb:.2f} MB\n⏱️ الوقت: {elapsed:.2f} ثانية\n🚀 السرعة: {speed_mbps:.2f} MB/s")
        return result
    except Exception as e:
        print(f"  ❌ فشل: {e}")
        send_telegram(f"❌ <b>فشل السحب:</b>\n{str(e)[:200]}")
        return {"status": "failed", "error": str(e)}

def test_processing(duration_sec: int = 300):
    print(f"\n⚙️ اختبار 2: سرعة المعالجة (لمدة {duration_sec} ثانية)")
    send_telegram(f"⚙️ <b>الاختبار 2:</b> سرعة المعالجة لمدة {duration_sec} ثانية")
    
    csv_files = list(INPUT_DIR.glob("*.csv.gz"))
    if not csv_files:
        print("  ❌ لا توجد ملفات CSV.gz في raw_dumps")
        send_telegram("❌ لا توجد ملفات للمعالجة")
        return {"status": "no_data"}
    
    input_file = csv_files[0]
    print(f"  📖 استخدام: {input_file.name}")
    
    stats = {
        "total": 0,
        "passed_safety": 0,
        "passed_dedup": 0,
        "rejected_safety": 0,
        "rejected_duplicate": 0,
        "bytes_processed": 0,
    }
    
    start = time.time()
    chunk_samples = []
    chunk_bytes = 0
    
    with gzip.open(input_file, 'rt', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            if time.time() - start > duration_sec:
                break
            
            stats["total"] += 1
            
            code = None
            for key in ["content", "code", "text"]:
                if key in row and row[key]:
                    code = row[key]
                    break
            
            if not code or len(code) < 50:
                continue
            
            stats["bytes_processed"] += len(code.encode('utf-8'))
            
            if not safety_ok(code):
                stats["rejected_safety"] += 1
                continue
            stats["passed_safety"] += 1
            
            if not dedup_ok(code):
                stats["rejected_duplicate"] += 1
                continue
            stats["passed_dedup"] += 1
            
            chunk_samples.append({"code": code})
            chunk_bytes += len(code.encode('utf-8'))
            
            if len(chunk_samples) >= 10000:
                chunk_file = OUTPUT_DIR / f"test_chunk_{len(list(OUTPUT_DIR.glob('test_chunk_*'))):04d}.jsonl.gz"
                with gzip.open(chunk_file, 'wt', encoding='utf-8') as cf:
                    for s in chunk_samples:
                        cf.write(json.dumps(s, ensure_ascii=False) + '\n')
                print(f"  💾 حفظ دفعة: {chunk_file.name} ({len(chunk_samples)} عينة)")
                chunk_samples = []
    
    if chunk_samples:
        chunk_file = OUTPUT_DIR / f"test_chunk_{len(list(OUTPUT_DIR.glob('test_chunk_*'))):04d}.jsonl.gz"
        with gzip.open(chunk_file, 'wt', encoding='utf-8') as cf:
            for s in chunk_samples:
                cf.write(json.dumps(s, ensure_ascii=False) + '\n')
    
    elapsed = time.time() - start
    
    compressed_size = sum(f.stat().st_size for f in OUTPUT_DIR.glob("test_chunk_*.jsonl.gz"))
    
    result = {
        **stats,
        "elapsed_sec": round(elapsed, 2),
        "samples_per_sec": round(stats["total"] / elapsed, 2) if elapsed > 0 else 0,
        "compressed_bytes": compressed_size,
        "compression_ratio": round(compressed_size / stats["bytes_processed"], 3) if stats["bytes_processed"] > 0 else 0,
    }
    
    print(f"\n📊 نتيجة المعالجة:")
    print(f"  إجمالي العينات: {stats['total']:,}")
    print(f"  ✅ اجتازت الأمان: {stats['passed_safety']:,}")
    print(f"  ✅ اجتازت التكرار: {stats['passed_dedup']:,}")
    print(f"  ❌ رُفضت (أمان): {stats['rejected_safety']:,}")
    print(f"  ❌ رُفضت (تكرار): {stats['rejected_duplicate']:,}")
    print(f"  ⏱️ الوقت: {elapsed:.2f} ثانية")
    print(f"  🚀 السرعة: {result['samples_per_sec']} عينة/ثانية")
    print(f"  📦 الحجم المضغوط: {compressed_size / (1024*1024):.2f} MB")
    print(f"  🗜️ نسبة الضغط: {result['compression_ratio']*100:.1f}%")
    
    send_telegram(
        f"📊 <b>نتيجة المعالجة:</b>\n"
        f"📝 إجمالي: {stats['total']:,}\n"
        f"✅ أمان: {stats['passed_safety']:,}\n"
        f"✅ فريد: {stats['passed_dedup']:,}\n"
        f"❌ أمان: {stats['rejected_safety']:,}\n"
        f"❌ تكرار: {stats['rejected_duplicate']:,}\n"
        f"⏱️ الوقت: {elapsed:.2f} ث\n"
        f"🚀 السرعة: {result['samples_per_sec']} ع/ث\n"
        f"📦 مضغوط: {compressed_size/(1024*1024):.2f} MB\n"
        f"🗜️ ضغط: {result['compression_ratio']*100:.1f}%"
    )
    
    return result

def predict_daily(download_result: Dict, process_result: Dict):
    print("\n🔮 التنبؤ بالإنتاج اليومي (24 ساعة)")
    
    if download_result.get("status") != "success" or process_result.get("status") == "no_data":
        send_telegram("❌ <b>لا يمكن التنبؤ:</b> بيانات الاختبار غير مكتملة")
        return
    
    samples_per_sec = process_result["samples_per_sec"]
    samples_per_day = samples_per_sec * 86400
    
    compressed_mb_per_sample = process_result["compressed_bytes"] / process_result["passed_dedup"] if process_result["passed_dedup"] > 0 else 0
    compressed_mb_per_day = (samples_per_day * compressed_mb_per_sample) / (1024 * 1024)
    
    download_speed_mbps = download_result.get("speed_mbps", 0)
    daily_download_gb = (download_speed_mbps * 86400) / 1024
    
    report = f"""
🔮 <b>التنبؤ بالإنتاج اليومي (24 ساعة)</b>

📊 <b>بناءً على الاختبار:</b>
• سرعة المعالجة: {samples_per_sec:.2f} عينة/ثانية
• سرعة السحب: {download_speed_mbps:.2f} MB/s
• نسبة الضغط: {process_result['compression_ratio']*100:.1f}%

🎯 <b>التوقعات:</b>
• العينات/يوم: {samples_per_day:,.0f}
• الحجم المضغوط/يوم: {compressed_mb_per_day:,.2f} MB ({compressed_mb_per_day/1024:,.2f} GB)
• السحب الخام/يوم: {daily_download_gb:,.2f} GB

📈 <b>التقييم:</b>
"""
    
    if compressed_mb_per_day >= 20000:
        report += "✅ <b>ممتاز!</b> يتجاوز هدف 20 جيجا"
    elif compressed_mb_per_day >= 10000:
        report += "⚠️ <b>جيد</b> - يحقق 50% من الهدف، يحتاج تحسين"
    elif compressed_mb_per_day >= 1000:
        report += "⚠️ <b>متوسط</b> - يحقق 5% من الهدف، يحتاج توسيع كبير"
    else:
        report += "❌ <b>ضعيف</b> - أقل من 1% من الهدف، يحتاج إعادة تصميم"
    
    print(report)
    send_telegram(report)

if __name__ == "__main__":
    print("=" * 70)
    print("🧪 MARSAD Diagnostic Test - اختبار تشخيصي")
    print("=" * 70)
    
    send_telegram("🚀 <b>بدء الاختبار التشخيصي الشامل</b>\nسيستغرق ~10 دقائق")
    
    download_result = test_hf_download()
    process_result = test_processing(duration_sec=300)
    predict_daily(download_result, process_result)
    
    send_telegram("✅ <b>اكتمل الاختبار التشخيصي</b>")
    print("\n✅ اكتمل الاختبار")
