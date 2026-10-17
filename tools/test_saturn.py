import re, json, urllib.request, urllib.error
from pathlib import Path

# اقرأ المفاتيح
FILE = Path.home() / "storage" / "downloads" / "marsad-dashboard.env.txt"
env = {}
for f in [FILE, Path.home()/"Marsad"/".env"]:
    if f.exists():
        for line in f.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                if k.strip() not in env:
                    env[k.strip()] = v.strip().strip('"').strip("'")

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"

# ابحث عن BASE_URL
base = env.get("SATURN_BASE_URL", "").rstrip("/")
if not base:
    print("❌ SATURN_BASE_URL غير موجود في الملف")
    print("   أضفه: SATURN_BASE_URL=https://app.community.saturnenterprise.io")
    print("   (أو رابط حسابك الخاص)")
    exit(0)

print(f"Base URL: {base}\n")

def call(name, path, token):
    url = f"{base}{path}"
    try:
        req = urllib.request.Request(url,
            headers={"Authorization": f"token {token}",  # ← token وليس Bearer
                     "User-Agent": UA,
                     "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as r:
            d = json.loads(r.read())
            return f"✅ {name}: {str(d)[:100]}"
    except urllib.error.HTTPError as e:
        body = e.read(200).decode()[:120] if hasattr(e, "read") else ""
        return f"❌ {name}: HTTP {e.code} — {body}"
    except Exception as e:
        return f"❌ {name}: {type(e).__name__}: {str(e)[:60]}"

for i in range(1, 7):
    key = env.get(f"SATURN_API_KEY_{i}")
    if not key: continue
    print(f"=== SATURN_API_KEY_{i} ===")
    print(" " + call("status", "/api/status", key))
    print(" " + call("resources", "/api/active/resources", key))
    print()
