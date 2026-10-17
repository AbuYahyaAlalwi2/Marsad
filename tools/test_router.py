import re, json, urllib.request, urllib.error
from pathlib import Path

env = {}
for f in [Path.home()/"storage"/"downloads"/"marsad-dashboard.env.txt",
          Path.home()/"Marsad"/".env"]:
    if f.exists():
        for line in f.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                if k.strip() not in env:
                    env[k.strip()] = v.strip().strip('"').strip("'")

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"

def groq(prompt, model="openai/gpt-oss-120b", key_idx=1):
    key = env.get(f"GROQ_API_KEY_{key_idx}")
    body = json.dumps({"model": model,
                       "messages":[{"role":"user","content":prompt}],
                       "max_tokens": 100}).encode()
    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=body, method="POST",
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type":"application/json", "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.loads(r.read())
            return d["choices"][0]["message"]["content"]
    except Exception as e:
        return f"ERR: {str(e)[:80]}"

def google(prompt, model="gemini-3.1-flash-lite"):
    key = env.get("GOOGLE_API_KEY")
    body = json.dumps({"contents":[{"parts":[{"text": prompt}]}]}).encode()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"Content-Type":"application/json","User-Agent":UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.loads(r.read())
            return d["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        return f"ERR: {str(e)[:80]}"

print("=== Groq (gpt-oss-120b) ===")
print(groq("أصلح: cur.execute('SELECT * FROM t WHERE id=' + uid)"))

print("\n=== Google (gemini-3.1-flash-lite) ===")
print(google("أصلح: cur.execute('SELECT * FROM t WHERE id=' + uid)"))
