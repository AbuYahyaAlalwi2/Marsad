import json, urllib.request, urllib.error
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

BASE = env.get("SATURN_BASE_URL")
UA = "Mozilla/5.0"
KEY = env.get("SATURN_API_KEY_1")

def call(path, method="GET", body=None):
    h = {"Authorization": f"token {KEY}", "User-Agent": UA,
         "Content-Type": "application/json"}
    req = urllib.request.Request(f"{BASE}{path}", method=method,
        data=json.dumps(body).encode() if body else None, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"_err": f"HTTP {e.code}", "_body": e.read(200).decode()[:150]}

print("=== Saturn resources الحالية ===")
d = call("/api/active/resources")
print(json.dumps(d, indent=2, ensure_ascii=False))

print("\n=== Saturn API endpoints ===")
for path in ["/api/status", "/api/datasets", "/api/projects"]:
    r = call(path)
    print(f"  {path}: {str(r)[:120]}")
