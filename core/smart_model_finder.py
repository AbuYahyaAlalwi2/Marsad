import requests, json, os
from pathlib import Path

OR_KEY = "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"
OUTPUT_FILE = Path.home() / "Marsad_Security_Tests" / "Dar_Security_Tests" / "live_collected_data.jsonl"

def get_free_model():
    print("🔍 جاري البحث عن نموذج مجاني نشط على OpenRouter...")
    try:
        resp = requests.get("https://openrouter.ai/api/v1/models", timeout=10)
        models = resp.json()['data']
        # البحث عن نموذج مجاني (free) وموثوق
        for m in models:
            if m['id'].endswith(':free') and 'llama' in m['id']:
                print(f"✅ تم العثور على نموذج نشط: {m['id']}")
                return m['id']
        # إذا لم نجد Llama، نأخذ أي نموذج مجاني
        for m in models:
            if m['id'].endswith(':free'):
                return m['id']
        return None
    except Exception as e:
        print(f"❌ فشل جلب القائمة: {e}")
        return None

def collect_with_model(model_id):
    print(f"🔄 استخدام النموذج: {model_id}")
    headers = {
        "Authorization": f"Bearer {OR_KEY}", 
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost",
        "X-Title": "Marsad Project"
    }
    payload = {
        "model": model_id, 
        "messages": [{"role": "user", "content": "Explain SQL Injection briefly."}]
    }
    
    try:
        resp = requests.post("https://openrouter.ai/api/v1/chat/completions", json=payload, headers=headers, timeout=30)
        if resp.status_code == 200:
            content = resp.json()['choices'][0]['message']['content']
            print(f"✅ نجاح! تم جمع البيانات.")
            
            entry = {"prompt": "SQL Injection Explanation", "response": content, "source": model_id}
            with open(OUTPUT_FILE, 'a') as f:
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')
            
            print(f"💾 تم الحفظ في: {OUTPUT_FILE}")
            return True
        else:
            print(f"❌ فشل ({resp.status_code}): {resp.text[:100]}")
            return False
    except Exception as e:
        print(f"❌ خطأ: {e}")
        return False

# التنفيذ
model = get_free_model()
if model:
    collect_with_model(model)
else:
    print("⚠️ لم يتم العثور على نماذج مجانية حالياً.")
