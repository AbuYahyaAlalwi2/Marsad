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
        """يختار الكرت المناسب ويشغّل المهمة."""
        payload = payload or {}
        
        logger.info(f"[منفّذ] مهمة {task_type}")

        # اختر الكرت
        gpu = gpu_pool.get_for_task(task_type)
        if not gpu:
            return {
                "status": "no_gpu",
                "message": "لا يوجد كرت متاح",
                "task": task_type,
            }

        logger.info(f"[منفّذ] → {gpu.name} ({gpu.gpu_type})")

        # وجّه للمنفّذ المناسب
        try:
            if gpu.name.startswith("kaggle_"):
                from gpu_pool.kaggle_deployer import kaggle_deployer
                result = kaggle_deployer.run(gpu, task_type, payload)
            elif gpu.name.startswith("saturn_"):
                from gpu_pool.saturn_deployer import saturn_deployer
                result = saturn_deployer.run(gpu, task_type, payload)
            elif gpu.name.startswith("lightning_"):
                from gpu_pool.lightning_deployer import lightning_deployer
                result = lightning_deployer.run(gpu, task_type, payload)
            else:
                result = {
                    "status": "unsupported",
                    "provider": gpu.name,
                }

            result["gpu_used"] = {
                "name": gpu.name,
                "type": gpu.gpu_type,
                "vram_gb": gpu.vram_gb,
            }

            # علّم الكرت كمستخدم
            gpu.last_used = __import__("time").time()

            return result
        except Exception as e:
            logger.error(f"[منفّذ] خطأ: {e}")
            return {
                "status": "error",
                "error": str(e),
                "gpu_used": gpu.name,
            }

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
