import os, sys, subprocess, shutil, glob, json, re, time, io
from pathlib import Path

HF_TOKEN = "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"
API_KEY = "marsad-" + os.urandom(16).hex()
print(f"✓ API key: {API_KEY[:20]}...")

# CUDA
subprocess.run([sys.executable, "-m", "pip", "install", "-q",
                "nvidia-cuda-runtime-cu12",
                "nvidia-cublas-cu12",
                "nvidia-cuda-nvrtc-cu12"], check=True)

import nvidia
cuda_libs = []
for sub in Path(nvidia.__path__[0]).iterdir():
    if sub.is_dir():
        for ld in [sub / "lib", sub / "lib64"]:
            if ld.exists():
                cuda_libs.append(str(ld))

# llama-server
hits = glob.glob("/kaggle/input/**/llama-server", recursive=True)
assert hits, "Add dataset llama-cpp-bin"
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

env = os.environ.copy()
env["GGML_CUDA_NO_PINNED"] = "1"
env["LD_LIBRARY_PATH"] = ":".join(
    [str(WORK), "/usr/local/nvidia/lib64", *cuda_libs,
     env.get("LD_LIBRARY_PATH", "")])

# Download GGUF
from huggingface_hub import hf_hub_download
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

# Server
print("→ starting llama-server...")
log = open("/kaggle/working/server.log", "w")
proc = subprocess.Popen(
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
    if proc.poll() is not None:
        break
    time.sleep(5)

if not ready:
    print(Path("/kaggle/working/server.log").read_text()[-3000:])
    raise RuntimeError("server did not start")
print("✓ server ready")

# Tunnel
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
print(f"\nURL: {URL}/v1")
print(f"KEY: {API_KEY}")

# ─── ارفع URL إلى HuggingFace ────────────────────────────
try:
    from huggingface_hub import HfApi, create_repo
    create_repo(repo_id="AbuYahya2/marsad-endpoints",
                repo_type="dataset", token=HF_TOKEN, exist_ok=True)
    api = HfApi(token=HF_TOKEN)
    payload = json.dumps({
        "url": f"{URL}/v1", "key": API_KEY,
        "model": "v2", "ts": time.time(),
    }, indent=2)
    api.upload_file(
        path_or_fileobj=io.BytesIO(payload.encode()),
        path_in_repo="current.json",
        repo_id="AbuYahya2/marsad-endpoints",
        repo_type="dataset")
    print("✓ URL uploaded to HF")
except Exception as e:
    print(f"⚠️ HF upload failed: {e}")

print("═" * 60)
print(f"API: {URL}/v1")
print("═" * 60)

# Keep alive
while True:
    time.sleep(60)
    if proc.poll() is not None:
        print("✗ server died"); break
    if tun.poll() is not None:
        print("✗ tunnel died"); break
