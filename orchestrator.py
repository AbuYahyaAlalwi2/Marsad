"""
CYBERGUARD OS - Autonomous Orchestrator
Runs the full loop: collect -> clean -> train -> merge -> upload.
All autonomous, all scheduled, all resilient.
"""
import os
import time
import logging
import threading
from typing import Dict, Any, Optional

from db import log_event, get_memory_size_gb, get_task_stats
try:
    from free_merger import free_merger
except ImportError:
    free_merger = None
try:
    from core.constitution import constitution_guard
except ImportError:
    constitution_guard = None
from config import MEMORY_MAX_GB, MEMORY_AUTO_TRAIN, MEMORY_AUTO_UPLOAD

logger = logging.getLogger(__name__)


class AutonomousOrchestrator:
    """
    The engine that keeps everything moving:
      - every N minutes: collect from platforms
      - every M minutes: clean + train on new data
      - every hour: merge models
      - every hour: upload to HuggingFace
      - continuous: monitor clouds, heal agents
    """

    def __init__(self):
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self.cycle_count = 0
        self.last_cycle_at = 0
        self.stats = {
            "collections": 0,
            "cleanings": 0,
            "trainings": 0,
            "merges": 0,
            "uploads": 0,
            "errors": 0,
        }

        # intervals (seconds)
        self.interval_collect = int(os.environ.get("CG_ORCH_COLLECT", "600"))    # 10 min
        self.interval_train = int(os.environ.get("CG_ORCH_TRAIN", "1800"))       # 30 min
        self.interval_merge = int(os.environ.get("CG_ORCH_MERGE", "3600"))       # 1 hour
        self.interval_upload = int(os.environ.get("CG_ORCH_UPLOAD", "3600"))     # 1 hour
        self.interval_loop = int(os.environ.get("CG_ORCH_LOOP", "60"))           # every 60s

    # ------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------

    def start(self):
        if self._running:
            return
        self._running = True
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info("[Orchestrator] Started")
        try:
            log_event("orchestrator", {"action": "start"})
        except Exception:
            pass

    def stop(self):
        self._running = False
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("[Orchestrator] Stopped")

    def _loop(self):
        """Main loop - dispatches tasks based on schedule."""
        # do one immediate collect on startup
        try:
            self._task_collect()
        except Exception as e:
            logger.error(f"[Orchestrator] initial collect failed: {e}")

        while not self._stop.is_set():
            self.cycle_count += 1
            self.last_cycle_at = time.time()
            try:
                self._dispatch()
            except Exception as e:
                self.stats["errors"] += 1
                logger.error(f"[Orchestrator] cycle error: {e}")
            self._stop.wait(self.interval_loop)

    def _dispatch(self):
        """Run whatever is due this cycle."""
        now = time.time()
        # Track last run times (initialized to 0 so first run happens immediately)
        if not hasattr(self, "_last"):
            self._last = {"collect": now, "train": now, "merge": now, "upload": now}

        if now - self._last["collect"] >= self.interval_collect:
            self._task_collect()
            self._last["collect"] = now

        if now - self._last["train"] >= self.interval_train:
            self._task_train()
            self._last["train"] = now

        if now - self._last["merge"] >= self.interval_merge:
            self._task_merge()
            self._last["merge"] = now

        if now - self._last["upload"] >= self.interval_upload:
            self._task_upload()
            self._last["upload"] = now

    # ------------------------------------------------------------
    # Tasks
    # ------------------------------------------------------------

    def _task_collect(self):
        """Collect data from platforms."""
        logger.info("[Orchestrator] Collecting data...")
        try:
            from collect.multi_platform import collector
            result = collector.collect_all(
                query=os.environ.get("CG_ORCH_QUERY", "security vulnerability"),
                limit=20,
            )
            self.stats["collections"] += 1
            log_event("orchestrator", {
                "action": "collect",
                "platforms": len(result) if isinstance(result, dict) else 0,
            })
            logger.info(f"[Orchestrator] Collect done: {len(result) if result else 0} platforms")
        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"[Orchestrator] collect error: {e}")

    def _task_train(self):
        """Clean + train on new memory."""
        # فحص الدستور
        if constitution_guard:
            check = constitution_guard.check_command("train model on new memory")
            if not check.get("allowed"):
                logger.warning(f"الدستور منع التدريب: {check}")
                return
        
        logger.info("[Orchestrator] Training cycle...")
        try:
            # Check memory size
            mem_gb = get_memory_size_gb()
            if mem_gb < 0.001:
                logger.info("[Orchestrator] Not enough memory to train")
                return

            # Trigger memory auto-processing
            try:
                from core.memory import memory
                memory._auto_process()
                self.stats["trainings"] += 1
                log_event("orchestrator", {"action": "train", "mem_gb": mem_gb})
                logger.info(f"[Orchestrator] Training done (mem: {mem_gb:.3f} GB)")
            except Exception as e:
                logger.warning(f"[Orchestrator] train inner failed: {e}")
        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"[Orchestrator] train error: {e}")

    def _task_merge(self):
        """Merge models - uses free_merger if available."""
        logger.info("[Orchestrator] Merge cycle...")
        try:
            if free_merger:
                result = free_merger.merge(strategy="auto")
                self.stats["merges"] += 1
                log_event("orchestrator", {
                    "action": "merge",
                    "status": result.get("status"),
                    "method": result.get("method"),
                })
                logger.info(f"[Orchestrator] Merge: {result.get('status')}")
            else:
                from model_merger import model_merger
                result = model_merger.merge_all()
                self.stats["merges"] += 1
                log_event("orchestrator", {"action": "merge", "status": result.get("status")})
        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"[Orchestrator] merge error: {e}")

    def _task_upload(self):
        """Upload to HuggingFace - runs every cycle if there is data."""
        logger.info("[Orchestrator] Upload cycle...")
        try:
            if not hf_uploader:
                logger.info("[Orchestrator] hf_uploader not available")
                return
            from db import get_untrained_memory
            pending = get_untrained_memory(limit=200)
            if not pending:
                logger.info("[Orchestrator] Nothing to upload")
                return
            
            # ارفع
            result = hf_uploader.upload_memory_batch(pending)
            success = result.success if hasattr(result, "success") else False
            
            if success:
                self.stats["uploads"] += 1
                log_event("orchestrator", {
                    "action": "upload",
                    "success": True,
                    "count": len(pending),
                    "dataset_id": getattr(result, "dataset_id", ""),
                })
                logger.info(f"[Orchestrator] Upload OK: {len(pending)} items")
            else:
                log_event("orchestrator", {
                    "action": "upload",
                    "success": False,
                    "error": getattr(result, "error", "unknown"),
                })
                logger.warning(f"[Orchestrator] Upload failed")
        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"[Orchestrator] upload error: {e}")

    # ------------------------------------------------------------
    # Status
    # ------------------------------------------------------------

    def status(self) -> Dict[str, Any]:
        return {
            "running": self._running,
            "cycles": self.cycle_count,
            "last_cycle_at": self.last_cycle_at,
            "stats": self.stats,
            "intervals": {
                "collect": self.interval_collect,
                "train": self.interval_train,
                "merge": self.interval_merge,
                "upload": self.interval_upload,
            },
        }


# Singleton
orchestrator = AutonomousOrchestrator()
