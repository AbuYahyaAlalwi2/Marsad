"""kaggle_runner.py — يشغّل Kaggle Notebook من Termux تلقائياً."""
import os, json, subprocess, time
from pathlib import Path
from kaggle.api.kaggle_api_extended import KaggleApi

KERNEL_ID = os.environ.get("MARSAD_KERNEL_ID", "goldletter/marsad-merge-v3")


def push_notebook(code: str, kernel_id: str = KERNEL_ID) -> dict:
    """يدفع نوت بوك جديد أو محدّث إلى Kaggle."""
    api = KaggleApi(); api.authenticate()
    user, slug = kernel_id.split("/")
    meta = {
        "id": kernel_id, "title": slug,
        "code_file": "notebook.py",
        "language": "python", "kernel_type": "notebook",
        "is_private": True, "enable_gpu": True,
        "enable_internet": True, "dataset_sources": [],
        "competition_sources": [], "kernel_sources": [],
    }
    tmp = Path("/tmp/marsad_kernel"); tmp.mkdir(exist_ok=True)
    (tmp / "notebook.py").write_text(code)
    (tmp / "kernel-metadata.json").write_text(json.dumps(meta))
    api.kernels_push(str(tmp))
    return {"status": "pushed", "kernel": kernel_id}


def status(kernel_id: str = KERNEL_ID) -> dict:
    api = KaggleApi(); api.authenticate()
    return api.kernels_status(kernel_id)


def wait_for_completion(kernel_id: str = KERNEL_ID, poll: int = 60) -> str:
    """ينتظر حتى ينتهي التشغيل."""
    while True:
        s = status(kernel_id)
        state = s.get("status", "unknown")
        print(f"[{time.strftime('%H:%M')}] status={state}")
        if state in ("complete", "error", "cancelAcknowledged"):
            return state
        time.sleep(poll)


if __name__ == "__main__":
    code = Path("tools/kaggle_merge_notebook.py").read_text()
    print(push_notebook(code))
    print("Waiting...")
    print("Result:", wait_for_completion())
