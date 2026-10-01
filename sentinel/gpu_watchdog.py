"""
GPU Watchdog — يراقب حالة LLM ويعيد التشغيل تلقائياً.
- يقرأ current.json من HF
- يختبر الاتصال
- إذا فشل → يشغّل Kaggle (عبر API)
"""
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

HF_ENDPOINT = "https://huggingface.co/datasets/AbuYahya2/marsad-endpoints/raw/main/current.json"
KAGGLE_DIR = Path.home() / "Marsad" / "kaggle-deploy"
CHECK_INTERVAL = 300   # 5 دقائق
LOG = Path.home() / "marsad_logs" / "watchdog.log"
LOG.parent.mkdir(parents=True, exist_ok=True)


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def get_current_endpoint():
    try:
        r = httpx.get(HF_ENDPOINT, timeout=15)
        if r.status_code != 200:
            return None
        return r.json()
    except Exception as e:
        log(f"fetch endpoint failed: {e}")
        return None


def test_llm(endpoint: dict) -> bool:
    """يختبر أن LLM يرد."""
    try:
        r = httpx.post(
            f"{endpoint['url']}/chat/completions",
            headers={"Authorization": f"Bearer {endpoint['key']}",
                     "Content-Type": "application/json"},
            json={"model": "v2",
                  "messages": [{"role": "user", "content": "ping"}],
                  "max_tokens": 3},
            timeout=30)
        return r.status_code == 200
    except Exception as e:
        log(f"test failed: {e}")
        return False


def restart_kaggle():
    """يشغّل Kaggle kernel عبر API."""
    try:
        sys.path.insert(0, str(Path.home() / "Marsad"))
        os.chdir(str(KAGGLE_DIR))
        result = subprocess.run(
            ["python3", "-c",
             "from kaggle.api.kaggle_api_extended import KaggleApi; "
             "api = KaggleApi(); api.authenticate(); "
             "api.kernels_push('/data/data/com.termux/files/home/Marsad/kaggle-deploy'); "
             "print('pushed')"],
            capture_output=True, text=True, timeout=120)
        if "pushed" in result.stdout:
            log("✓ Kaggle restarted")
            return True
        log(f"kaggle restart failed: {result.stderr[:200]}")
        return False
    except Exception as e:
        log(f"kaggle exception: {e}")
        return False


def main():
    log("═══ Watchdog started ═══")
    consecutive_fails = 0

    while True:
        try:
            endpoint = get_current_endpoint()

            if not endpoint:
                log("no endpoint — waiting")
                time.sleep(CHECK_INTERVAL)
                continue

            log(f"checking {endpoint.get('platform', '?')} | {endpoint.get('ts', '?')}")

            if test_llm(endpoint):
                log(f"✓ LLM alive")
                consecutive_fails = 0
            else:
                consecutive_fails += 1
                log(f"✗ fail #{consecutive_fails}")

                if consecutive_fails >= 2:
                    log("→ attempting Kaggle restart...")
                    if restart_kaggle():
                        consecutive_fails = 0
                        log("→ waiting 5min for kernel to boot")
                        time.sleep(300)
                    else:
                        log("→ Kaggle restart failed — try Colab manually")
                        consecutive_fails = 0

        except KeyboardInterrupt:
            log("stopped by user")
            break
        except Exception as e:
            log(f"loop error: {e}")

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
