import json, urllib.request, urllib.error
from pathlib import Path

env = {}
for f in [Path.home()/"storage"/"downloads"/"marsad-dashboard.env.txt",
          Path.home()/"Marsad"/".env"]:
    if f.exists():
        for line in f.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                if k.strip() not in env: env[k.strip()] = v.strip().strip('"').strip("'")

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"

def test_google(model, key):
    body = json.dumps({"contents":[{"parts":[{"text":"say hi"}]}]}).encode()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    try:
        req = urllib.request.Request(url, data=body, method="POST",
                                     headers={"Content-Type":"application/json","User-Agent":UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            d = json.loads(r.read())
            return "✅", d["candidates"][0]["content"]["parts"][0]["text"][:50]
    except urllib.error.HTTPError as e:
        return f"❌ {e.code}", e.read(150).decode()[:100]
    except Exception as e:
        return "❌", str(e)[:60]

def test_openrouter(model, key):
    body = json.dumps({"model": model,
                       "messages":[{"role":"user","content":"say hi"}],
                       "max_tokens":5}).encode()
    try:
        req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions",
                                     data=body, method="POST",
                                     headers={"Authorization": f"Bearer {key}",
                                              "Content-Type":"application/json",
                                              "User-Agent":UA})
        with urllib.request.urlopen(req, timeout=25) as r:
            d = json.loads(r.read())
            return "✅", d["choices"][0]["message"]["content"][:40]
    except urllib.error.HTTPError as e:
        return f"❌ {e.code}", e.read(150).decode()[:100]
    except Exception as e:
        return "❌", str(e)[:60]

print("=== Google — تجربة 5 موديلات ===")
k = env.get("GOOGLE_API_KEY")
for m in ["gemini-3.1-flash-lite", "gemini-2.5-flash", "gemini-flash-latest",
          "gemini-2.5-flash-lite", "gemini-2.0-flash"]:
    s, msg = test_google(m, k)
    print(f"  {s:8s} {m:30s} {msg}")

print("\n=== OpenRouter ===")
k = env.get("OPENROUTER_API_KEY")
for m in ["apodex/apodex-1.1-mini:free",
          "deepseek/deepseek-r1:free",
          "meta-llama/llama-3.3-70b-instruct:free"]:
    s, msg = test_openrouter(m, k)
    print(f"  {s:8s} {m:45s} {msg}")
