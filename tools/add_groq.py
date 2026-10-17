"""add_groq.py — إضافة 5 مفاتيح Groq بشكل تفاعلي."""
import re
from pathlib import Path

FILE = Path.home() / "storage" / "downloads" / "marsad-dashboard.env.txt"
# لو ما وجد — جرب /sdcard/Download
if not FILE.exists():
    FILE = Path("/sdcard/Download/marsad-dashboard.env.txt")

def add(key, val):
    text = FILE.read_text() if FILE.exists() else ""
    pat = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
    line = f"{key}={val}"
    if pat.search(text):
        text = pat.sub(line, text)
        print(f"  ✓ {key} [مُحدَّث]")
    else:
        if text and not text.endswith("\n"):
            text += "\n"
        text += line + "\n"
        print(f"  ✓ {key} [مُضاف]")
    FILE.write_text(text)

if not FILE.exists():
    print(f"❌ الملف غير موجود: {FILE}")
    exit(1)

print(f"📝 الملف: {FILE}\n")
for i in range(1, 6):
    key = f"GROQ_API_KEY_{i}"
    while True:
        val = input(f"[{i}/5] {key} (الصق المفتاح ثم Enter): ").strip()
        if val:
            add(key, val)
            break
        print("  ⚠️  فارغ — أعد الإدخال")

print(f"\n✅ تم إضافة 5 مفاتيح Groq إلى {FILE}")
