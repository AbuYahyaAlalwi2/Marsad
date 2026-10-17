"""verify_everything.py — فحص شامل لكل مفتاح في all.env."""
import re, json, base64, urllib.request, urllib.error
from pathlib import Path

FILE = Path.home() / ".marsad_secrets" / "all.env"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"

env = {}
for line in FILE.read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")

def http(name, url, headers=None, method="GET", body=None, ok_codes=(200, 201)):
    try:
        req = urllib.request.Request(url, method=method, data=body,
                                     headers={**(headers or {}), "User-Agent": UA})
        with urllib.request.urlopen(req, timeout=15) as r:
            return f"✅ {name}: {r.status}"
    except urllib.error.HTTPError as e:
        return f"{'✅' if e.code in ok_codes else '❌'} {name}: HTTP {e.code}"
    except Exception as e:
        return f"❌ {name}: {type(e).__name__}: {str(e)[:40]}"

results = []

# ── HF ──
for k, v in sorted(env.items()):
    if re.match(r"^HF_TOKEN_\d+$", k) and v:
        try:
            req = urllib.request.Request("https://huggingface.co/api/whoami-v2",
                                         headers={"Authorization": f"Bearer {v}", "User-Agent": UA})
            with urllib.request.urlopen(req, timeout=15) as r:
                d = json.loads(r.read())
                results.append(f"✅ {k}: {d.get('name','?')}")
        except urllib.error.HTTPError as e:
            results.append(f"❌ {k}: HTTP {e.code}")
        except Exception as e:
            results.append(f"❌ {k}: {str(e)[:40]}")

# ── Groq ──
for k, v in sorted(env.items()):
    if re.match(r"^GROQ_API_KEY_\d+$", k) and v:
        body = json.dumps({"model": "openai/gpt-oss-120b",
                           "messages":[{"role":"user","content":"hi"}],
                           "max_tokens":3}).encode()
        results.append(http(k, "https://api.groq.com/openai/v1/chat/completions",
                            {"Authorization": f"Bearer {v}", "Content-Type": "application/json"},
                            method="POST", body=body))

# ── Cloudflare tokens ──
for k, v in sorted(env.items()):
    if re.match(r"^CF_TOKEN_\d+$", k) and v:
        results.append(http(k, "https://api.cloudflare.com/client/v4/user/tokens/verify",
                            {"Authorization": f"Bearer {v}"}))

# ── Cloudflare global API ──
if env.get("CLOUDFLARE_API_TOKEN"):
    results.append(http("CLOUDFLARE_API_TOKEN", "https://api.cloudflare.com/client/v4/user/tokens/verify",
                        {"Authorization": f"Bearer {env['CLOUDFLARE_API_TOKEN']}"}))

# ── E2B ──
for k, v in sorted(env.items()):
    if re.match(r"^E2B_API_KEY_\d+$", k) and v:
        results.append(http(k, "https://api.e2b.dev/sandboxes", {"X-API-KEY": v}))

# ── Saturn ──
SAT_BASE = env.get("SATURN_BASE_URL") or "https://app.community.saturnenterprise.io"
for k, v in sorted(env.items()):
    if re.match(r"^SATURN_API_KEY_\d+$", k) and v:
        results.append(http(k, f"{SAT_BASE}/api/status", {"Authorization": f"token {v}"}))

# ── GitHub ──
for k, v in sorted(env.items()):
    if re.match(r"^GITHUB_TOKEN_\d+$", k) and v:
        results.append(http(k, "https://api.github.com/user", {"Authorization": f"token {v}"}))

# ── Kaggle ──
users = {int(m.group(1)): v for k, v in env.items() if (m := re.match(r"^KAGGLE_USERNAME_(\d+)$", k))}
keys  = {int(m.group(1)): v for k, v in env.items() if (m := re.match(r"^KAGGLE_KEY_(\d+)$", k))}
for i in sorted(set(users) & set(keys)):
    creds = base64.b64encode(f"{users[i]}:{keys[i]}".encode()).decode()
    results.append(http(f"KAGGLE_{i}({users[i]})", "https://www.kaggle.com/api/v1/datasets/list?page=1",
                        {"Authorization": f"Basic {creds}"}))

# ── Google ──
if env.get("GOOGLE_API_KEY"):
    results.append(http("GOOGLE_API_KEY", f"https://generativelanguage.googleapis.com/v1beta/models?key={env['GOOGLE_API_KEY']}"))

# ── NVD ──
if env.get("NVD_API_KEY"):
    results.append(http("NVD_API_KEY", "https://services.nvd.nist.gov/rest/json/cves/2.0?resultsPerPage=1",
                        {"apiKey": env["NVD_API_KEY"]}))

# ── Telegram ──
if env.get("TELEGRAM_BOT_TOKEN"):
    results.append(http("TELEGRAM_BOT", f"https://api.telegram.org/bot{env['TELEGRAM_BOT_TOKEN']}/getMe"))

# ── DeepSeek ──
if env.get("DEEPSEEK_API_KEY"):
    body = json.dumps({"model":"deepseek-chat","messages":[{"role":"user","content":"hi"}],"max_tokens":3}).encode()
    results.append(http("DEEPSEEK", "https://api.deepseek.com/v1/chat/completions",
                        {"Authorization": f"Bearer {env['DEEPSEEK_API_KEY']}", "Content-Type": "application/json"},
                        method="POST", body=body, ok_codes=(200,)))

# ── OpenRouter ──
if env.get("OPENROUTER_API_KEY"):
    results.append(http("OPENROUTER", "https://openrouter.ai/api/v1/auth/key",
                        {"Authorization": f"Bearer {env['OPENROUTER_API_KEY']}"}))

# ── العرض ──
print("=" * 65)
print("  الفحص الشامل")
print("=" * 65)
for r in results:
    print(f"  {r}")

# ── الإحصاء ──
ok_count = sum(1 for r in results if r.startswith("✅"))
fail_count = sum(1 for r in results if r.startswith("❌"))
print(f"\n  الإجمالي: ✅ {ok_count} يعمل | ❌ {fail_count} فشل")
