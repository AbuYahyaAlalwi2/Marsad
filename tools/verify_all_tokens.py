import os, json, urllib.request, base64
from pathlib import Path

SECRETS = Path.home() / ".marsad_secrets"
env = {}
for f in SECRETS.glob("*.env"):
    for line in f.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()

def test_http(name, url, headers=None):
    try:
        req = urllib.request.Request(url, headers=headers or {})
        with urllib.request.urlopen(req, timeout=15) as r:
            return f"✅ {name}: HTTP {r.status}"
    except urllib.error.HTTPError as e:
        return f"{'✅' if e.code in (200,201,401) else '❌'} {name}: HTTP {e.code}"
    except Exception as e:
        return f"❌ {name}: {type(e).__name__}: {str(e)[:60]}"

results = []

# 1. HF (كل توكن)
hf = env.get("HUGGINGFACE_TOKEN") or env.get("HF_TOKEN")
if hf:
    results.append(test_http("HF_TOKEN", "https://huggingface.co/api/whoami-v2",
                             {"Authorization": f"Bearer {hf}"}))

# 2. GitHub
gh = env.get("GH_TOKEN") or env.get("GITHUB_TOKEN")
if gh:
    results.append(test_http("GH_TOKEN", "https://api.github.com/user",
                             {"Authorization": f"token {gh}"}))

# 3. Cloudflare (كل 5)
for i in range(1, 6):
    tok = env.get(f"CF_TOKEN_{i}")
    if tok:
        results.append(test_http(f"CF_TOKEN_{i}", "https://api.cloudflare.com/client/v4/user/tokens/verify",
                                 {"Authorization": f"Bearer {tok}"}))

# 4. Railway
rw = env.get("RAILWAY_TOKEN")
if rw:
    results.append(test_http("RAILWAY_TOKEN", "https://backboard.railway.app/graphql/v2",
                             {"Authorization": f"Bearer {rw}", "Content-Type": "application/json"}))

# 5. Render
rn = env.get("RENDER_API_KEY")
if rn:
    results.append(test_http("RENDER_API_KEY", "https://api.render.com/v1/owners",
                             {"Authorization": f"Bearer {rn}"}))

# 6. E2B (كل 7)
for i in range(1, 8):
    k = env.get(f"E2B_API_KEY_{i}")
    if k:
        results.append(test_http(f"E2B_KEY_{i}", "https://api.e2b.dev/sandboxes",
                                 {"X-API-KEY": k}))

# 7. Saturn (كل 6)
for i in range(1, 7):
    k = env.get(f"SATURN_API_KEY_{i}")
    if k:
        results.append(test_http(f"SATURN_KEY_{i}", "https://api.saturncloud.io/v1/me",
                                 {"Authorization": f"Bearer {k}"}))

# 8. Telegram
tg = env.get("TELEGRAM_BOT_TOKEN")
if tg:
    results.append(test_http("TELEGRAM_BOT", f"https://api.telegram.org/bot{tg}/getMe"))

# 9. mail.tm
results.append(test_http("mail.tm", "https://api.mail.tm/domains"))

print("\n".join(results))
