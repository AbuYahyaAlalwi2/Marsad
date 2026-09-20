"""
CYBERGUARD OS - Control Plane
Orchestrates: Worker Pool, Cloud Layer, Queue, Health, Clinic, Knowledge.
"""
import time
import logging
import threading
from typing import Dict, Any, List

from db import log_event, get_database_stats
from queue_manager import get_backend
from cloud_health import cloud_health
from self_healing import clinic
from knowledge_sharing import knowledge_bus
from config import CLOUD_HEALTH_INTERVAL, SELF_HEALING_HEARTBEAT

logger = logging.getLogger(__name__)


class ControlPlane:
    def __init__(self):
        self._running = False
        self._threads: List[threading.Thread] = []
        self.start_time = time.time()

    def start(self):
        if self._running:
            return
        self._running = True

        logger.info("[Control] Starting subsystems...")
        try:
            log_event("control", {"action": "start"})
        except Exception:
            pass

        cloud_health.start_background()
        clinic.start_watchdog()

        t = threading.Thread(target=self._main_loop, daemon=True)
        t.start()
        self._threads.append(t)

        logger.info("[Control] All subsystems running")

    def stop(self):
        self._running = False
        cloud_health.stop_background()
        clinic.stop_watchdog()
        for t in self._threads:
            t.join(timeout=5)
        try:
            log_event("control", {"action": "stop"})
        except Exception:
            pass

    def _main_loop(self):
        while self._running:
            try:
                self._tick()
            except Exception as e:
                logger.error(f"[Control] tick error: {e}")
            time.sleep(30)

    def _tick(self):
        weak = cloud_health.list_weak()
        if weak:
            logger.info(f"[Control] Weak providers: {weak[:5]}"
                        f"{'...' if len(weak) > 5 else ''}")

        for provider in weak[:3]:
            try:
                from vpn_manager import vpn_manager
                vpn_manager.connect_for_provider(provider)
            except Exception:
                pass

    def status(self) -> Dict[str, Any]:
        db_stats = {}
        try:
            db_stats = get_database_stats()
        except Exception:
            pass

        return {
            "running": self._running,
            "uptime_seconds": int(time.time() - self.start_time),
            "queue_backend": get_backend(),
            "cloud_health": {
                "weak": len(cloud_health.list_weak()),
                "healthy": len(cloud_health.list_healthy()),
            },
            "clinic": clinic.status(),
            "knowledge": knowledge_bus.stats(),
            "database": db_stats,
        }


control_plane = ControlPlane()
