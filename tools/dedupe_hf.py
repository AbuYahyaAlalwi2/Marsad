"""dedupe_hf.py — يحذف مفاتيح HF المكررة (نفس الحساب) ويعيد الترقيم."""
import re, json, urllib.request, urllib.error
from pathlib import Path

FILE = Path.home() / ".marsad_secrets" / "all.env"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"

def who(key):
    try:
        req = urllib.request.Request("https://huggingface.co/api/whoami-v2",
                                     headers={"Authorization": f"Bearer {key}", "User-Agent": UA})
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read()).get("name", "?")
    except Exception:
        return None

text = FILE.read_text()
keys = {}
for line in text.splitlines():
    m = re.match(r"^(HF_TOKEN_\d+)=(.+)$", line.strip())
    if m:
        keys[m.group(1)] = m.group(2).strip().strip('"').strip("'")

print(f"=== فحص {len(keys)} مفتاح ===")
# اجمع حسب الحساب — احتفظ بالأول فقط
by_user = {}
for name, key in sorted(keys.items(), key=lambda x: int(x[0].split("_")[-1])):
    u = who(key)
    if not u:
        print(f"  ❌ {name}: مكسور → سيُحذف")
        continue
    if u in by_user:
        print(f"  ⊘ {name}: {u} (مكرر — محفوظ: {by_user[u][0]}) → سيُحذف")
    else:
        by_user[u] = (name, key)
        print(f"  ✅ {name}: {u} → يُبقى")

# احذف كل مفاتيح HF القديمة
clean = re.sub(r"^HF_TOKEN_\d+=.*\n?", "", text, flags=re.MULTILINE)

# أعد الإضافة بأسماء موحّدة
new_lines = []
print(f"\n=== المفاتيح النهائية ===")
for i, (u, (old_name, key)) in enumerate(sorted(by_user.items()), 1):
    new_name = f"HF_TOKEN_{i}"
    new_lines.append(f"{new_name}={key}")
    print(f"  {new_name} → {u}  (كان {old_name})")

if clean and not clean.endswith("\n"):
    clean += "\n"
clean += "\n".join(new_lines) + "\n"
FILE.write_text(clean)

print(f"\n✅ أُبقِي {len(by_user)} مفتاح نظيف")
