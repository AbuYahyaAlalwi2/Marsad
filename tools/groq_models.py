import re, json, urllib.request, urllib.error
from pathlib import Path

FILE = Path.home() / "storage" / "downloads" / "marsad-dashboard.env.txt"
if not FILE.exists():
    FILE = Path("/sdcard/Download/marsad-dashboard.env.txt")

keys = {}
for line in FILE.read_text().splitlines():
    m = re.match(r"^(GROQ_API_KEY_\d+)=(.+)$", line.strip())
    if m:
        keys[m.group(1)] = m.group(2).strip().strip('"').strip("'")

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

# 1. الموديلات المتاحة
k = list(keys.values())[0]
req = urllib.request.Request(
    "https://api.groq.com/openai/v1/models",
    headers={"Authorization": f"Bearer {k}", "User-Agent": UA})
try:
    with urllib.request.urlopen(req, timeout=15) as r:
        d = json.loads(r.read())
    print("=== الموديلات المتاحة ===")
    for m in d.get("data", []):
        print(f"  {m['id']}")
except urllib.error.HTTPError as e:
    print(f"❌ HTTP {e.code}: {e.read(200).decode()[:200]}")

# 2. اختبار كل مفتاح بموديل صحيح
print("\n=== فحص 6 مفاتيح ===")
MODEL = "llama-3.3-70b-versatile"

def check(key):
    body = json.dumps({"model": MODEL,
                       "messages": [{"role":"user","content":"1"}],
                       "max_tokens": 3}).encode()
    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=body, method="POST",
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json",
                 "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return "✅", "OK"
    except urllib.error.HTTPError as e:
        return f"❌ {e.code}", e.read(150).decode()[:80]
    except Exception as e:
        return "❌", str(e)[:60]

ok = 0
for name, key in sorted(keys.items()):
    s, msg = check(key)
    if "✅" in s: ok += 1
    print(f"  {s:10s} {name:18s} {msg}")
print(f"\n=== {ok}/6 يعمل ===")
