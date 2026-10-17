"""unify_keys.py — يدمج كل ملفات env في ملف واحد موحّد."""
import re
from pathlib import Path

SOURCES = [
    Path.home() / ".marsad_secrets" / "marsad.env",
    Path.home() / ".marsad_secrets" / "miner.env",
    Path.home() / ".marsad_secrets" / "render.env",
    Path.home() / ".marsad_secrets" / "llm_endpoint.env",
    Path.home() / "Marsad" / ".env",
    Path.home() / "Marsad-Manager" / ".env",
    Path.home() / "kaggle_debug_kernel" / "marsad-dashboard.env.txt",
]

UNIFIED = Path.home() / ".marsad_secrets" / "all.env"

merged = {}
sources_used = 0

for f in SOURCES:
    if not f.exists():
        continue
    sources_used += 1
    for line in f.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        # لا نستبدل قيمة موجودة بقيمة فارغة
        if k in merged and merged[k] and not v:
            continue
        if k not in merged or (not merged[k] and v):
            merged[k] = v

# اكتب الملف الموحّد
lines = [f"{k}={v}" for k, v in sorted(merged.items())]
UNIFIED.write_text("\n".join(lines) + "\n")
UNIFIED.chmod(0o600)

print(f"✅ دمج {sources_used} ملف → {UNIFIED}")
print(f"   {len(merged)} مفتاح")

# إحصاء
print("\n=== المفاتيح (أسماء فقط) ===")
for k in sorted(merged):
    v = merged[k]
    status = "✓" if v else "✗ (فارغ)"
    print(f"  {status:12s} {k}")

# المفاتيح الناقصة المتوقعة
expected = ["GROQ_API_KEY_1", "GROQ_API_KEY_2", "GROQ_API_KEY_3",
            "GROQ_API_KEY_4", "GROQ_API_KEY_5", "GROQ_API_KEY_6",
            "DEEPSEEK_API_KEY", "OPENROUTER_API_KEY", "GOOGLE_API_KEY",
            "GITHUB_TOKEN_1", "GITHUB_TOKEN_2",
            "HF_TOKEN_1", "HF_TOKEN_2", "HF_TOKEN_3", "HF_TOKEN_4",
            "NVD_API_KEY", "TELEGRAM_BOT_TOKEN",
            "CF_TOKEN_1", "CF_TOKEN_2", "CF_TOKEN_3", "CF_TOKEN_4", "CF_TOKEN_5",
            "E2B_API_KEY_1", "E2B_API_KEY_2", "E2B_API_KEY_3", "E2B_API_KEY_4",
            "E2B_API_KEY_5", "E2B_API_KEY_6", "E2B_API_KEY_7",
            "SATURN_API_KEY_1", "SATURN_API_KEY_2", "SATURN_API_KEY_3",
            "SATURN_API_KEY_4", "SATURN_API_KEY_5", "SATURN_API_KEY_6"]

print("\n=== المفاتيح الناقصة ===")
missing = [k for k in expected if k not in merged or not merged[k]]
if missing:
    for k in missing:
        print(f"  ✗ {k}")
else:
    print("  لا شيء — كل المفاتيح موجودة")
