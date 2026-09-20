"""
CYBERGUARD OS - Worker Pool
Spawns and manages agent workers. Auto-restarts dead ones.
"""
import time
import logging
import threading
from typing import Dict, List, Optional

from db import (log_event, insert_agent, count_agents_by_level,
                create_task, complete_task)
from config import MAX_AGENTS, TASK_QUEUE_WORKERS
from queue_manager import get_backend

logger = logging.getLogger(__name__)


class WorkerPool:
    def __init__(self):
        self._workers: List[Dict] = []
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self, worker_count: int = None):
        worker_count = worker_count or TASK_QUEUE_WORKERS
        logger.info(f"[Pool] Starting {worker_count} workers")

        for i in range(worker_count):
            self._spawn_worker(worker_id=f"worker-{i:03d}")

        self._stop.clear()
        self._thread = threading.Thread(target=self._supervisor, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("[Pool] Stopped")

    def _supervisor(self):
        while not self._stop.is_set():
            self._stop.wait(60)
            with self._lock:
                for w in self._workers:
                    if not w["alive"]:
                        logger.warning(f"[Pool] Worker {w['id']} dead - restarting")
                        self._spawn_worker(w["id"])

    def _spawn_worker(self, worker_id: str):
        w = {
            "id": worker_id,
            "started_at": time.time(),
            "alive": True,
            "agents": [],
        }

        task_id = f"spawn_{worker_id}_{int(time.time() * 1000)}"
        create_task(task_id, f"بدء عامل {worker_id}", "worker_spawn", worker_id)

        try:
            insert_agent(
                agent_id=worker_id,
                level=2,
                parent_id="root",
                cloud_provider="local",
            )
            complete_task(task_id, result=f"Worker {worker_id} spawned")
        except Exception as e:
            complete_task(task_id, error=str(e))

        with self._lock:
            self._workers = [x for x in self._workers if x["id"] != worker_id]
            self._workers.append(w)

        try:
            log_event("worker_pool", {"action": "spawn", "worker_id": worker_id})
        except Exception:
            pass

    def deploy_agents(self, count: int) -> Dict:
        deploy_task = f"deploy_{int(time.time() * 1000)}"
        create_task(deploy_task, f"نشر {count} وكيل", "deploy_agents")

        with self._lock:
            if len(self._workers) == 0:
                self._spawn_worker("worker-000")

        deployed = 0
        per_worker = max(1, count // max(1, len(self._workers)))

        for w in self._workers:
            for i in range(per_worker):
                aid = f"{w['id']}-agent-{i:05d}"
                try:
                    insert_agent(
                        agent_id=aid,
                        level=3,
                        parent_id=w["id"],
                        cloud_provider="local",
                    )
                    w["agents"].append(aid)
                    deployed += 1
                except Exception:
                    pass

        try:
            log_event("worker_pool", {"action": "deploy", "count": deployed})
        except Exception:
            pass

        complete_task(deploy_task, result=f"Deployed {deployed} agents")
        return {"status": "ok", "deployed": deployed, "workers": len(self._workers)}

    def status(self) -> Dict:
        with self._lock:
            total_agents = sum(len(w["agents"]) for w in self._workers)
            return {
                "workers": len(self._workers),
                "alive_workers": sum(1 for w in self._workers if w["alive"]),
                "total_agents_in_pool": total_agents,
                "queue_backend": get_backend(),
                "max_agents": MAX_AGENTS,
                "db_agents_level_3": count_agents_by_level(3),
            }


worker_pool = WorkerPool()
