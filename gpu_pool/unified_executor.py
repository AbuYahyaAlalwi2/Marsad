"""
المنفّذ الموحّد — يوجّه المهام للكرت المناسب تلقائياً.
"""
import logging
from typing import Dict, Any

from gpu_pool.pool_manager import gpu_pool

logger = logging.getLogger(__name__)


class UnifiedGPUExecutor:
    """يوجّه المهام حسب النوع."""

    # المهام التي تحتاج كرتاً قوياً
    HEAVY = ["merge", "quantization", "full_finetune"]


    def execute(self, task_type: str, payload: Dict = None) -> Dict:
        """يجرّب كل الكروت حتى ينجح."""
        payload = payload or {}
        logger.info(f"[منفّذ] مهمة {task_type}")

        all_gpus = gpu_pool.list_available()
        if not all_gpus:
            return {"status": "no_gpu", "message": "لا يوجد كرت متاح"}

        # رتّب حسب القوة
        all_gpus.sort(
            key=lambda g: gpu_pool.GPU_RANK.get(g.gpu_type, 0),
            reverse=True
        )

        last_error = "no_provider_tried"
        tried = []

        for gpu in all_gpus:
            logger.info(f"[منفّذ] محاولة على {gpu.name} ({gpu.gpu_type})")
            tried.append(gpu.name)
            try:
                result = self._try_provider(gpu, task_type, payload)
                
                if result.get("status") in ("queued", "success"):
                    result["gpu_used"] = {
                        "name": gpu.name,
                        "type": gpu.gpu_type,
                        "vram_gb": gpu.vram_gb,
                    }
                    result["tried"] = tried
                    return result
                
                last_error = result.get("status", "unknown_error")
                logger.warning(f"[منفّذ] فشل {gpu.name}: {last_error}")
            except Exception as e:
                logger.error(f"[منفّذ] خطأ في {gpu.name}: {e}")
                last_error = str(e)

        return {
            "status": "all_providers_failed",
            "last_error": last_error,
            "task": task_type,
            "tried": tried,
        }

    def _try_provider(self, gpu, task_type: str, payload: Dict) -> Dict:
        """يوجّه للمنفّذ الصحيح."""
        if gpu.name.startswith("kaggle_"):
            from gpu_pool.kaggle_deployer import kaggle_deployer
            return kaggle_deployer.run(gpu, task_type, payload)
        elif gpu.name.startswith("saturn_"):
            from gpu_pool.saturn_deployer import saturn_deployer
            return saturn_deployer.run(gpu, task_type, payload)
        elif gpu.name == "huggingface":
            from gpu_pool.huggingface_deployer import huggingface_deployer
            return huggingface_deployer.run(gpu, task_type, payload)
        elif gpu.name.startswith("lightning_"):
            from gpu_pool.lightning_deployer import lightning_deployer
            return lightning_deployer.run(gpu, task_type, payload)
        else:
            return {"status": "unsupported", "provider": gpu.name}

    def execute_merge(self, payload: Dict = None) -> Dict:
        """اختصار للصهر — يستخدم أقوى كرت."""
        return self.execute("merge", payload)

    def execute_train(self, payload: Dict = None) -> Dict:
        """اختصار للتدريب."""
        return self.execute("train", payload)

    def status(self) -> Dict[str, Any]:
        """حالة المنفّذ."""
        return {
            "gpu_pool": gpu_pool.status(),
            "heavy_tasks": self.HEAVY,
        }


unified_executor = UnifiedGPUExecutor()
