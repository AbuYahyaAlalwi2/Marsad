import re
from pathlib import Path

FILE = Path.home() / "storage" / "downloads" / "marsad-dashboard.env.txt"
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

print(f"📝 {FILE}\n")
while True:
    val = input("[6/6] GROQ_API_KEY_6 (الصق المفتاح ثم Enter): ").strip()
    if val:
        add("GROQ_API_KEY_6", val)
        break
    print("  ⚠️  فارغ — أعد الإدخال")

print(f"\n✅ تم")
