"""add_extra.py — يضيف OpenRouter + Cloudflare بشكل تفاعلي."""
import re, json, urllib.request, urllib.error
from pathlib import Path

FILE = Path.home() / ".marsad_secrets" / "all.env"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"

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

def test_openrouter(key):
    try:
        req = urllib.request.Request("https://openrouter.ai/api/v1/auth/key",
                                     headers={"Authorization": f"Bearer {key}", "User-Agent": UA})
        with urllib.request.urlopen(req, timeout=15) as r:
            d = json.loads(r.read())
            data = d.get("data", {})
            return True, f"label={data.get('label','?')}, usage={data.get('usage',0)}"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)[:40]}"

def test_cf_token(key):
    try:
        req = urllib.request.Request("https://api.cloudflare.com/client/v4/user/tokens/verify",
                                     headers={"Authorization": f"Bearer {key}", "User-Agent": UA})
        with urllib.request.urlopen(req, timeout=15) as r:
            d = json.loads(r.read())
            return True, f"status={d.get('result',{}).get('status','?')}"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)[:40]}"

print(f"📝 الملف: {FILE}\n")

# ═══ OpenRouter ═══
print("── OpenRouter ──")
print("(مفتاح يبدأ بـ sk-or-)")
while True:
    val = input("أدخل مفتاح OpenRouter (أو 'skip'): ").strip()
    if val.lower() == "skip":
        break
    if not val:
        continue
    print("  → فحص...")
    ok, msg = test_openrouter(val)
    if ok:
        add("OPENROUTER_API_KEY", val)
        print(f"  ✅ {msg}")
        break
    else:
        print(f"  ❌ {msg} — أعد المحاولة")

# ═══ Cloudflare ═══
print("\n── Cloudflare ──")
print("النوعان:")
print("  1) API Token (يبدأ بـ cfut_)  ← الموصى به")
print("  2) Global API Key (يبدأ بـ cfk_) ← قديم")
val = input("\nأدخل مفتاح Cloudflare (أو 'skip'): ").strip()
if val.lower() != "skip" and val:
    print("  → فحص...")
    ok, msg = test_cf_token(val)
    if ok:
        add("CLOUDFLARE_API_TOKEN", val)
        print(f"  ✅ {msg}")
    else:
        # جرّب Global Key
        print(f"  ⚠️  كـ Token فشل ({msg})")
        # Global Key يحتاج email أيضاً
        email = input("إذا كان Global Key، أدخل الإيميل (أو Enter للتخطي): ").strip()
        if email:
            add("CLOUDFLARE_EMAIL", email)
            add("CLOUDFLARE_GLOBAL_KEY", val)
            print(f"  ✓ حُفظ كـ Global Key + Email")
        else:
            add("CLOUDFLARE_API_TOKEN", val)
            print(f"  ⚠️  حُفظ بدون تحقق")

print(f"\n✅ اكتمل")
