import json, urllib.request, urllib.error
from pathlib import Path

# اجمع المتغيرات
env = {}
for f in [Path.home()/"storage"/"downloads"/"marsad-dashboard.env.txt",
          Path.home()/"Marsad"/".env"]:
    if f.exists():
        for line in f.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                if k.strip() not in env: env[k.strip()] = v.strip().strip('"').strip("'")

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"

def get(url, h=None):
    req = urllib.request.Request(url, headers={**(h or {}), "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"_error": f"HTTP {e.code}", "_body": e.read(300).decode()[:200]}
    except Exception as e:
        return {"_error": str(e)[:100]}

print("=== OpenRouter models (free) ===")
d = get("https://openrouter.ai/api/v1/models")
if "_error" in d: print(f"  ❌ {d}")
else:
    for m in d.get("data", [])[:40]:
        if ":free" in m["id"]:
            print(f"  {m['id']}")

print("\n=== Google models ===")
k = env.get("GOOGLE_API_KEY")
if k:
    d = get(f"https://generativelanguage.googleapis.com/v1beta/models?key={k}")
    if "_error" in d: print(f"  ❌ {d}")
    else:
        for m in d.get("models", [])[:20]:
            if "generateContent" in m.get("supportedGenerationMethods", []):
                print(f"  {m['name']}")
