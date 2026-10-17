"""verify_all_v3.py — فحص كل مفاتيح Groq + HF من الملف الموحّد."""
import re, json, urllib.request, urllib.error
from pathlib import Path

FILE = Path.home() / ".marsad_secrets" / "all.env"
env = {}
for line in FILE.read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"

# ═══ Groq ═══
print("=" * 60)
print("  فحص Groq (gpt-oss-120b)")
print("=" * 60)

def test_groq(key):
    body = json.dumps({
        "model": "openai/gpt-oss-120b",
        "messages": [{"role": "user", "content": "say hi"}],
        "max_tokens": 5,
    }).encode()
    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=body, method="POST",
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json",
                 "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return True, "ok"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}: {e.read(120).decode()[:60]}"
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)[:50]}"

groq_ok = 0
groq_total = 0
for k, v in sorted(env.items(), key=lambda x: x[0]):
    if not k.startswith("GROQ_API_KEY_"):
        continue
    groq_total += 1
    if not v:
        print(f"  ✗ {k:18s} (فارغ)")
        continue
    ok, msg = test_groq(v)
    if ok:
        groq_ok += 1
        print(f"  ✅ {k:18s} → يعمل")
    else:
        print(f"  ❌ {k:18s} → {msg}")

print(f"\n  النتيجة: {groq_ok}/{groq_total}\n")

# ═══ HF ═══
print("=" * 60)
print("  فحص HuggingFace")
print("=" * 60)

def test_hf(key):
    req = urllib.request.Request(
        "https://huggingface.co/api/whoami-v2",
        headers={"Authorization": f"Bearer {key}", "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            d = json.loads(r.read())
            return True, d.get("name", "?")
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)[:40]}"

hf_ok = 0
hf_total = 0
hf_users = []
for k, v in sorted(env.items(), key=lambda x: x[0]):
    if not (k.startswith("HF_TOKEN_") or k in ("HF_TOKEN", "HUGGINGFACE_TOKEN", "HF_API_KEY")):
        continue
    hf_total += 1
    if not v:
        print(f"  ✗ {k:22s} (فارغ)")
        continue
    ok, msg = test_hf(v)
    if ok:
        hf_ok += 1
        hf_users.append((k, msg))
        print(f"  ✅ {k:22s} → {msg}")
    else:
        print(f"  ❌ {k:22s} → {msg}")

print(f"\n  النتيجة: {hf_ok}/{hf_total}")

# ═══ الخلاصة ═══
print("\n" + "=" * 60)
print("  الخلاصة")
print("=" * 60)
print(f"  Groq:  {groq_ok}/{groq_total} يعمل")
print(f"  HF:    {hf_ok}/{hf_total} يعمل")
if hf_users:
    print(f"\n  حسابات HF الشغّالة:")
    for k, u in hf_users:
        print(f"    {k} → {u}")
