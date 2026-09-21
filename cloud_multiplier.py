"""
CYBERGUARD OS - Cloud Multiplier

AGENTS = FIXED (1,000,000 working always)
CLOUDS = DOUBLE when load increases

Example:
  10 clouds x 100,000 agents each = 1,000,000 agents
  20 clouds x  50,000 agents each = 1,000,000 agents
  40 clouds x  25,000 agents each = 1,000,000 agents

Goal: spread 1M agents across more clouds to keep each healthy.
"""
import os
import time
import logging
import threading
from typing import Dict, Any, List

from db import log_event

logger = logging.getLogger(__name__)


class CloudMultiplier:
    """
    Keeps agents fixed at 1M, but doubles CLOUDS when load rises.
    """

    CPU_TRIGGER = float(os.environ.get("CG_MULT_CPU", "50"))
    RAM_TRIGGER = float(os.environ.get("CG_MULT_RAM", "60"))
    QUEUE_TRIGGER = int(os.environ.get("CG_MULT_QUEUE", "10"))

    STARTING_CLOUDS = int(os.environ.get("CG_MULT_START", "10"))
    TARGET_CLOUDS = int(os.environ.get("CG_MULT_TARGET", "100"))

    FIXED_AGENTS = int(os.environ.get("CG_TARGET_AGENTS", "1000000"))

    CHECK_INTERVAL = int(os.environ.get("CG_MULT_CHECK", "60"))
    COOLDOWN = int(os.environ.get("CG_MULT_COOLDOWN", "120"))

    def __init__(self):
        self.running = False
        self.current_clouds = 0
        self.generation = 0
        self.last_multiply_at = 0
        self.history: List[Dict] = []
        self._stop = threading.Event()
        self._thread = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------
    def start(self):
        if self.running:
            return
        self.running = True
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info(f"[Multiplier] Started (agents={self.FIXED_AGENTS:,} fixed)")

    def stop(self):
        self.running = False
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _loop(self):
        # Seed initial clouds
        self._seed_initial()
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception as e:
                logger.error(f"[Multiplier] tick error: {e}")
            self._stop.wait(self.CHECK_INTERVAL)

    def _seed_initial(self):
        logger.info(f"[Multiplier] Seeding {self.STARTING_CLOUDS} clouds "
                    f"for {self.FIXED_AGENTS:,} agents")
        self._spread_agents(self.STARTING_CLOUDS)
        self.current_clouds = self.STARTING_CLOUDS

    # ------------------------------------------------------------
    # Load detection
    # ------------------------------------------------------------
    def _read_load(self) -> Dict:
        load = {"cpu": 0.0, "ram": 0.0, "queue": 0}
        try:
            import psutil
            load["cpu"] = psutil.cpu_percent(interval=0.1)
            load["ram"] = psutil.virtual_memory().percent
        except Exception:
            try:
                la = os.getloadavg()[0]
                ncpu = os.cpu_count() or 1
                load["cpu"] = min(100.0, la / ncpu * 100)
            except Exception:
                pass
        try:
            from db import get_task_stats
            load["queue"] = get_task_stats().get("running", 0)
        except Exception:
            pass
        return load

    def _under_pressure(self, load: Dict) -> bool:
        return (
            load["cpu"] >= self.CPU_TRIGGER
            or load["ram"] >= self.RAM_TRIGGER
            or load["queue"] >= self.QUEUE_TRIGGER
        )

    # ------------------------------------------------------------
    # Tick
    # ------------------------------------------------------------
    def _tick(self):
        load = self._read_load()

        if self.current_clouds >= self.TARGET_CLOUDS:
            return

        if time.time() - self.last_multiply_at < self.COOLDOWN:
            return

        if not self._under_pressure(load):
            return

        new_total = min(self.current_clouds * 2, self.TARGET_CLOUDS)
        added = new_total - self.current_clouds

        if added <= 0:
            return

        logger.info(f"[Multiplier] Pressure! Clouds: "
                    f"{self.current_clouds} -> {new_total} (+{added})")

        # Re-spread FIXED agents across MORE clouds
        self._spread_agents(new_total)

        with self._lock:
            self.current_clouds = new_total
            self.generation += 1
            self.last_multiply_at = time.time()
            self.history.append({
                "ts": time.time(),
                "clouds_from": new_total - added,
                "clouds_to": new_total,
                "agents_still": self.FIXED_AGENTS,
                "agents_per_cloud": self.FIXED_AGENTS // new_total,
                "load": load,
                "generation": self.generation,
            })

        try:
            log_event("multiplier", {
                "action": "double_clouds",
                "clouds_to": new_total,
                "agents_fixed": self.FIXED_AGENTS,
                "generation": self.generation,
            })
        except Exception:
            pass

    # ------------------------------------------------------------
    # Spread agents across clouds
    # ------------------------------------------------------------
    def _spread_agents(self, cloud_count: int):
        """Distribute 1M agents across cloud_count clouds."""
        try:
            from platforms_registry import list_no_card
            platforms = list_no_card()
        except Exception:
            platforms = []

        if not platforms:
            logger.warning("[Multiplier] No platforms")
            return

        agents_per_cloud = self.FIXED_AGENTS // cloud_count
        logger.info(f"[Multiplier] Spreading {self.FIXED_AGENTS:,} agents "
                    f"across {cloud_count} clouds "
                    f"({agents_per_cloud:,} agents per cloud)")

        for i in range(min(cloud_count, len(platforms))):
            p = platforms[i % len(platforms)]
            pname = p["name"]
            try:
                from auto_deployer import auto_deployer
                if pname in auto_deployer.PROVIDER_MAX:
                    result = auto_deployer._run_http(pname, agents_per_cloud // 10000)
                    logger.info(f"[Multiplier] {pname}: {result.get('status')}")
            except Exception as e:
                logger.warning(f"[Multiplier] {pname}: {e}")

    # ------------------------------------------------------------
    # Manual
    # ------------------------------------------------------------
    def force_double(self) -> Dict:
        if self.current_clouds >= self.TARGET_CLOUDS:
            return {"status": "at_target", "clouds": self.current_clouds}

        new_total = min(self.current_clouds * 2, self.TARGET_CLOUDS)
        self._spread_agents(new_total)

        with self._lock:
            self.current_clouds = new_total
            self.generation += 1
            self.last_multiply_at = time.time()

        return {
            "status": "doubled",
            "clouds": new_total,
            "agents_still": self.FIXED_AGENTS,
            "agents_per_cloud": self.FIXED_AGENTS // new_total,
        }

    # ------------------------------------------------------------
    # Status
    # ------------------------------------------------------------
    def status(self) -> Dict[str, Any]:
        agents_per_cloud = self.FIXED_AGENTS // max(1, self.current_clouds)
        return {
            "running": self.running,
            "agents_total": self.FIXED_AGENTS,        # ثابت دائماً
            "agents_per_cloud": agents_per_cloud,     # يتغير
            "clouds_current": self.current_clouds,    # يتضاعف
            "clouds_target": self.TARGET_CLOUDS,
            "generation": self.generation,
            "thresholds": {
                "cpu": self.CPU_TRIGGER,
                "ram": self.RAM_TRIGGER,
                "queue": self.QUEUE_TRIGGER,
            },
            "history": self.history[-10:],
        }


# Singleton
cloud_multiplier = CloudMultiplier()
