"""Real uploader. No fake simulation and no fake success.

This uploader only succeeds when a real Hugging Face token is configured and the
library is available.
"""

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

try:
    from db import insert_sample, log_event, get_conn, get_untrained_memory, mark_memory_trained, clear_trained_memory
    from config import MEMORY_AUTO_UPLOAD, HF_TOKEN
    from key_manager import key_manager
except ImportError:
    MEMORY_AUTO_UPLOAD = True
    HF_TOKEN = None
    key_manager = None

    def insert_sample(*args, **kwargs):
        pass

    def log_event(*args, **kwargs):
        pass

    def get_conn():
        return None

    def get_untrained_memory(limit):
        return []

    def mark_memory_trained(ids):
        pass

    def clear_trained_memory():
        pass


@dataclass
class UploadResult:
    success: bool
    dataset_id: str = ""
    files_uploaded: int = 0
    error: str = ""
    upload_time: float = 0.0
    metadata: Dict = field(default_factory=dict)


class HuggingFaceUploader:
    def __init__(self):
        self._running = False
        self._thread = None

    def start_auto_upload(self, interval: int = 3600):
        if not MEMORY_AUTO_UPLOAD:
            print("[!] Auto upload is disabled")
            return
        token = HF_TOKEN or (key_manager.get_key("HF_TOKEN") if key_manager else None)
        if not token:
            print("[!] No HF_TOKEN configured. Auto upload skipped.")
            return
        if self._running:
            return
        self._running = True
        import threading
        self._thread = threading.Thread(target=self._auto_upload_loop, args=(interval,), daemon=True)
        self._thread.start()
        print("[+] Auto upload started")

    def stop_auto_upload(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)

    def _auto_upload_loop(self, interval: int):
        while self._running:
            try:
                untrained = get_untrained_memory(limit=100)
                if untrained:
                    result = self.upload_memory_batch(untrained)
                    if result.success:
                        mark_memory_trained([item["id"] for item in untrained])
                time.sleep(interval)
            except Exception as exc:
                log_event("hf_upload", {"action": "auto_upload", "error": str(exc)})
                time.sleep(60)

    def upload_memory_batch(self, memory_items: List[Dict]) -> UploadResult:
        start_time = time.time()
        token = HF_TOKEN or (key_manager.get_key("HF_TOKEN") if key_manager else None)
        if not token:
            return UploadResult(success=False, error="No HF_TOKEN available. Real upload requires a configured token.", upload_time=time.time() - start_time)

        try:
            from huggingface_hub import HfApi, login
            login(token=token)
            api = HfApi()
            dataset = self._prepare_dataset(memory_items)
            timestamp = int(time.time())
            dataset_name = f"cyberguard_memory_{timestamp}"
            repo_id = f"CYBERGUARD/{dataset_name}"
            local_dir = Path(__file__).resolve().parent.parent / "datasets" / dataset_name
            local_dir.mkdir(parents=True, exist_ok=True)
            self._save_dataset_locally(dataset, local_dir)
            api.create_repo(repo_id=repo_id, private=False, repo_type="dataset")
            api.upload_folder(folder_path=str(local_dir), repo_id=repo_id, repo_type="dataset")
            clear_trained_memory()
            log_event("hf_upload", {"action": "upload", "repo_id": repo_id, "items_count": len(memory_items), "status": "success"})
            return UploadResult(success=True, dataset_id=repo_id, files_uploaded=3, upload_time=time.time() - start_time)
        except ImportError:
            return UploadResult(success=False, error="huggingface_hub is not installed. Install it with a real token configured.", upload_time=time.time() - start_time)
        except Exception as exc:
            log_event("hf_upload", {"action": "upload", "error": str(exc)})
            return UploadResult(success=False, error=str(exc), upload_time=time.time() - start_time)

    def _prepare_dataset(self, memory_items: List[Dict]) -> Dict:
        dataset = {"text": [], "metadata": []}
        for item in memory_items:
            dataset["text"].append(item.get("content", ""))
            dataset["metadata"].append({
                "id": item.get("id", 0),
                "hash": item.get("content_hash", ""),
                "created_at": item.get("created_at", 0),
                "trained": item.get("trained", 0),
            })
        return dataset

    def _save_dataset_locally(self, dataset: Dict, local_dir: Path):
        (local_dir / "dataset.json").write_text(json.dumps(dataset, ensure_ascii=False, indent=2), encoding="utf-8")
        csv_lines = ["text,metadata"]
        for text, meta in zip(dataset["text"], dataset["metadata"]):
            csv_lines.append(f'"{text}","{json.dumps(meta)}"')
        (local_dir / "dataset.csv").write_text("\n".join(csv_lines), encoding="utf-8")
        txt = "\n\n---\n\n".join(dataset["text"]) + ("\n\n---\n\n" if dataset["text"] else "")
        (local_dir / "dataset.txt").write_text(txt, encoding="utf-8")


hf_uploader = HuggingFaceUploader()
