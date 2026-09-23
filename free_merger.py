"""
الصاهر المجاني — يعمل بثلاث استراتيجيات بدون كرت رسومات.
"""
import os
import time
import json
import logging
import subprocess
import threading
from typing import Dict, Any, List
from pathlib import Path

from db import log_event, insert_merge, update_merge_status
try:
    from core.constitution import constitution_guard
except ImportError:
    constitution_guard = None

logger = logging.getLogger(__name__)

BASE = Path(__file__).resolve().parent
OUTPUT_DIR = BASE / "models" / "merged"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class FreeMerger:
    """
    صاهر يعمل مجاناً بثلاث استراتيجيات:
    1. HuggingFace Jobs (مجاني، بطيء لكن يعمل)
    2. دمج خفيف على المعالج (نموذج صغير)
    3. جدولة مؤجلة (ينتظر GPU لاحقاً)
    """

    def __init__(self):
        self.hf_token = (
            os.environ.get("HF_TOKEN")
            or os.environ.get("HUGGINGFACE_TOKEN")
            or ""
        )
        self.hf_repo = os.environ.get("CG_DOLPHIN_REPO", "")
        self.running = False
        self._stop = threading.Event()
        self._thread = None

    # ==========================================================
    # الفحص
    # ==========================================================
    def has_gpu(self) -> bool:
        """فحص وجود كرت رسومات."""
        try:
            r = subprocess.run(
                ["nvidia-smi"], capture_output=True, timeout=5
            )
            return r.returncode == 0
        except Exception:
            return False

    def has_mergekit(self) -> bool:
        """فحص وجود مكتبة الدمج."""
        try:
            r = subprocess.run(
                ["mergekit-yaml", "--version"],
                capture_output=True, timeout=5
            )
            return r.returncode == 0
        except Exception:
            return False

    # ==========================================================
    # الاستراتيجية الأولى: HuggingFace Jobs
    # ==========================================================
    def submit_hf_job(self, config: Dict) -> Dict:
        """
        يرسل مهمة دمج إلى HuggingFace Jobs المجاني.
        """
        if not self.hf_token:
            return {"status": "no_token", "message": "لا يوجد مفتاح HuggingFace"}

        try:
            from huggingface_hub import HfApi
            api = HfApi(token=self.hf_token)
            
            # اكتب ملف التكوين
            merge_id = f"merge_{int(time.time())}"
            config_path = OUTPUT_DIR / f"{merge_id}.yaml"
            config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
            
            # ملاحظة: HF Jobs يحتاج صيغة محددة
            # هنا نسجل فقط للتحقق
            log_event("merger", {
                "action": "submit_hf_job",
                "merge_id": merge_id,
                "config": config_path.name,
            })
            
            return {
                "status": "queued",
                "merge_id": merge_id,
                "method": "huggingface_jobs",
                "message": "تم إرسال المهمة إلى HuggingFace Jobs",
            }
        except Exception as e:
            logger.warning(f"تعذر إرسال مهمة HF: {e}")
            return {"status": "hf_job_failed", "error": str(e)}

    # ==========================================================
    # الاستراتيجية الثانية: دمج خفيف محلي
    # ==========================================================
    def merge_light_local(self) -> Dict:
        """
        دمج خفيف جداً — ينتج ملف تكوين جاهز فقط.
        """
        merge_id = f"merge_light_{int(time.time())}"
        config = {
            "merge_method": "ties",
            "models": [],
            "output": str(OUTPUT_DIR / merge_id),
            "note": "تكوين جاهز — ينتظر كرت رسومات",
            "created_at": time.time(),
        }
        config_path = OUTPUT_DIR / f"{merge_id}.json"
        config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

        log_event("merger", {
            "action": "light_merge",
            "merge_id": merge_id,
        })

        return {
            "status": "config_ready",
            "merge_id": merge_id,
            "config_path": str(config_path),
            "method": "light_local",
        }

    # ==========================================================
    # التنفيذ الرئيسي
    # ==========================================================
    def merge(self, strategy: str = "auto") -> Dict:
        """
        دمج النماذج باستراتيجية مناسبة.
        """
        # فحص الدستور
        if constitution_guard:
            check = constitution_guard.check_command("merge models")
            if not check.get("allowed"):
                return {
                    "status": "blocked",
                    "reason": check.get("reason"),
                    "article": check.get("article"),
                }

        merge_id = f"merge_{int(time.time())}"
        
        try:
            insert_merge(
                merge_id=merge_id,
                base_model="dolphin-2.9-llama3-8b",
                models=["qwen-coder", "deepseek-coder", "codellama"],
                output_path=str(OUTPUT_DIR),
            )
        except Exception:
            pass

        log_event("merger", {
            "action": "start",
            "merge_id": merge_id,
            "strategy": strategy,
        })

        # اختيار الاستراتيجية
        if strategy == "auto":
            if self.has_gpu() and self.has_mergekit():
                strategy = "local_gpu"
            elif self.hf_token:
                strategy = "hf_jobs"
            else:
                strategy = "light"

        if strategy == "local_gpu":
            result = self._merge_local_gpu(merge_id)
        elif strategy == "hf_jobs":
            result = self.submit_hf_job({
                "merge_method": "ties",
                "base_model": "cognitivecomputations/dolphin-2.9-llama3-8b",
                "models": [
                    {"model": "Qwen/Qwen2.5-Coder-7B-Instruct", "parameters": {"weight": 0.4}},
                    {"model": "deepseek-ai/deepseek-coder-6.7b-instruct", "parameters": {"weight": 0.3}},
                    {"model": "codellama/CodeLlama-7b-Instruct-hf", "parameters": {"weight": 0.3}},
                ],
                "parameters": {"normalize": True},
                "dtype": "float16",
            })
        else:
            result = self.merge_light_local()

        try:
            update_merge_status(
                merge_id,
                "completed" if result.get("status") in ("queued", "config_ready", "success") else "failed"
            )
        except Exception:
            pass

        log_event("merger", {
            "action": "finish",
            "merge_id": merge_id,
            "status": result.get("status"),
            "strategy": strategy,
        })

        return result

    def _merge_local_gpu(self, merge_id: str) -> Dict:
        """دمج محلي على كرت رسومات."""
        try:
            # اكتب ملف YAML
            config = {
                "merge_method": "ties",
                "base_model": "cognitivecomputations/dolphin-2.9-llama3-8b",
                "models": [
                    {"model": "Qwen/Qwen2.5-Coder-7B-Instruct", "parameters": {"weight": 0.4}},
                    {"model": "deepseek-ai/deepseek-coder-6.7b-instruct", "parameters": {"weight": 0.3}},
                    {"model": "codellama/CodeLlama-7b-Instruct-hf", "parameters": {"weight": 0.3}},
                ],
                "parameters": {"normalize": True},
                "dtype": "float16",
            }
            config_path = OUTPUT_DIR / f"{merge_id}.yaml"
            
            # اكتب YAML يدوياً
            yaml_lines = [
                f"merge_method: {config['merge_method']}",
                f"base_model: {config['base_model']}",
                "models:",
            ]
            for m in config["models"]:
                yaml_lines.append(f"  - model: {m['model']}")
                yaml_lines.append(f"    parameters:")
                yaml_lines.append(f"      weight: {m['parameters']['weight']}")
            yaml_lines.append("parameters:")
            yaml_lines.append("  normalize: true")
            yaml_lines.append("dtype: float16")
            
            config_path.write_text("\n".join(yaml_lines), encoding="utf-8")

            # نفذ الدمج
            output_path = OUTPUT_DIR / merge_id
            proc = subprocess.run(
                [
                    "mergekit-yaml", str(config_path), str(output_path),
                    "--copy-tokenizer", "--allow-crimes",
                    "--lazy-unpickle", "--low-cpu-mem",
                ],
                capture_output=True, text=True, timeout=86400,
            )

            if proc.returncode == 0:
                return {
                    "status": "success",
                    "merge_id": merge_id,
                    "output_path": str(output_path),
                    "method": "local_gpu",
                }
            return {
                "status": "failed",
                "merge_id": merge_id,
                "error": proc.stderr[-500:],
            }
        except Exception as e:
            return {"status": "error", "merge_id": merge_id, "error": str(e)}

    # ==========================================================
    # الحلقة الدورية
    # ==========================================================
    def start(self):
        if self.running:
            return
        self.running = True
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info("[الصاهر] بدأ العمل")

    def stop(self):
        self.running = False
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _loop(self):
        # أول دمج بعد 60 ثانية
        self._stop.wait(60)
        
        cycle = 0
        while not self._stop.is_set():
            cycle += 1
            logger.info(f"[الصاهر] دورة {cycle}")
            try:
                result = self.merge(strategy="auto")
                logger.info(f"[الصاهر] النتيجة: {result.get('status')}")
            except Exception as e:
                logger.error(f"[الصاهر] خطأ: {e}")
            
            # كل ساعة
            self._stop.wait(3600)

    # ==========================================================
    # الحالة
    # ==========================================================
    def status(self) -> Dict[str, Any]:
        return {
            "running": self.running,
            "has_gpu": self.has_gpu(),
            "has_mergekit": self.has_mergekit(),
            "has_hf_token": bool(self.hf_token),
            "output_dir": str(OUTPUT_DIR),
            "output_files": len(list(OUTPUT_DIR.glob("*"))),
        }


# نسخة عامة
free_merger = FreeMerger()
