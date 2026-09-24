"""
مجمع الكروت الموحّد.
- يقرأ كل المفاتيح من Render
- يوزّع المهام حسب قوة الكرت
- يوجّه الصهر للكرت الأقوى
"""
import os
import time
import logging
import threading
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

from db import log_event

logger = logging.getLogger(__name__)


@dataclass
class GPUProvider:
    name: str
    username: str
    token: str
    gpu_type: str = "unknown"
    vram_gb: int = 0
    weekly_hours: int = 0
    priority: int = 5
    available: bool = True
    last_used: float = 0


class GPUPoolManager:
    """
    يدير كل الكروت كوحدة واحدة.
    - الأولوية للصهر: أقوى كرت
    - التدريب: أي كرت
    - الجمع: على Render
    """

    # ترتيب قوة الكروت
    GPU_RANK = {
        "A100": 10, "H100": 10, "L40": 9, "A10G": 8,
        "RTX 6000": 8, "L4": 7, "T4": 5, "P100": 4,
        "M4000": 3, "unknown": 1,
    }

    def __init__(self):
        self.providers: List[GPUProvider] = []
        self._lock = threading.Lock()
        self._load_providers()

    # ==========================================================
    # تحميل المزودين
    # ==========================================================
    def _load_providers(self):
        """يقرأ كل المفاتيح من متغيرات البيئة."""
        self.providers = []

        # 1. كاغل
        for i in range(1, 51):
            user = os.environ.get(f"KAGGLE_USERNAME_{i}", "")
            key = os.environ.get(f"KAGGLE_KEY_{i}", "")
            if user and key:
                self.providers.append(GPUProvider(
                    name=f"kaggle_{i}",
                    username=user,
                    token=key,
                    gpu_type="T4",
                    vram_gb=16,
                    weekly_hours=30,
                    priority=2,
                ))

        # 2. لايتنينغ
        for i in range(1, 51):
            token = os.environ.get(f"LIGHTNING_TOKEN_{i}", "")
            if token:
                self.providers.append(GPUProvider(
                    name=f"lightning_{i}",
                    username=f"lightning_{i}",
                    token=token,
                    gpu_type="L4",
                    vram_gb=24,
                    weekly_hours=80,
                    priority=3,
                ))

        # 3. كولاب
        for i in range(1, 51):
            token = os.environ.get(f"COLAB_TOKEN_{i}", "")
            if token:
                self.providers.append(GPUProvider(
                    name=f"colab_{i}",
                    username=f"colab_{i}",
                    token=token,
                    gpu_type="T4",
                    vram_gb=16,
                    weekly_hours=50,
                    priority=2,
                ))

        # 4. هاغينغ
        hf = os.environ.get("HF_TOKEN", "") or os.environ.get("HUGGINGFACE_TOKEN", "")
        if hf:
            self.providers.append(GPUProvider(
                name="huggingface",
                username="hf",
                token=hf,
                gpu_type="RTX 6000",
                vram_gb=48,
                weekly_hours=100,
                priority=4,
            ))

        # 5. AMD
        for i in range(1, 21):
            token = os.environ.get(f"AMD_TOKEN_{i}", "")
            if token:
                self.providers.append(GPUProvider(
                    name=f"amd_{i}",
                    username=f"amd_{i}",
                    token=token,
                    gpu_type="L40",
                    vram_gb=48,
                    weekly_hours=50,
                    priority=5,
                ))

        # 6. NVIDIA
        for i in range(1, 21):
            token = os.environ.get(f"NVIDIA_TOKEN_{i}", "")
            if token:
                self.providers.append(GPUProvider(
                    name=f"nvidia_{i}",
                    username=f"nvidia_{i}",
                    token=token,
                    gpu_type="A100",
                    vram_gb=80,
                    weekly_hours=30,
                    priority=6,
                ))

        logger.info(f"[مجمع الكروت] تم تحميل {len(self.providers)} كرت")

        # سجّل في قاعدة البيانات
        try:
            log_event("gpu_pool", {
                "action": "load",
                "count": len(self.providers),
                "providers": [p.name for p in self.providers],
            })
        except Exception:
            pass

    # ==========================================================
    # اختيار الكرت المناسب
    # ==========================================================
    def get_strongest(self) -> Optional[GPUProvider]:
        """أقوى كرت متاح — للصهر."""
        with self._lock:
            available = [p for p in self.providers if p.available]
            if not available:
                return None
            return max(available, key=lambda p: (
                self.GPU_RANK.get(p.gpu_type, 0),
                p.vram_gb,
            ))

    def get_lightest(self) -> Optional[GPUProvider]:
        """أضعف كرت متاح — للمهام الخفيفة."""
        with self._lock:
            available = [p for p in self.providers if p.available]
            if not available:
                return None
            return min(available, key=lambda p: p.priority)

    def get_for_task(self, task_type: str) -> Optional[GPUProvider]:
        """
        اختيار الكرت حسب نوع المهمة.
        - صهر: أقوى كرت
        - تدريب: أي كرت متوسط
        - استدلال: أي كرت
        """
        if task_type == "merge":
            return self.get_strongest()
        elif task_type == "train":
            # يحتاج 24 جيجا على الأقل
            with self._lock:
                medium = [p for p in self.providers 
                         if p.available and p.vram_gb >= 24]
                if medium:
                    return medium[0]
            return self.get_lightest()
        else:
            return self.get_lightest()

    # ==========================================================
    # الحالة
    # ==========================================================
    def status(self) -> Dict[str, Any]:
        """حالة المجمع."""
        by_type = {}
        total_vram = 0
        total_hours = 0

        for p in self.providers:
            by_type[p.gpu_type] = by_type.get(p.gpu_type, 0) + 1
            total_vram += p.vram_gb
            total_hours += p.weekly_hours

        strongest = self.get_strongest()

        return {
            "total_providers": len(self.providers),
            "available": sum(1 for p in self.providers if p.available),
            "by_gpu_type": by_type,
            "total_vram_gb": total_vram,
            "weekly_hours": total_hours,
            "strongest": {
                "name": strongest.name if strongest else None,
                "gpu": strongest.gpu_type if strongest else None,
                "vram": strongest.vram_gb if strongest else 0,
            } if strongest else None,
            "providers": [
                {
                    "name": p.name,
                    "gpu": p.gpu_type,
                    "vram": p.vram_gb,
                    "available": p.available,
                }
                for p in self.providers
            ],
        }

    def refresh(self):
        """إعادة تحميل المفاتيح."""
        self._load_providers()
        return self.status()


# نسخة عامة
gpu_pool = GPUPoolManager()
