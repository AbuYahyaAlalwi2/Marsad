"""
Marsad — Kaggle Unified Server + Self-Play
==========================================
يشغّل v2 (llama-server) + يبني المهام من CVEfixes + يدير Self-Play + قناة تحكم عبر HF.
"""
import os, sys, json, time, glob, shutil, subprocess, re, threading
from pathlib import Path

# ─── 1. HF Token ─────────────────────────────────────────
try:
    from kaggle_secrets import UserSecretsClient
    HF_TOKEN = UserSecretsClient().get_secret("HF_TOKEN")
except Exception:
    HF_TOKEN = os.environ.get("HF_TOKEN", "")
assert HF_TOKEN, "Add HF_TOKEN in Kaggle Secrets"
os.environ["HF_TOKEN"] = HF_TOKEN
os.environ["HUGGING_FACE_HUB_TOKEN"] = HF_TOKEN
print(f"✓ HF token: {HF_TOKEN[:8]}...")

CONTROL_REPO = "AbuYahya2/marsad-endpoints"
API_KEY = "marsad-" + os.urandom(16).hex()
print(f"✓ API key: {API_KEY[:20]}...")

# ─── 2. Install deps ─────────────────────────────────────
print("→ installing deps...")
subprocess.run([sys.executable, "-m", "pip", "install", "-q",
                "huggingface_hub", "datasets",
                "nvidia-cuda-runtime-cu12",
                "nvidia-cublas-cu12",
                "nvidia-cuda-nvrtc-cu12"], check=True)

# ─── 3. CUDA libs ────────────────────────────────────────
import nvidia
cuda_libs = []
for sub in Path(nvidia.__path__[0]).iterdir():
    if sub.is_dir():
        for ld in [sub / "lib", sub / "lib64"]:
            if ld.exists():
                cuda_libs.append(str(ld))
print(f"✓ CUDA dirs: {len(cuda_libs)}")

# ─── 4. Copy llama-server ────────────────────────────────
hits = glob.glob("/kaggle/input/**/llama-server", recursive=True)
assert hits, "Add dataset: llama-server-slim-gpu"
SRC = Path(hits[0]).parent
WORK = Path("/kaggle/working/llama-bin")
WORK.mkdir(parents=True, exist_ok=True)
for f in SRC.iterdir():
    if f.is_file():
        d = WORK / f.name
        if not d.exists():
            shutil.copy2(f, d)
        os.chmod(d, 0o755)
LLAMA = str(WORK / "llama-server")
print(f"✓ llama-server: {LLAMA}")

env = os.environ.copy()
env["GGML_CUDA_NO_PINNED"] = "1"
env["LD_LIBRARY_PATH"] = ":".join(
    [str(WORK), "/usr/local/nvidia/lib64", *cuda_libs,
     env.get("LD_LIBRARY_PATH", "")])

# ─── 5. Download GGUF ────────────────────────────────────
from huggingface_hub import hf_hub_download, HfApi
GGUF = "/kaggle/working/model-q8.gguf"
if not Path(GGUF).exists():
    print("→ downloading GGUF...")
    p = hf_hub_download(
        repo_id="AbuYahya2/deepseek-marsad-v2-gguf",
        filename="model-q8.gguf",
        token=HF_TOKEN, local_dir="/kaggle/working")
    if not Path(GGUF).exists():
        GGUF = p
print(f"✓ GGUF: {Path(GGUF).stat().st_size/1e9:.2f} GB")

# ─── 6. Start llama-server ───────────────────────────────
print("→ starting llama-server...")
log = open("/kaggle/working/llama_server.log", "w")
server_proc = subprocess.Popen(
    [LLAMA, "--host", "127.0.0.1", "--port", "8080",
     "--model", GGUF, "--n-gpu-layers", "99",
     "--ctx-size", "8192", "--threads", "4",
     "--parallel", "1", "--cont-batching",
     "--api-key", API_KEY, "--jinja"],
    stdout=log, stderr=subprocess.STDOUT, env=env)

