import re
from pathlib import Path

FILE = Path.home() / ".marsad_secrets" / "all.env"

def add(key, val):
    text = FILE.read_text()
    pat = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
    line = f"{key}={val}"
    if pat.search(text):
        text = pat.sub(line, text)
        print(f"  ✓ {key} [مُحدَّث]")
    else:
        if text and not text.endswith("\n"): text += "\n"
        text += line + "\n"
        print(f"  ✓ {key} [مُضاف]")
    FILE.write_text(text)

print("اختر النوع:")
print("  1) API Token ثانٍ (يبدأ بـ cfut_)")
print("  2) Global API Key (يبدأ بـ cfk_ أو 37 حرف hex) — يحتاج إيميل")
print()
choice = input("اختيارك (1 أو 2): ").strip()

if choice == "1":
    val = input("أدخل API Token (cfut_...): ").strip()
    if val:
        add("CLOUDFLARE_API_TOKEN_2", val)
        print("  → سيُستخدم كاحتياطي")
elif choice == "2":
    email = input("أدخل إيميل Cloudflare: ").strip()
    key = input("أدخل Global API Key: ").strip()
    if email:
        add("CLOUDFLARE_EMAIL", email)
    if key:
        add("CLOUDFLARE_GLOBAL_KEY", key)
    print("  → Global Key يحتاج الإيميل دائماً")

print("\n✅ اكتمل")
