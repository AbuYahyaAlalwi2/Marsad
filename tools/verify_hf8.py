import re, json, urllib.request, urllib.error
from pathlib import Path

FILE = Path.home() / ".marsad_secrets" / "all.env"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"

keys = {}
for line in FILE.read_text().splitlines():
    m = re.match(r"^(HF_TOKEN_\d+)=(.+)$", line.strip())
    if m:
        keys[m.group(1)] = m.group(2).strip().strip('"').strip("'")

print(f"فحص {len(keys)} مفتاح HF\n")
ok, users = 0, {}
for name, key in sorted(keys.items(), key=lambda x: int(x[0].split("_")[-1])):
    try:
        req = urllib.request.Request("https://huggingface.co/api/whoami-v2",
                                     headers={"Authorization": f"Bearer {key}", "User-Agent": UA})
        with urllib.request.urlopen(req, timeout=15) as r:
            d = json.loads(r.read())
            u = d.get("name", "?")
            users.setdefault(u, []).append(name)
            print(f"  ✅ {name:14s} → {u}")
            ok += 1
    except urllib.error.HTTPError as e:
        print(f"  ❌ {name:14s} → HTTP {e.code}")
    except Exception as e:
        print(f"  ❌ {name:14s} → {str(e)[:50]}")

print(f"\n=== {ok}/{len(keys)} يعمل ===")
if users:
    print("\nحسابات فريدة:")
    for u, ks in users.items():
        print(f"  {u}: {', '.join(ks)}")