deadline = time.time() + 900
ready = False
while time.time() < deadline:
    try:
        r = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
             "-H", f"Authorization: Bearer {API_KEY}",
             "http://127.0.0.1:8080/health"],
            capture_output=True, text=True, timeout=5, env=env)
        if r.stdout.strip() == "200":
            ready = True; break
    except Exception:
        pass
    if server_proc.poll() is not None:
        break
    time.sleep(5)

assert ready, "server did not start"
print("✓ server ready on :8080")

# ─── 7. Build tasks from CVEfixes ────────────────────────
REPO = Path("/kaggle/working/Marsad/challenge/repo")
REPO.mkdir(parents=True, exist_ok=True)
TASKS = REPO / "tasks.json"

if not TASKS.exists():
    print("→ building tasks from CVEfixes...")
    from datasets import load_dataset
    ds = load_dataset("ASSERT-KTH/CVEfixes", split="train", streaming=True)
    tasks = []
    for i, row in enumerate(ds):
        if len(tasks) >= 200:
            break
        before = row.get("func_before") or row.get("code_before") or ""
        after = row.get("func_after") or row.get("code_after") or ""
        if not before or not after:
            continue
        tasks.append({
            "id": f"cve-{row.get('cve_id', i)}",
            "cve": row.get("cve_id", ""),
            "language": row.get("language", "python"),
            "before": str(before)[:5000],
            "after": str(after)[:5000],
            "commit": row.get("hash", ""),
            "cvss": float(row.get("cvss") or 5.0),
        })
    TASKS.write_text(json.dumps(tasks, ensure_ascii=False))
    print(f"✓ tasks: {len(tasks)}")
else:
    print(f"✓ tasks exists: {len(json.loads(TASKS.read_text()))}")

# ─── 8. Judge ────────────────────────────────────────────
import re

def judge(task, answer):
    if not answer:
        return {"score": 0}
    a_low = answer.lower()
    cve = (task.get("cve") or "").lower()
    correct = (task.get("after") or "").lower()
    score = 0
    if cve and cve in a_low:
        score += 30
    kws = {"injection","xss","sql","rce","overflow","log4j","validation",
           "sanitiz","escape","ثغرة","حقن","تحقق","استغلال"}
    score += min(sum(1 for k in kws if k in a_low) * 5, 20)
    if correct:
        tc = set(re.findall(r"[a-z_][a-z0-9_]{2,}", correct))
        ta = set(re.findall(r"[a-z_][a-z0-9_]{2,}", answer.lower()))
        if tc:
            score += int((len(tc & ta) / len(tc)) * 40)
    if any(m in a_low for m in ["fix","patch","update","validate","أصلح"]):
        score += 10
    return {"score": min(score, 100)}

# ─── 9. Control channel ──────────────────────────────────
api = HfApi(token=HF_TOKEN)

def read_command():
    try:
        p = hf_hub_download(CONTROL_REPO, "commands.json",
                            repo_type="dataset", token=HF_TOKEN,
                            force_download=True)
        return json.loads(Path(p).read_text())
    except Exception:
        return {"action": "run"}

def write_status(status):
    Path("/kaggle/working/status.json").write_text(
        json.dumps(status, ensure_ascii=False))
    try:
        api.upload_file(
            path_or_fileobj="/kaggle/working/status.json",
            path_in_repo="status.json",
            repo_id=CONTROL_REPO, repo_type="dataset")
    except Exception as e:
        print(f"[status] upload failed: {e}")

# ─── 10. Start tunnel ────────────────────────────────────
print("→ cloudflared...")
CF = Path("/kaggle/working/cloudflared")
if not CF.exists():
    subprocess.run(["wget", "-q",
                    "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64",
                    "-O", str(CF)], check=True)
    CF.chmod(0o755)

tun = subprocess.Popen(
    [str(CF), "tunnel", "--url", "http://127.0.0.1:8080", "--no-autoupdate"],
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)

