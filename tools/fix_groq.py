import re, json, urllib.request, urllib.error
from pathlib import Path

FILE = Path.home() / "storage" / "downloads" / "marsad-dashboard.env.txt"

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

def read_keys():
    keys = {}
    for line in FILE.read_text().splitlines():
        m = re.match(r"^(GROQ_API_KEY_\d+)=(.+)$", line.strip())
        if m:
            keys[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return keys

def check(key, model):
    body = json.dumps({"model": model,
                       "messages": [{"role":"user","content":"say hi"}],
                       "max_tokens": 5}).encode()
    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=body, method="POST",
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json",
                 "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            d = json.loads(r.read())
            return True, d["choices"][0]["message"]["content"][:40]
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}: {e.read(150).decode()[:80]}"
    except Exception as e:
        return False, str(e)[:60]

keys = read_keys()
MODEL = "openai/gpt-oss-120b"
print(f"فحص {len(keys)} مفتاح بموديل {MODEL}\n")

working = []
for name, key in sorted(keys.items()):
    ok, msg = check(key, MODEL)
    status = "✅" if ok else "❌"
    print(f"  {status} {name:18s} {msg}")
    if ok: working.append(name)

print(f"\n=== {len(working)}/{len(keys)} مفتاح يعمل ===")

# إضافة أسماء الموديلات للملف
if working:
    text = FILE.read_text()
    for k, v in [("GROQ_MODEL_PRIMARY", "openai/gpt-oss-120b"),
                 ("GROQ_MODEL_FAST", "openai/gpt-oss-20b"),
                 ("GROQ_MODEL_QWEN", "qwen/qwen3.8-27b")]:
        pat = re.compile(rf"^{re.escape(k)}=.*$", re.MULTILINE)
        line = f"{k}={v}"
        if pat.search(text):
            text = pat.sub(line, text)
        else:
            if not text.endswith("\n"): text += "\n"
            text += line + "\n"
    FILE.write_text(text)
    print(f"\n✅ أُضيفت أسماء الموديلات إلى {FILE.name}")
