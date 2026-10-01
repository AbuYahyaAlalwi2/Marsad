"""
Colab — Marsad v2 Server + Tunnel (نُسخة قابلة لإعادة الاستخدام)
"""
import os, subprocess, time, shutil, re, json, io
from pathlib import Path

# ─── Config ─────────────────────────────────────────
BASE = "/content/drive/MyDrive/marsad_persistent"
LOCAL_BIN = "/content/llama-local"
GGUF_LOCAL = "/content/model-q8.gguf"
GGUF_DRIVE = BASE + "/model-q8.gguf"
BIN_DRIVE = BASE + "/llama-bin"
PORT = 5000
CONTROL_REPO = "AbuYahya2/marsad-endpoints"

# ─── 1. Mount Drive ─────────────────────────────────
from google.colab import drive, userdata
if not Path("/content/drive/MyDrive").exists():
    drive.mount('/content/drive')

HF_TOKEN = userdata.get("HF_TOKEN")
os.environ["HF_TOKEN"] = HF_TOKEN
os.environ["HUGGING_FACE_HUB_TOKEN"] = HF_TOKEN

# ─── 2. Validate Drive files ────────────────────────
assert Path(BIN_DRIVE + "/llama-server").exists(), "llama-bin missing on Drive"
assert Path(GGUF_DRIVE).exists(), "GGUF missing on Drive"
print("✓ Drive files OK")

# ─── 3. Copy binaries locally ───────────────────────
Path(LOCAL_BIN).mkdir(exist_ok=True)
for f in Path(BIN_DRIVE).iterdir():
    if f.is_file():
        dst = Path(LOCAL_BIN) / f.name
        if not dst.exists():
            shutil.copy2(f, dst)
        os.chmod(dst, 0o755)

# ─── 4. Copy GGUF locally ───────────────────────────
if not Path(GGUF_LOCAL).exists():
    print("→ copying GGUF (~30s)...")
    shutil.copy2(GGUF_DRIVE, GGUF_LOCAL)

# ─── 5. Kill old ────────────────────────────────────
subprocess.call("pkill -9 -f llama-server", shell=True)
subprocess.call("pkill -9 -f cloudflared", shell=True)
time.sleep(3)

# ─── 6. Start server ────────────────────────────────
API_KEY = "marsad-" + os.urandom(16).hex()
Path("/content/api_key.txt").write_text(API_KEY)
print("API_KEY:", API_KEY)

env = os.environ.copy()
env["LD_LIBRARY_PATH"] = LOCAL_BIN + ":" + env.get("LD_LIBRARY_PATH", "")
env["GGML_CUDA_NO_PINNED"] = "1"

log = open("/content/llama_server.log", "w")
proc = subprocess.Popen(
    [LOCAL_BIN + "/llama-server",
     "--host", "127.0.0.1", "--port", str(PORT),
     "--model", GGUF_LOCAL,
     "--n-gpu-layers", "99",
     "--ctx-size", "4096",
     "--threads", "2",
     "--parallel", "1",
     "--cont-batching",
     "--flash-attn",
     "--cache-type-k", "q8_0",
     "--cache-type-v", "q8_0",
     "--api-key", API_KEY,
     "--jinja"],
    stdout=log, stderr=subprocess.STDOUT, env=env)

for i in range(30):
    time.sleep(10)
    if "server is listening" in Path("/content/llama_server.log").read_text().lower():
        print(f"✓ server ready after {(i+1)*10}s")
        break
    if proc.poll() is not None:
        print("✗ server crashed")
        print(Path("/content/llama_server.log").read_text()[-1500:])
        raise SystemExit(1)
else:
    print("⏱️ timeout")
    raise SystemExit(1)

# ─── 7. Cloudflare Tunnel ───────────────────────────
CF = Path("/content/cloudflared")
if not CF.exists():
    subprocess.run(["wget", "-q",
                    "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64",
                    "-O", str(CF)], check=True)
    CF.chmod(0o755)

tun = subprocess.Popen(
    [str(CF), "tunnel", "--url", f"http://127.0.0.1:{PORT}", "--no-autoupdate"],
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

assert URL, "tunnel failed"

# ─── 8. Publish to HF ───────────────────────────────
from huggingface_hub import HfApi
api = HfApi(token=HF_TOKEN)
api.upload_file(
    path_or_fileobj=io.BytesIO(json.dumps({
        "url": f"{URL}/v1", "key": API_KEY,
        "model": "v2", "ts": time.time(),
        "platform": "colab",
    }).encode()),
    path_in_repo="current.json",
    repo_id=CONTROL_REPO, repo_type="dataset")

print()
print("═" * 60)
print(f"URL: {URL}/v1")
print(f"KEY: {API_KEY}")
print("═" * 60)

# ─── 9. Keep alive ──────────────────────────────────
while True:
    time.sleep(60)
    if proc.poll() is not None:
        print("✗ server died"); break
    if tun.poll() is not None:
        print("✗ tunnel died"); break