URL = None
pat = re.compile(r"https://[-a-z0-9]+\.trycloudflare\.com")
deadline = time.time() + 120
while time.time() < deadline:
    line = tun.stdout.readline()
    if not line: continue
    m = pat.search(line)
    if m:
        URL = m.group(0); break

assert URL
Path("/kaggle/working/endpoint.json").write_text(json.dumps({
    "url": f"{URL}/v1", "key": API_KEY, "model": "v2",
    "ts": time.time(),
}, indent=2))

# ارفع الرابط لـ HF
try:
    import io
    api.upload_file(
        path_or_fileobj=io.BytesIO(json.dumps({
            "url": f"{URL}/v1", "key": API_KEY,
            "model": "v2", "ts": time.time(),
        }).encode()),
        path_in_repo="current.json",
        repo_id=CONTROL_REPO, repo_type="dataset")
    print(f"✓ URL uploaded: {URL}/v1")
except Exception as e:
    print(f"⚠️ URL upload failed: {e}")

print()
print("=" * 60)
print(f"URL: {URL}/v1")
print(f"KEY: {API_KEY}")
print("=" * 60)

# ─── 11. Self-Play Loop ──────────────────────────────────
print("\n→ starting self-play loop...")
log_path = Path("/kaggle/working/self_play.jsonl")
tiers = [
    (0.0, 3.9, "Tier-1"),
    (4.0, 6.9, "Tier-2"),
    (7.0, 8.9, "Tier-3"),
    (9.0, 10.0, "Tier-4"),
]

import random, httpx

tasks_all = json.loads(TASKS.read_text())
by_tier = {}
for i, (lo, hi, name) in enumerate(tiers):
    by_tier[i] = [t for t in tasks_all if lo <= t["cvss"] <= hi]

LLM_URL = f"{URL}/v1"
HEADERS = {"Authorization": f"Bearer {API_KEY}",
           "Content-Type": "application/json"}

def call_llm(prompt, max_tokens=500):
    try:
        r = httpx.post(f"{LLM_URL}/chat/completions",
                       headers=HEADERS,
                       json={"model": "v2",
                             "messages": [
                                 {"role": "system",
                                  "content": "أنت Marsad CyberAgent. حلل الثغرة واقترح إصلاحاً."},
                                 {"role": "user", "content": prompt}],
                             "max_tokens": max_tokens,
                             "temperature": 0.3},
                       timeout=180)
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"ERR: {e}"

current_tier = 0
recent = []
round_i = 0
PROMOTE = 70
CHECK = 5

while True:
    cmd = read_command()
    action = cmd.get("action", "run")

    if action == "stop":
        write_status({"state": "stopped", "round": round_i})
        print("stopped by command")
        break
    if action == "pause":
        write_status({"state": "paused", "round": round_i})
        time.sleep(30)
        continue

    pool = by_tier.get(current_tier) or []
    if not pool:
        current_tier = min(current_tier + 1, len(tiers) - 1)
        continue

    task = random.choice(pool)
    prompt = (f"حلّل الثغرة {task['cve']}.\n"
              f"الكود قبل: {task['before'][:400]}\n"
              f"اقترح الإصلاح.")
    answer = call_llm(prompt)
    score = judge(task, answer)["score"]

    entry = {"round": round_i, "cve": task["cve"],
             "tier": current_tier, "score": score,
             "ts": time.time()}
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    recent.append(score)
    recent = recent[-CHECK:]
    print(f"[round {round_i}] tier={current_tier} cve={task['cve']} score={score}")

    write_status({"state": "running", "round": round_i,
                  "tier": current_tier, "last_score": score,
                  "avg_recent": sum(recent) / len(recent)})

    if len(recent) >= CHECK:
        avg = sum(recent) / len(recent)
        if avg >= PROMOTE and current_tier < len(tiers) - 1:
            current_tier += 1
            recent = []
            print(f"🎓 promoted to tier {current_tier}")

    round_i += 1
    time.sleep(3)
