"""
Full Pipeline Runner - Qwen Task
يشغل: الجمع، المعالجة، والتحقق من الجاهزية للرفع
"""

import json, os
from pathlib import Path

DATA_FILE = Path.home() / "Marsad_Security_Tests" / "Dar_Security_Tests" / "live_collected_data.jsonl"
PROCESSED_FILE = Path.home() / "Marsad_Security_Tests" / "Dar_Security_Tests" / "processed_training_data.jsonl"

def run_pipeline():
    print("🚀 بدء تشغيل خط الأنابيب الكامل...")
    
    # 1. التحقق من وجود بيانات مجمعة
    if not DATA_FILE.exists():
        print("❌ لا توجد بيانات مجمعة بعد. شغّل data_collector.py أولاً.")
        return

    # 2. المعالجة (التنظيف والتنسيق)
    print("🔄 جاري معالجة البيانات وتنسيقها...")
    count = 0
    with open(DATA_FILE, 'r') as f_in, open(PROCESSED_FILE, 'w') as f_out:
        for line in f_in:
            try:
                data = json.loads(line)
                # تنسيق نهائي للتدريب
                entry = {
                    "messages": [
                        {"role": "user", "content": data.get("prompt", "")},
                        {"role": "assistant", "content": data.get("response", "")}
                    ]
                }
                f_out.write(json.dumps(entry, ensure_ascii=False) + '\n')
                count += 1
            except: continue
            
    print(f"✅ تمت معالجة {count} سجل تدريبي بنجاح.")
    
    # 3. التحقق من الجاهزية للرفع
    if count > 0:
        print(f"💾 الملف جاهز للرفع: {PROCESSED_FILE}")
        print("📊 الحجم: ", os.path.getsize(PROCESSED_FILE), " bytes")
        print("\n🎉 النظام جاهز تماماً! يمكنك الآن رفع هذا الملف لمستودع Hugging Face الخاص بك.")
    else:
        print("⚠️ لم يتم العثور على سجلات صالحة.")

if __name__ == "__main__":
    run_pipeline()
