import requests, json, os
from pathlib import Path

OR_KEY = "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"
OUTPUT_FILE = Path.home() / "Marsad_Security_Tests" / "Dar_Security_Tests" / "live_collected_data.jsonl"
OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

def collect(prompt):
    print(f"🔄 [OpenRouter] إرسال الطلب باستخدام Llama-3...")
    headers = {
        "Authorization": f"Bearer {OR_KEY}", 
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost",
        "X-Title": "Marsad Project"
    }
    
    # الاسم الصحيح والمضمون لنموذج مجاني
    payload = {
        "model": "meta-llama/llama-3-8b-instruct:free", 
        "messages": [{"role": "user", "content": prompt}]
    }
    
    try:
        resp = requests.post("https://openrouter.ai/api/v1/chat/completions", json=payload, headers=headers, timeout=30)
        
        if resp.status_code == 200:
            content = resp.json()['choices'][0]['message']['content']
            print(f"✅ نجاح! تم استخراج الرد.")
            
            entry = {"prompt": prompt, "response": content, "source": "OpenRouter-Llama3"}
            with open(OUTPUT_FILE, 'a') as f:
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')
            return True
        else:
            print(f"❌ فشل ({resp.status_code}): {resp.text[:100]}")
            return False
    except Exception as e:
        print(f"❌ خطأ اتصال: {e}")
        return False

print("🚀 بدء الجمع النهائي...")
if collect("What is SQL Injection and how to prevent it in Python?"):
    print("\n💾 تم الحفظ. جاري تشغيل المعالجة...")
    os.system("python ~/Marsad/core/full_pipeline_runner.py")
else:
    print("\n⚠️ تأكد من اتصال الإنترنت وحاول مرة أخرى.")
