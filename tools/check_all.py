import re, json, urllib.request, urllib.error
from pathlib import Path

FILE = Path.home() / "storage" / "downloads" / "marsad-dashboard.env.txt"
env = {}
for line in FILE.read_text().splitlines():
    line = line.strip()
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"

def http(name, url, headers=None, method="GET", body=None, expect=(200, 201, 401)):
    try:
        req = urllib.request.Request(url, method=method, data=body,
                                     headers={**(headers or {}), "User-Agent": UA})
        with urllib.request.urlopen(req, timeout=15) as r:
            return f"✅ {name}: {r.status}"
    except urllib.error.HTTPError as e:
        # 401/403 على endpoint محمي يعني المفتاح وصل لكنه غير صالح
        # 200/201 يعني شغال
        return f"{'✅' if e.code in expect else '❌'} {name}: HTTP {e.code}"
    except Exception as e:
        return f"❌ {name}: {type(e).__name__}: {str(e)[:50]}"

print("=== فحص المزودين ===\n")

# HuggingFace
for k in ["HF_TOKEN", "HUGGINGFACE_TOKEN", "HF_API_KEY"]:
    if env.get(k):
        print(http(f"{k}", "https://huggingface.co/api/whoami-v2",
                   {"Authorization": f"Bearer {env[k]}"}))
        break

# GitHub
for k in ["GITHUB_TOKEN_1", "GITHUB_TOKEN_2", "GITHUB_TOKEN"]:
    if env.get(k):
        print(http(k, "https://api.github.com/user",
                   {"Authorization": f"token {env[k]}"}))

# Cloudflare
for i in range(1, 6):
    t = env.get(f"CF_TOKEN_{i}")
    if t:
        print(http(f"CF_TOKEN_{i}", "https://api.cloudflare.com/client/v4/user/tokens/verify",
                   {"Authorization": f"Bearer {t}"}))

# E2B
for i in range(1, 8):
    k = env.get(f"E2B_API_KEY_{i}")
    if k:
        print(http(f"E2B_KEY_{i}", "https://api.e2b.dev/sandboxes",
                   {"X-API-KEY": k}))

# DeepSeek
if env.get("DEEPSEEK_API_KEY"):
    body = json.dumps({"model": "deepseek-chat",
                       "messages": [{"role":"user","content":"hi"}],
                       "max_tokens": 3}).encode()
    print(http("DEEPSEEK", "https://api.deepseek.com/v1/chat/completions",
               {"Authorization": f"Bearer {env['DEEPSEEK_API_KEY']}",
                "Content-Type": "application/json"},
               method="POST", body=body))

# OpenRouter
if env.get("OPENROUTER_API_KEY"):
    print(http("OPENROUTER", "https://openrouter.ai/api/v1/auth/key",
               {"Authorization": f"Bearer {env['OPENROUTER_API_KEY']}"}))

# Google
if env.get("GOOGLE_API_KEY"):
    print(http("GOOGLE", f"https://generativelanguage.googleapis.com/v1/models?key={env['GOOGLE_API_KEY']}"))

# NVD
if env.get("NVD_API_KEY"):
    print(http("NVD", "https://services.nvd.nist.gov/rest/json/cves/2.0?resultsPerPage=1",
               {"apiKey": env["NVD_API_KEY"]}))

# Railway
if env.get("RAILWAY_TOKEN"):
    print(http("RAILWAY", "https://backboard.railway.app/graphql/v2",
               {"Authorization": f"Bearer {env['RAILWAY_TOKEN']}",
                "Content-Type": "application/json"}))

# Telegram
if env.get("TELEGRAM_BOT_TOKEN"):
    print(http("TELEGRAM", f"https://api.telegram.org/bot{env['TELEGRAM_BOT_TOKEN']}/getMe"))
