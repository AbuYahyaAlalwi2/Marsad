import re, json, urllib.request, urllib.error
from pathlib import Path

FILE = Path.home() / "storage" / "downloads" / "marsad-dashboard.env.txt"
env = {}
for line in FILE.read_text().splitlines():
    line = line.strip()
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"

def post_chat(name, url, key, model, extra_headers=None):
    body = json.dumps({"model": model,
                       "messages": [{"role":"user","content":"say hi"}],
                       "max_tokens": 5}).encode()
    h = {"Authorization": f"Bearer {key}", "Content-Type": "application/json",
         "User-Agent": UA}
    if extra_headers: h.update(extra_headers)
    try:
        req = urllib.request.Request(url, data=body, method="POST", headers=h)
        with urllib.request.urlopen(req, timeout=20) as r:
            d = json.loads(r.read())
            content = d.get("choices",[{}])[0].get("message",{}).get("content","")[:30]
            return f"✅ {name}: {content}"
    except urllib.error.HTTPError as e:
        msg = e.read(200).decode()[:120]
        return f"❌ {name}: HTTP {e.code} — {msg}"
    except Exception as e:
        return f"❌ {name}: {type(e).__name__}: {str(e)[:60]}"

def get(name, url, headers=None):
    h = {**(headers or {}), "User-Agent": UA}
    try:
        req = urllib.request.Request(url, headers=h)
        with urllib.request.urlopen(req, timeout=15) as r:
            return f"✅ {name}: {r.status}"
    except urllib.error.HTTPError as e:
        return f"{'✅' if e.code in (200,201) else '❌'} {name}: HTTP {e.code}"
    except Exception as e:
        return f"❌ {name}: {type(e).__name__}: {str(e)[:50]}"

print("=== 1. DeepSeek ===\n")
if env.get("DEEPSEEK_API_KEY"):
    print(post_chat("DEEPSEEK", "https://api.deepseek.com/v1/chat/completions",
                    env["DEEPSEEK_API_KEY"], "deepseek-chat"))
else:
    print("  ❌ DEEPSEEK_API_KEY مفقود")

print("\n=== 2. OpenRouter ===\n")
if env.get("OPENROUTER_API_KEY"):
    print(get("OPENROUTER (auth/key)", "https://openrouter.ai/api/v1/auth/key",
              {"Authorization": f"Bearer {env['OPENROUTER_API_KEY']}"}))
    print(post_chat("OPENROUTER chat", "https://openrouter.ai/api/v1/chat/completions",
                    env["OPENROUTER_API_KEY"],
                    "meta-llama/llama-3.3-70b-instruct:free"))
else:
    print("  ❌ OPENROUTER_API_KEY مفقود")

print("\n=== 3. Google AI Studio ===\n")
if env.get("GOOGLE_API_KEY"):
    print(get("GOOGLE models", f"https://generativelanguage.googleapis.com/v1beta/models?key={env['GOOGLE_API_KEY']}"))
    body = json.dumps({"contents":[{"parts":[{"text":"say hi"}]}]}).encode()
    try:
        req = urllib.request.Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={env['GOOGLE_API_KEY']}",
            data=body, method="POST", headers={"Content-Type":"application/json","User-Agent":UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            d = json.loads(r.read())
            text = d["candidates"][0]["content"]["parts"][0]["text"][:30]
            print(f"✅ GOOGLE chat: {text}")
    except urllib.error.HTTPError as e:
        print(f"❌ GOOGLE chat: HTTP {e.code} — {e.read(150).decode()[:100]}")
    except Exception as e:
        print(f"❌ GOOGLE chat: {type(e).__name__}: {str(e)[:60]}")
else:
    print("  ❌ GOOGLE_API_KEY مفقود")

print("\n=== 4. Saturn Cloud ===\n")
saturn_keys = {k: v for k, v in env.items() if k.startswith("SATURN_API_KEY")}
if not saturn_keys:
    print("  ❌ لا توجد مفاتيح Saturn في الملف")
else:
    for name, key in sorted(saturn_keys.items()):
        print(get(f"{name}", "https://api.saturncloud.io/v1/me",
                  {"Authorization": f"Bearer {key}"}))

print("\n=== 5. مزودون آخرون إن وُجدوا ===\n")
for alt in ["CEREBRAS_API_KEY", "TOGETHER_API_KEY", "FIREWORKS_API_KEY",
            "MISTRAL_API_KEY", "NVIDIA_API_KEY", "QIANFAN_API_KEY",
            "MOONSHOT_API_KEY", "COHERE_API_KEY", "PERPLEXITY_API_KEY"]:
    if env.get(alt):
        print(f"  🔑 {alt} موجود (لم يُختبر)")
