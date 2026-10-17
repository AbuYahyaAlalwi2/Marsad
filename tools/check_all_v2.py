import re, json, urllib.request, urllib.error
from pathlib import Path

# اقرأ من كل الملفات
FILES = [
    Path.home() / "storage" / "downloads" / "marsad-dashboard.env.txt",
    Path.home() / "Marsad" / ".env",
    Path.home() / ".marsad_secrets" / "render.env",
    Path.home() / ".marsad_secrets" / "llm_endpoint.env",
]
env = {}
for f in FILES:
    if not f.exists(): continue
    for line in f.read_text().splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            k = k.strip()
            if k not in env:  # الأولوية للأول
                env[k] = v.strip().strip('"').strip("'")

print(f"=== قرأت {len(env)} متغير من {sum(f.exists() for f in FILES)} ملف ===\n")

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
        return f"❌ {name}: HTTP {e.code} — {e.read(150).decode()[:100]}"
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

print("=== 1. DeepSeek ===")
if env.get("DEEPSEEK_API_KEY"):
    print(" " + post_chat("DEEPSEEK", "https://api.deepseek.com/v1/chat/completions",
                          env["DEEPSEEK_API_KEY"], "deepseek-chat"))
else: print("  ❌ مفقود")

print("\n=== 2. OpenRouter ===")
if env.get("OPENROUTER_API_KEY"):
    print(" " + get("OpenRouter auth", "https://openrouter.ai/api/v1/auth/key",
              {"Authorization": f"Bearer {env['OPENROUTER_API_KEY']}"}))
    print(" " + post_chat("OpenRouter chat", "https://openrouter.ai/api/v1/chat/completions",
                          env["OPENROUTER_API_KEY"],
                          "meta-llama/llama-3.3-70b-instruct:free"))
else: print("  ❌ مفقود")

print("\n=== 3. Google ===")
if env.get("GOOGLE_API_KEY"):
    print(" " + get("Google models", f"https://generativelanguage.googleapis.com/v1beta/models?key={env['GOOGLE_API_KEY']}"))
    body = json.dumps({"contents":[{"parts":[{"text":"say hi"}]}]}).encode()
    try:
        req = urllib.request.Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={env['GOOGLE_API_KEY']}",
            data=body, method="POST", headers={"Content-Type":"application/json","User-Agent":UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            d = json.loads(r.read())
            print(f" ✅ GOOGLE chat: {d['candidates'][0]['content']['parts'][0]['text'][:30]}")
    except urllib.error.HTTPError as e:
        print(f" ❌ GOOGLE chat: HTTP {e.code} — {e.read(200).decode()[:120]}")
    except Exception as e:
        print(f" ❌ GOOGLE chat: {type(e).__name__}: {str(e)[:60]}")
else: print("  ❌ مفقود")

print("\n=== 4. Saturn (endpoints متعددة) ===")
saturn = {k: v for k, v in env.items() if k.startswith("SATURN_API_KEY")}
if not saturn:
    print("  ❌ لا مفاتيح Saturn")
else:
    for name, key in sorted(saturn.items())[:1]:  # مفتاح واحد للتجربة
        print(f"  {name}:")
        for url, hdr in [
            ("https://api.saturncloud.io/v1/me", {"Authorization": f"Bearer {key}"}),
            ("https://api.saturncloud.io/api/v1/me", {"Authorization": f"Bearer {key}"}),
            ("https://saturncloud.io/api/me", {"Authorization": f"Bearer {key}"}),
            ("https://api.saturncloud.io/s/me", {"Authorization": f"Bearer {key}"}),
        ]:
            print(f"    {url}")
            print(f"      → {get('', url, hdr)}")

print("\n=== 5. NVD ===")
if env.get("NVD_API_KEY"):
    print(" " + get("NVD", "https://services.nvd.nist.gov/rest/json/cves/2.0?resultsPerPage=1",
              {"apiKey": env["NVD_API_KEY"]}))
