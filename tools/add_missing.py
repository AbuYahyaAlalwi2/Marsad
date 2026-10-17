"""add_missing.py — يضيف المفاتيح الناقصة تفاعلياً إلى all.env."""
import re, sys
from pathlib import Path

FILE = Path.home() / ".marsad_secrets" / "all.env"

if not FILE.exists():
    print(f"❌ الملف غير موجود: {FILE}")
    print("   شغّل unify_keys.py أولاً")
    sys.exit(1)

MISSING = [
    "GROQ_API_KEY_1",
    "GROQ_API_KEY_2",
    "GROQ_API_KEY_3",
    "GROQ_API_KEY_4",
    "GROQ_API_KEY_5",
    "GROQ_API_KEY_6",
    "HF_TOKEN_2",
    "HF_TOKEN_3",
    "HF_TOKEN_4",
]

def add(key, val):
    text = FILE.read_text()
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

# فحص الموجود
existing = {}
for line in FILE.read_text().splitlines():
    if "=" in line:
        k, v = line.split("=", 1)
        existing[k.strip()] = v.strip()

print(f"📝 الملف: {FILE}\n")
print(f"سأطلب {len(MISSING)} مفتاح (اكتب 'skip' لأي مفتاح تريد تخطيه)\n")

added = 0
for i, key in enumerate(MISSING, 1):
    if existing.get(key):
        print(f"[{i}/{len(MISSING)}] {key} — موجود مسبقاً (تخطي)")
        continue
    while True:
        val = input(f"[{i}/{len(MISSING)}] {key}: ").strip()
        if val.lower() == "skip":
            print(f"  ⊘ {key} [تخطي]")
            break
        if val:
            add(key, val)
            added += 1
            break
        print("  ⚠️  فارغ — أعد الإدخال أو اكتب 'skip'")

print(f"\n✅ اكتمل — أضيف {added} مفتاح")

# افحص
text = FILE.read_text()
print("\n=== مفاتيح Groq في الملف ===")
for k in sorted([l.split("=")[0] for l in text.splitlines() if l.startswith("GROQ_API_KEY_")]):
    print(f"  {k}")

print("\n=== مفاتيح HF ===")
for k in sorted([l.split("=")[0] for l in text.splitlines() if l.startswith("HF_TOKEN_")]):
    print(f"  {k}")
