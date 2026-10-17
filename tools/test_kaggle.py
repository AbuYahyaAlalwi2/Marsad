"""test_kaggle.py — يفحص كل أزواج Kaggle (USERNAME + KEY) ويحذف المكسورة."""
import re, json, base64, urllib.request, urllib.error
from pathlib import Path

FILE = Path.home() / ".marsad_secrets" / "all.env"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"

# اقرأ
env = {}
for line in FILE.read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")

# اكتشف الأزواج
users = {}
keys = {}
for k, v in env.items():
    m = re.match(r"^KAGGLE_USERNAME_(\d+)$", k)
    if m: users[int(m.group(1))] = v
    m = re.match(r"^KAGGLE_KEY_(\d+)$", k)
    if m: keys[int(m.group(1))] = v

indices = sorted(set(users.keys()) & set(keys.keys()))
print(f"فحص {len(indices)} زوج Kaggle\n")

def test_kaggle(username, key):
    """يختبر زوج Kaggle — يُرجع (ok, message)"""
    if not username or not key:
        return False, "فارغ"
    creds = base64.b64encode(f"{username}:{key}".encode()).decode()
    req = urllib.request.Request(
        "https://www.kaggle.com/api/v1/datasets/list?page=1",
        headers={"Authorization": f"Basic {creds}", "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return True, f"HTTP {r.status}"
    except urllib.error.HTTPError as e:
        if e.code == 401: return False, "401 — مصادقة خاطئة"
        if e.code == 403: return False, "403 — منتهي/محظور"
        return False, f"HTTP {e.code}"
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)[:50]}"

working = []
broken = []
for i in indices:
    u = users[i]
    k = keys[i]
    ok, msg = test_kaggle(u, k)
    status = "✅" if ok else "❌"
    print(f"  {status} USERNAME_{i} = {u:20s} → {msg}")
    if ok:
        working.append(i)
    else:
        broken.append(i)

print(f"\n=== {len(working)}/{len(indices)} يعمل ===")

# احذف المكسورة من الملف
if broken:
    text = FILE.read_text()
    for i in broken:
        text = re.sub(rf"^KAGGLE_USERNAME_{i}=.*\n?", "", text, flags=re.MULTILINE)
        text = re.sub(rf"^KAGGLE_KEY_{i}=.*\n?", "", text, flags=re.MULTILINE)
    FILE.write_text(text)
    print(f"\n🗑️  حُذف {len(broken)} زوج مكسور: {broken}")

# عرض الباقي
print(f"\n=== Kaggle النهائي ===")
for line in FILE.read_text().splitlines():
    if line.startswith("KAGGLE_USERNAME_") or line.startswith("KAGGLE_KEY_"):
        print(f"  {line.split('=')[0]}")
