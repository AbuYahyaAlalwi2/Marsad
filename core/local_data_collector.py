import requests, json, os
from pathlib import Path

# المفاتيح الحقيقية
KEYS = {
    "Groq": "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",
    "OpenRouter": "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"
}

OUTPUT_FILE = Path.home() / "Marsad_Security_Tests" / "Dar_Security_Tests" / "live_collected_data.jsonl"

def collect(provider, prompt):
    print(f"🔄 [{provider}] جاري الجمع...")
    headers = {"Authorization": f"Bearer {KEYS[provider]}", "Content-Type": "application/json"}
    
    if provider == "Groq":
        url = "https://api.groq.com/openai/v1/chat/completions"
        payload = {"model": "llama3-8b-8192", "messages": [{"role": "user", "content": prompt}]}
    else:
        url = "https://openrouter.ai/api/v1/chat/completions"
        payload = {"model": "mistralai/mistral-7b-instruct:free", "messages": [{"role": "user", "content": prompt}]}

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=20)
        if resp.status_code == 200:
            content = resp.json()['choices'][0]['message']['content']
            with open(OUTPUT_FILE, 'a') as f:
                f.write(json.dumps({"prompt": prompt, "response": content}) + '\n')
            print(f"✅ تم الحفظ.")
        else:
            print(f"❌ فشل ({resp.status_code})")
    except Exception as e:
        print(f"❌ خطأ: {e}")

# مهام الجمع
tasks = [
    ("Groq", "Generate a Python code for SQL Injection and its fix."),
    ("OpenRouter", "Explain XSS vulnerability with an example.")
]

print("🚀 بدء الجمع المحلي...")
for p, t in tasks:
    collect(p, t)
print(f"💾 البيانات محفوظة في: {OUTPUT_FILE}")
