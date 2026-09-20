"""
CYBERGUARD OS - Model Merger
Merges programming-focused models (Qwen Coder, DeepSeek, CodeLlama...).
Uses mergekit if available, otherwise produces a merge plan (simulated).
"""
import os
import time
import json
import logging
import subprocess
from typing import Dict, Any

from config import (
    MERGE_STRATEGY, MERGE_OUTPUT_DIR, MERGE_BASE_MODEL,
    PROGRAMMING_MODELS,
)
from db import log_event, insert_merge, update_merge_status

logger = logging.getLogger(__name__)


class ModelMerger:
    def __init__(self):
        self.output_dir = MERGE_OUTPUT_DIR
        os.makedirs(self.output_dir, exist_ok=True)

    def get_plan(self) -> Dict[str, Any]:
        return {
            "strategy": MERGE_STRATEGY,
            "base_model": MERGE_BASE_MODEL,
            "models": PROGRAMMING_MODELS,
            "total_models": len(PROGRAMMING_MODELS),
            "output_dir": self.output_dir,
            "focus": "programming",
        }

    def merge_all(self) -> Dict[str, Any]:
        merge_id = f"merge_{int(time.time())}"

        try:
            insert_merge(
                merge_id=merge_id,
                base_model=MERGE_BASE_MODEL,
                models=[m["name"] for m in PROGRAMMING_MODELS],
                output_path=self.output_dir,
            )
        except Exception as e:
            logger.warning(f"[Merger] DB insert failed: {e}")

        try:
            log_event("merger", {"merge_id": merge_id, "status": "started",
                                 "strategy": MERGE_STRATEGY})
        except Exception:
            pass

        config_path = self._write_config(merge_id)
        result = self._run_mergekit(config_path)

        try:
            update_merge_status(
                merge_id,
                "completed" if result.get("status") in ("ok", "simulated") else "failed"
            )
        except Exception:
            pass

        return {"merge_id": merge_id, **result, "config_path": config_path}

    def merge_simulated(self) -> Dict[str, Any]:
        merge_id = f"merge_sim_{int(time.time())}"
        meta_path = os.path.join(self.output_dir, f"{merge_id}.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump({
                "merge_id": merge_id,
                "strategy": MERGE_STRATEGY,
                "base_model": MERGE_BASE_MODEL,
                "models": PROGRAMMING_MODELS,
                "simulated": True,
                "created_at": time.time(),
            }, f, indent=2, ensure_ascii=False)

        try:
            log_event("merger", {"merge_id": merge_id, "status": "simulated"})
        except Exception:
            pass

        return {"status": "simulated", "merge_id": merge_id, "path": meta_path}

    def _write_config(self, merge_id: str) -> str:
        config = {
            "merge_method": MERGE_STRATEGY,
            "base_model": MERGE_BASE_MODEL,
            "models": [
                {"model": m["path"], "parameters": {"weight": m["weight"]}}
                for m in PROGRAMMING_MODELS
            ],
            "parameters": {"normalize": True},
            "dtype": "bfloat16",
        }
        path = os.path.join(self.output_dir, f"{merge_id}.yaml")

        try:
            import yaml
            with open(path, "w", encoding="utf-8") as f:
                yaml.safe_dump(config, f, allow_unicode=True)
        except ImportError:
            with open(path, "w", encoding="utf-8") as f:
                f.write(json.dumps(config, indent=2))

        return path

    def _run_mergekit(self, config_path: str) -> Dict[str, Any]:
        try:
            subprocess.run(["mergekit-yaml", "--version"],
                           capture_output=True, timeout=5)
        except Exception:
            logger.info("[Merger] mergekit not installed - producing plan only")
            return self.merge_simulated()

        output_path = os.path.join(self.output_dir, "merged")
        try:
            proc = subprocess.run(
                ["mergekit-yaml", config_path, output_path,
                 "--copy-tokenizer", "--allow-crimes",
                 "--out-shard-size", "2B", "--lazy-unpickle"],
                capture_output=True, text=True, timeout=3600,
            )
            if proc.returncode == 0:
                return {"status": "ok", "output_path": output_path}
            return {"status": "error", "error": proc.stderr[-2000:]}
        except subprocess.TimeoutExpired:
            return {"status": "timeout"}
        except Exception as e:
            return {"status": "error", "error": str(e)}


model_merger = ModelMerger()
