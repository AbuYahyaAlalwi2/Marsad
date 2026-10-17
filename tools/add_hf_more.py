"""add_hf_more.py — يضيف مفاتيح HF بأي عدد.
الاستخدام:
  python3 add_hf_more.py       ← يضيف واحداً واحداً حتى تكتب stop
"""
import re, json, urllib.request, urllib.error
from pathlib import Path

FILE = Path.home() / ".marsad_secrets" / "all.env"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"

if not FILE.exists():
    print(f"❌ الملف غير موجود: {FILE}")
    exit(1)

# اكتشف الأرقام المستخدمة
existing = set()
for line in FILE.read_text().splitlines():
    m = re.match(r"^HF_TOKEN_(\d+)=", line.strip())
    if m:
        existing.add(int(m.group(1)))

nxt = max(existing) + 1 if existing else 1
print(f"📝 الملف: {FILE}")
print(f"🔑 موجود: {sorted(existing)}")
print(f"🔢 سيبدأ من HF_TOKEN_{nxt}\n")
print("اكتب 'stop' للتوقف، 'skip' لتخطي رقم، أو الصق المفتاح ثم Enter.\n")

def add(key, val):
    text = FILE.read_text()
    pat = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
    line = f"{key}={val}"
    if pat.search(text):
        text = pat.sub(line, text)
    else:
        if not text.endswith("\n"): text += "\n"
        text += line + "\n"
    FILE.write_text(text)

def test_hf(key):
    try:
        req = urllib.request.Request(
            "https://huggingface.co/api/whoami-v2",
            headers={"Authorization": f"Bearer {key}", "User-Agent": UA})
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read()).get("name", "?")
    except Exception as e:
        return None

while True:
    key_name = f"HF_TOKEN_{nxt}"
    print(f"[{nxt}] {key_name}:")
    val = input("  > ").strip()

    if val.lower() == "stop":
        print("  ⊘ توقف")
        break
    if val.lower() == "skip":
        print(f"  ⊘ تخطي {key_name}")
        nxt += 1
        continue
    if not val:
        print("  ⚠️  فارغ — أعد الإدخال")
        continue

    print("  → فحص المفتاح...")
    user = test_hf(val)
    if user:
        add(key_name, val)
        print(f"  ✅ {key_name} → {user} [مُضاف]")
        nxt += 1
    else:
        print("  ❌ المفتاح لا يعمل — أعد المحاولة أو اكتب skip")

# عرض النتيجة
text = FILE.read_text()
print("\n=== مفاتيح HF النهائية ===")
for line in text.splitlines():
    if re.match(r"^HF_TOKEN_\d+=", line):
        k = line.split("=")[0]
        print(f"  {k}")
