"""
CYBERGUARD OS - Distributed Manager
Orchestrates workers across 245 cloud providers.
Render = Control Plane. Other clouds = Worker Nodes.
"""
import os
import time
import uuid
import logging
import threading
import requests
from typing import Dict, List, Any, Optional

from db import get_conn, log_event

logger = logging.getLogger(__name__)


SCHEMA = """
CREATE TABLE IF NOT EXISTS worker_nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id TEXT UNIQUE NOT NULL,
    provider TEXT,
    region TEXT,
    endpoint TEXT,
    capacity INTEGER DEFAULT 10000,
    active_agents INTEGER DEFAULT 0,
    status TEXT DEFAULT 'registering',
    cpu REAL DEFAULT 0,
    ram REAL DEFAULT 0,
    queue_size INTEGER DEFAULT 0,
    last_heartbeat REAL,
    registered_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_worker_status ON worker_nodes(status);
CREATE INDEX IF NOT EXISTS idx_worker_hb ON worker_nodes(last_heartbeat);

CREATE TABLE IF NOT EXISTS distributed_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT UNIQUE NOT NULL,
    task_type TEXT,
    payload TEXT,
    assigned_to TEXT,
    status TEXT DEFAULT 'pending',
    result TEXT,
    created_at REAL NOT NULL,
    assigned_at REAL,
    completed_at REAL
);
CREATE INDEX IF NOT EXISTS idx_dist_task_status ON distributed_tasks(status);
"""


