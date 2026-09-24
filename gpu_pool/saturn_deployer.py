"""منفّذ ساتورن كلاود — يشغّل المهام عبر API."""
import os
import json
import time
import logging
import requests
from typing import Dict, Any

logger = logging.getLogger(__name__)


class SaturnDeployer:
    """يشغّل مهام على Saturn Cloud."""

    BASE_URL = "https://app.compute.studio/api"

    def run(self, provider, task_type: str, payload: Dict) -> Dict:
        """يشغّل مهمة على ساتورن."""
        headers = {
            "Authorization": f"Bearer {provider.token}",
            "Content-Type": "application/json",
        }

        try:
            # 1. افحص المفتاح
            r = requests.get(
                f"{self.BASE_URL}/user/profile",
                headers=headers, timeout=30,
            )
            if r.status_code != 200:
                return {
                    "status": "auth_failed",
                    "provider": provider.name,
                    "http": r.status_code,
                }

            # 2. جهّز المهمة حسب النوع
            if task_type == "merge":
                job_config = self._build_merge_job(payload)
            elif task_type == "train":
                job_config = self._build_train_job(payload)
            else:
                job_config = self._build_generic_job(task_type, payload)

            # 3. أرسل المهمة
            job_name = f"marsad-{task_type}-{int(time.time())}"
            r = requests.post(
                f"{self.BASE_URL}/jobs",
                headers=headers,
                json={"name": job_name, "config": job_config},
                timeout=60,
            )

            if r.status_code in (200, 201, 202):
                data = r.json() if r.text else {}
                return {
                    "status": "queued",
                    "provider": provider.name,
                    "job_id": data.get("id", job_name),
                    "gpu": provider.gpu_type,
                    "url": data.get("url", ""),
                }
            return {
                "status": f"http_{r.status_code}",
                "provider": provider.name,
                "output": r.text[:300],
            }

        except Exception as e:
            logger.error(f"[Saturn] خطأ: {e}")
            return {"status": "error", "provider": provider.name, "error": str(e)}

    def _build_merge_job(self, payload):
        """يبني مهمة صهر."""
        return {
            "command": "mergekit-yaml",
            "args": [
                "/configs/merge.yaml", "/output",
                "--copy-tokenizer", "--allow-crimes", "--low-cpu-mem",
            ],
            "gpu": "a10g",
            "image": "python:3.11",
            "env": {
                "MERGE_CONFIG": json.dumps(payload or {}),
            },
        }

    def _build_train_job(self, payload):
        """يبني مهمة تدريب."""
        return {
            "command": "python",
            "args": ["/scripts/train_lora.py"],
            "gpu": "a10g",
            "image": "python:3.11",
            "env": {
                "TRAIN_CONFIG": json.dumps(payload or {}),
            },
        }

    def _build_generic_job(self, task_type, payload):
        """مهمة عامة."""
        return {
            "command": "python",
            "args": ["-c", f"print('task: {task_type}')"],
            "gpu": "a10g",
            "image": "python:3.11",
        }


saturn_deployer = SaturnDeployer()
