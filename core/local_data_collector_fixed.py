import requests, json, os
from pathlib import Path

# المفاتيح الحقيقية
KEYS = {
    "Groq": "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",
    "OpenRouter": "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"
}

OUTPUT_FILE = Path.home() / "Marsad_Security_Tests" / "Dar_Security_Tests" / "live_collected_data.jsonl"
OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

def collect(provider, prompt):
    print(f"🔄 [{provider}] جاري الاتصال...")
    headers = {
        "Authorization": f"Bearer {KEYS[provider]}", 
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost", # مطلوب لـ OpenRouter
        "X-Title": "Marsad Project"
    }
    
    if provider == "Groq":
        url = "https://api.groq.com/openai/v1/chat/completions"
        payload = {
            "model": "llama3-8b-8192", 
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7
        }
    else: # OpenRouter
        url = "https://openrouter.ai/api/v1/chat/completions"
        payload = {
            "model": "google/gemma-2-9b-it:free", # نموذج مجاني ومضمون
            "messages": [{"role": "user", "content": prompt}]
        }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=20)
        
        # طبقة التصحيح
        if resp.status_code != 200:
            print(f"⚠️ تفاصيل الخطأ من {provider}: {resp.status_code}")
            print(f"   الرد: {resp.text[:150]}")
            return False

        content = resp.json()['choices'][0]['message']['content']
        with open(OUTPUT_FILE, 'a') as f:
            f.write(json.dumps({"prompt": prompt, "response": content}) + '\n')
        print(f"✅ تم الجمع والحفظ بنجاح.")
        return True
        
    except Exception as e:
        print(f"❌ خطأ في الاتصال: {e}")
        return False

# مهام الجمع
tasks = [
    ("Groq", "Write a Python function to validate email addresses using regex."),
    ("OpenRouter", "What is the difference between Symmetric and Asymmetric encryption?")
]

print("🚀 بدء الجمع المحلي المصحح...")
success_count = 0
for p, t in tasks:
    if collect(p, t):
        success_count += 1

if success_count > 0:
    print(f"\n💾 تم حفظ {success_count} سجلات في: {OUTPUT_FILE}")
    # تشغيل المعالجة فوراً إذا نجحنا
    os.system("python ~/Marsad/core/full_pipeline_runner.py")
else:
    print("\n❌ فشل الجمع. يرجى التحقق من اتصال الإنترنت أو صلاحية المفاتيح.")
