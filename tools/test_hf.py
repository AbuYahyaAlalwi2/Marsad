import re, json, urllib.request, urllib.error
from pathlib import Path

FILE = Path.home() / "storage" / "downloads" / "marsad-dashboard.env.txt"
keys = {}
for line in FILE.read_text().splitlines():
    m = re.match(r"^(HF_TOKEN_\d+)=(.+)$", line.strip())
    if m:
        keys[m.group(1)] = m.group(2).strip().strip('"').strip("'")

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
print(f"فحص {len(keys)} مفتاح HF\n")

ok = 0
for name, key in sorted(keys.items(), key=lambda x: int(x[0].split("_")[-1])):
    req = urllib.request.Request("https://huggingface.co/api/whoami-v2",
                                 headers={"Authorization": f"Bearer {key}",
                                          "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            d = json.loads(r.read())
            print(f"  ✅ {name:15s} → {d.get('name', '?')}")
            ok += 1
    except urllib.error.HTTPError as e:
        print(f"  ❌ {name:15s} → HTTP {e.code}")
    except Exception as e:
        print(f"  ❌ {name:15s} → {str(e)[:50]}")

print(f"\n=== {ok}/{len(keys)} مفتاح يعمل ===")