class DistributedManager:
    """
    Manages worker nodes across all cloud providers.
    """

    HEARTBEAT_TIMEOUT = 120  # seconds
    MAX_WORKERS = int(os.environ.get("CG_MAX_WORKERS", "1000"))

    def __init__(self):
        self.control_plane_url = os.environ.get(
            "CG_CONTROL_PLANE_URL",
            "https://marsad-dashboard.onrender.com"
        )
        self.running = False
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._ensure_schema()

    def _ensure_schema(self):
        try:
            with get_conn() as conn:
                conn.executescript(SCHEMA)
                conn.commit()
            logger.info("[Distributed] Schema ready")
        except Exception as e:
            logger.error(f"[Distributed] schema failed: {e}")

    # ------------------------------------------------------------
    # Worker registration
    # ------------------------------------------------------------
    def register_worker(self, node_id: str, provider: str = "unknown",
                       region: str = "auto", endpoint: str = "",
                       capacity: int = 10000) -> Dict[str, Any]:
        try:
            with get_conn() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO worker_nodes "
                    "(node_id, provider, region, endpoint, capacity, status, "
                    "last_heartbeat, registered_at) "
                    "VALUES (?, ?, ?, ?, ?, 'online', ?, ?)",
                    (node_id, provider, region, endpoint, capacity,
                     time.time(), time.time())
                )
                conn.commit()

            log_event("distributed", {
                "action": "register_worker",
                "node_id": node_id,
                "provider": provider,
            })
            logger.info(f"[Distributed] Worker registered: {node_id} ({provider})")
            return {"status": "registered", "node_id": node_id}
        except Exception as e:
            logger.error(f"[Distributed] register failed: {e}")
            return {"status": "error", "error": str(e)}

    def heartbeat(self, node_id: str, cpu: float = 0, ram: float = 0,
                 active_agents: int = 0, queue_size: int = 0) -> Dict[str, Any]:
        try:
            with get_conn() as conn:
                conn.execute(
                    "UPDATE worker_nodes SET last_heartbeat = ?, cpu = ?, ram = ?, "
                    "active_agents = ?, queue_size = ?, status = 'online' "
                    "WHERE node_id = ?",
                    (time.time(), cpu, ram, active_agents, queue_size, node_id)
                )
                conn.commit()
            return {"status": "ok"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ------------------------------------------------------------
    # Worker listing
    # ------------------------------------------------------------
    def list_workers(self, only_alive: bool = True) -> List[Dict]:
        try:
            with get_conn() as conn:
                if only_alive:
                    cutoff = time.time() - self.HEARTBEAT_TIMEOUT
                    rows = conn.execute(
                        "SELECT * FROM worker_nodes WHERE last_heartbeat > ? "
                        "ORDER BY last_heartbeat DESC",
                        (cutoff,)
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT * FROM worker_nodes ORDER BY last_heartbeat DESC"
                    ).fetchall()
                return [dict(r) for r in rows]
        except Exception:
            return []

    def count_online(self) -> int:
        try:
            cutoff = time.time() - self.HEARTBEAT_TIMEOUT
            with get_conn() as conn:
                row = conn.execute(
                    "SELECT COUNT(*) as c FROM worker_nodes WHERE last_heartbeat > ?",
                    (cutoff,)
                ).fetchone()
                return row["c"] if row else 0
        except Exception:
            return 0

    def total_capacity(self) -> int:
        try:
            cutoff = time.time() - self.HEARTBEAT_TIMEOUT
            with get_conn() as conn:
                row = conn.execute(
                    "SELECT SUM(capacity) as c FROM worker_nodes "
                    "WHERE last_heartbeat > ?",
                    (cutoff,)
                ).fetchone()
                return row["c"] or 0 if row else 0
        except Exception:
            return 0

    def total_active_agents(self) -> int:
        try:
            cutoff = time.time() - self.HEARTBEAT_TIMEOUT
            with get_conn() as conn:
                row = conn.execute(
                    "SELECT SUM(active_agents) as c FROM worker_nodes "
                    "WHERE last_heartbeat > ?",
                    (cutoff,)
                ).fetchone()
                return row["c"] or 0 if row else 0
        except Exception:
            return 0

    # ------------------------------------------------------------
    # Task dispatch
    # ------------------------------------------------------------
    def dispatch_task(self, task_type: str, payload: Dict) -> Dict[str, Any]:
        """Assign task to a worker with lowest load."""
        workers = self.list_workers()
        if not workers:
            return {"status": "no_workers"}

        # Pick worker with lowest load
        best = min(workers, key=lambda w: (w.get("queue_size", 0), w.get("cpu", 0)))
        node_id = best["node_id"]

        task_id = f"dist_{uuid.uuid4().hex[:12]}"
        try:
            import json
            with get_conn() as conn:
                conn.execute(
                    "INSERT INTO distributed_tasks "
                    "(task_id, task_type, payload, assigned_to, status, "
                    "created_at, assigned_at) "
                    "VALUES (?, ?, ?, ?, 'assigned', ?, ?)",
                    (task_id, task_type, json.dumps(payload), node_id,
                     time.time(), time.time())
                )
                conn.commit()

            log_event("distributed", {
                "action": "dispatch",
                "task_id": task_id,
                "node_id": node_id,
                "task_type": task_type,
            })
            return {
                "status": "dispatched",
                "task_id": task_id,
                "node_id": node_id,
                "endpoint": best.get("endpoint"),
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ------------------------------------------------------------
    # Watchdog: mark dead workers
    # ------------------------------------------------------------
    def start_watchdog(self):
        if self.running:
            return
        self.running = True
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info("[Distributed] Watchdog started")

    def stop_watchdog(self):
        self.running = False
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _loop(self):
        while not self._stop.is_set():
            try:
                self._mark_dead()
            except Exception as e:
                logger.error(f"[Distributed] watchdog error: {e}")
            self._stop.wait(60)

    def _mark_dead(self):
        cutoff = time.time() - self.HEARTBEAT_TIMEOUT
        try:
            with get_conn() as conn:
                conn.execute(
                    "UPDATE worker_nodes SET status = 'dead' "
                    "WHERE last_heartbeat < ? AND status != 'dead'",
                    (cutoff,)
                )
                conn.commit()
        except Exception:
            pass

    # ------------------------------------------------------------
    # Status
    # ------------------------------------------------------------
    def status(self) -> Dict[str, Any]:
        return {
            "online_workers": self.count_online(),
            "total_capacity": self.total_capacity(),
            "active_agents": self.total_active_agents(),
            "max_workers": self.MAX_WORKERS,
            "control_plane": self.control_plane_url,
        }


# Singleton
distributed_manager = DistributedManager()
