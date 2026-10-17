import re, json, urllib.request
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
key = env.get("GROQ_API_KEY_1")

def test_model(model):
    body = json.dumps({
        "model": model,
        "messages":[{"role":"user","content":"أصلح: cur.execute('SELECT * FROM t WHERE id=' + uid)"}],
        "max_tokens": 400,
    }).encode()
    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=body, method="POST",
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type":"application/json", "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            d = json.loads(r.read())
        msg = d["choices"][0]["message"]
        content = msg.get("content", "")
        reasoning = msg.get("reasoning_content", "")
        return {"content_len": len(content),
                "reasoning_len": len(reasoning),
                "content": content[:300],
                "reasoning": reasoning[:200]}
    except Exception as e:
        return {"err": str(e)[:120]}

for m in ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"]:
    print(f"=== {m} ===")
    r = test_model(m)
    print(json.dumps(r, ensure_ascii=False, indent=2))
    print()
