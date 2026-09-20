"""
CYBERGUARD OS - Worker Node
Deployable to ANY cloud (Fly.io, Railway, Render, Cloudflare).
Registers with Control Plane, runs a share of the million agents.
"""
import os
import sys
import time
import json
import uuid
import logging
import threading
import requests
from pathlib import Path
from typing import Dict, Any, Optional

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
os.chdir(BASE)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("worker")


class WorkerNode:
    """
    A single worker. Deployed across many clouds.
    Each worker:
      - registers with Control Plane
      - receives agent count allocation
      - sends heartbeats
      - runs its share of agents (lightweight)
    """

    def __init__(self):
        self.node_id = os.environ.get(
            "CG_NODE_ID",
            f"worker-{uuid.uuid4().hex[:8]}"
        )
        self.provider = os.environ.get("CG_CLOUD_PROVIDER", "unknown")
        self.region = os.environ.get("CG_REGION", "auto")
        self.endpoint = os.environ.get("CG_ENDPOINT", "")
        self.capacity = int(os.environ.get("CG_WORKER_CAPACITY", "10000"))
        self.control_url = os.environ.get(
            "CG_CONTROL_PLANE_URL",
            "https://marsad-dashboard.onrender.com"
        ).rstrip("/")

        self.running = False
        self.active_agents = 0
        self._stop = threading.Event()
        self._hb_thread: Optional[threading.Thread] = None
        self._agent_thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------
    def start(self):
        logger.info(f"[Worker] Starting {self.node_id} ({self.provider}/{self.region})")
        logger.info(f"[Worker] Capacity: {self.capacity:,} agents")
        logger.info(f"[Worker] Control: {self.control_url}")

        self.running = True
        self._register()

        # Heartbeat thread
        self._hb_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._hb_thread.start()

        # Agent simulation thread (lightweight: just tracks numbers)
        self._agent_thread = threading.Thread(target=self._agent_loop, daemon=True)
        self._agent_thread.start()

        # Block forever
        while self.running and not self._stop.is_set():
            time.sleep(1)

    def stop(self):
        self.running = False
        self._stop.set()

    # ------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------
    def _register(self):
        """Register with Control Plane."""
        try:
            r = requests.post(
                f"{self.control_url}/api/worker/register",
                json={
                    "node_id": self.node_id,
                    "provider": self.provider,
                    "region": self.region,
                    "endpoint": self.endpoint,
                    "capacity": self.capacity,
                },
                timeout=10,
            )
            if r.status_code == 200:
                logger.info(f"[Worker] Registered with Control Plane")
            else:
                logger.warning(f"[Worker] Register got {r.status_code}")
        except Exception as e:
            logger.warning(f"[Worker] Could not register: {e}")
            logger.info("[Worker] Will retry via heartbeat")

    # ------------------------------------------------------------
    # Heartbeat
    # ------------------------------------------------------------
    def _heartbeat_loop(self):
        while not self._stop.is_set():
            try:
                self._send_heartbeat()
            except Exception as e:
                logger.warning(f"[Worker] heartbeat failed: {e}")
            self._stop.wait(30)

    def _send_heartbeat(self):
        cpu, ram = self._read_metrics()
        try:
            r = requests.post(
                f"{self.control_url}/api/worker/heartbeat",
                json={
                    "node_id": self.node_id,
                    "cpu": cpu,
                    "ram": ram,
                    "active_agents": self.active_agents,
                    "queue_size": 0,
                },
                timeout=10,
            )
            if r.status_code == 200:
                logger.debug(f"[Worker] HB sent ({self.active_agents} agents)")
        except Exception as e:
            logger.warning(f"[Worker] HB error: {e}")

    def _read_metrics(self):
        try:
            import psutil
            return round(psutil.cpu_percent(interval=0.1), 1), round(psutil.virtual_memory().percent, 1)
        except Exception:
            try:
                la = os.getloadavg()[0]
                ncpu = os.cpu_count() or 1
                return round(min(100.0, la / ncpu * 100), 1), 0.0
            except Exception:
                return 0.0, 0.0

    # ------------------------------------------------------------
    # Agents (lightweight logical agents)
    # ------------------------------------------------------------
    def _agent_loop(self):
        """Simulate running N agents (logical, not processes)."""
        while not self._stop.is_set():
            # Grow towards capacity
            if self.active_agents < self.capacity:
                step = max(100, self.capacity // 100)
                self.active_agents = min(self.capacity, self.active_agents + step)
                logger.info(f"[Worker] Active agents: {self.active_agents:,}")
            self._stop.wait(10)


def main():
    w = WorkerNode()

    def shutdown(sig, frame):
        w.stop()

    import signal
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    w.start()


if __name__ == "__main__":
    main()
