"""cleanup_hf.py — يحذف مفاتيح HF المكسورة ويوحّد الأسماء."""
import re, json, urllib.request, urllib.error
from pathlib import Path

FILE = Path.home() / ".marsad_secrets" / "all.env"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"

# اقرأ
env = {}
for line in FILE.read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")

def test_hf(key):
    if not key: return None
    try:
        req = urllib.request.Request(
            "https://huggingface.co/api/whoami-v2",
            headers={"Authorization": f"Bearer {key}", "User-Agent": UA})
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read()).get("name", "?")
    except Exception:
        return None

# افحص كل مفاتيح HF
hf_candidates = [k for k in env if k.startswith("HF_TOKEN_") or k in ("HF_TOKEN","HUGGINGFACE_TOKEN","HF_API_KEY")]
print("=== فحص مفاتيح HF ===")
working = {}  # username → (key_name, key_value)
broken_keys = []

for k in hf_candidates:
    v = env.get(k, "")
    if not v:
        print(f"  ⊘ {k}: فارغ — حذف")
        broken_keys.append(k)
        continue
    user = test_hf(v)
    if user:
        if user in working:
            print(f"  ⚠️  {k}: {user} — مكرر (المحفوظ: {working[user][0]}) → حذف")
            broken_keys.append(k)
        else:
            working[user] = (k, v)
            print(f"  ✅ {k}: {user}")
    else:
        print(f"  ❌ {k}: مكسور/منتهي → حذف")
        broken_keys.append(k)

# احذف المكسورة والمكررة
text = FILE.read_text()
for k in broken_keys:
    text = re.sub(rf"^{re.escape(k)}=.*\n?", "", text, flags=re.MULTILINE)

# أعد التسمية: HF_TOKEN_1, HF_TOKEN_2, ...
# أولاً احذف الأسماء القديمة الشغّالة
for user, (k, v) in working.items():
    text = re.sub(rf"^{re.escape(k)}=.*\n?", "", text, flags=re.MULTILINE)

# ثم أضفها بأسماء موحّدة
lines = []
for i, (user, (k, v)) in enumerate(sorted(working.items()), 1):
    lines.append(f"HF_TOKEN_{i}={v}")
    print(f"  → HF_TOKEN_{i} = {user}")

if text and not text.endswith("\n"):
    text += "\n"
text += "\n".join(lines) + "\n"
FILE.write_text(text)

print(f"\n✅ نظّف {len(broken_keys)} مفتاح، أبقى {len(working)} مفتاح شغّال")

# عرض النتيجة
print("\n=== مفاتيح HF النهائية ===")
for line in FILE.read_text().splitlines():
    if line.startswith("HF_TOKEN_") or line in ("HF_TOKEN", "HUGGINGFACE_TOKEN", "HF_API_KEY") or line.startswith("HUGGINGFACE"):
        k = line.split("=")[0]
        print(f"  {k}")
