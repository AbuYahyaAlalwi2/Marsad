"""
Kaggle Notebook — serve v2 as OpenAI-compatible API
- GGUF conversion + llama-server + Cloudflare tunnel
"""
import os, sys, time, subprocess, json, re
from pathlib import Path

try:
    from kaggle_secrets import UserSecretsClient
    HF_TOKEN = UserSecretsClient().get_secret("HF_TOKEN")
except Exception:
    HF_TOKEN = os.environ.get("HF_TOKEN", "")
assert HF_TOKEN, "Add HF_TOKEN in Kaggle Secrets"

os.environ["HF_TOKEN"] = HF_TOKEN
os.environ["HUGGING_FACE_HUB_TOKEN"] = HF_TOKEN
from huggingface_hub import login
login(token=HF_TOKEN)
print("✓ HF authenticated")

subprocess.run([sys.executable, "-m", "pip", "install", "-q",
                "transformers", "torch", "sentencepiece",
                "protobuf", "huggingface_hub", "accelerate"], check=True)

LLAMA_DIR = Path("/kaggle/working/llama.cpp")
if not (LLAMA_DIR / "build/bin/llama-server").exists():
    print("→ cloning llama.cpp...")
    subprocess.run(["git", "clone", "--depth=1",
                    "https://github.com/ggml-org/llama.cpp.git",
                    str(LLAMA_DIR)], check=True)
    subprocess.run("ln -sf /usr/local/nvidia/lib64/libcuda.so /usr/local/cuda/lib64/libcuda.so", shell=True)
    print("→ building (sm_75)...")
    subprocess.run(["cmake", "-B", str(LLAMA_DIR / "build"),
                    "-DGGML_CUDA=ON",
                    "-DCMAKE_CUDA_ARCHITECTURES=75",
                    "-DCMAKE_PREFIX_PATH=/usr/local/nvidia",
                    "-DLLAMA_CURL=OFF",
                    "-DCMAKE_BUILD_TYPE=Release"],
                   cwd=str(LLAMA_DIR), check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["cmake", "--build", str(LLAMA_DIR / "build"),
                    "--config", "Release", "-j4"],
                   cwd=str(LLAMA_DIR), check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("✓ llama.cpp built")

LLAMA_SERVER = str(LLAMA_DIR / "build/bin/llama-server")

HF_MODEL = "AbuYahya2/deepseek-marsad-v2"
GGUF_PATH = Path("/kaggle/working/model.gguf")
LOCAL_MODEL = Path("/kaggle/working/v2")

if not GGUF_PATH.exists():
    print("→ downloading v2...")
    from huggingface_hub import snapshot_download
    snapshot_download(repo_id=HF_MODEL, local_dir=str(LOCAL_MODEL),
                     token=HF_TOKEN,
                     ignore_patterns=["*.gguf", "*.pth", "*.bin"])
    print("→ converting to GGUF...")
    subprocess.run([sys.executable,
                    str(LLAMA_DIR / "convert_hf_to_gguf.py"),
                    str(LOCAL_MODEL), "--outtype", "f16",
                    "--outfile", str(GGUF_PATH)], check=True)
    print(f"✓ GGUF: {GGUF_PATH}")

print("→ starting server...")
server_log = open("/kaggle/working/llama_server.log", "w")
server_proc = subprocess.Popen(
    [LLAMA_SERVER, "--host", "0.0.0.0", "--port", "8080",
     "--model", str(GGUF_PATH), "--n-gpu-layers", "99",
     "--ctx-size", "8192", "--threads", "4",
     "--parallel", "1", "--cont-batching"],
    stdout=server_log, stderr=subprocess.STDOUT)

deadline = time.time() + 300
ready = False
while time.time() < deadline:
    try:
        r = subprocess.run(["curl", "-s", "-o", "/dev/null",
                            "-w", "%{http_code}",
                            "http://127.0.0.1:8080/health"],
                           capture_output=True, text=True, timeout=5)
        if r.stdout.strip() == "200":
            ready = True; break
    except Exception:
        pass
    time.sleep(3)
assert ready, "server did not start"
print("✓ server ready :8080")

print("→ installing cloudflared...")
CF_BIN = Path("/kaggle/working/cloudflared")
if not CF_BIN.exists():
    subprocess.run(["wget", "-q",
                    "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64",
                    "-O", str(CF_BIN)], check=True)
    CF_BIN.chmod(0o755)

print("→ starting tunnel...")
tunnel_proc = subprocess.Popen(
    [str(CF_BIN), "tunnel", "--url", "http://127.0.0.1:8080", "--no-autoupdate"],
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)

URL = None
pat = re.compile(r"https://[-a-z0-9]+\.trycloudflare\.com")
deadline = time.time() + 120
while time.time() < deadline:
    line = tunnel_proc.stdout.readline()
    if not line: continue
    print("[cloudflared]", line.rstrip())
    m = pat.search(line)
    if m:
        URL = m.group(0); break
assert URL, "tunnel failed"

Path("/kaggle/working/server_url.txt").write_text(URL + "\n")
Path("/kaggle/working/server_info.json").write_text(json.dumps({
    "url": URL, "model": HF_MODEL, "endpoint": f"{URL}/v1",
    "started_at": time.time()
}, indent=2))

print()
print("═" * 60)
print(f"✓ API: {URL}/v1")
print(f"✓ saved: /kaggle/working/server_url.txt")
print("═" * 60)
print("⚠️  keep this notebook running")

while True:
    time.sleep(60)
    if server_proc.poll() is not None:
        print("✗ server died"); break
    if tunnel_proc.poll() is not None:
        print("✗ tunnel died"); break
