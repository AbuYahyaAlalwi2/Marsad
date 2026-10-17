"""test_groq.py — يفحص كل مفاتيح Groq في الملف."""
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

print(f"فحص {len(keys)} مفتاح...\n")

def check(name, key):
    body = json.dumps({
        "model": "llama-3.1-8b-instant",
        "messages": [{"role": "user", "content": "1"}],
        "max_tokens": 3,
    }).encode()
    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=body, method="POST",
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            d = json.loads(r.read())
            return "✅", d.get("model", "?")
    except urllib.error.HTTPError as e:
        body = e.read(200).decode() if hasattr(e, "read") else ""
        if e.code == 401: return "❌ مصادقة", "key invalid"
        if e.code == 429: return "⚠️  حد", "rate limit"
        return f"❌ HTTP {e.code}", body[:60]
    except Exception as e:
        return "❌", str(e)[:60]

working = 0
for name, key in sorted(keys.items()):
    s, msg = check(name, key)
    if s == "✅": working += 1
    print(f"  {s:12s} {name:18s} {msg}")

print(f"\n=== {working}/{len(keys)} مفتاح يعمل ===")
