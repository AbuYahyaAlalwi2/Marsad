"""
CYBERGUARD OS - Auto Deployer
Scales worker nodes across clouds automatically based on load.
Controls: Fly.io, Railway, Render, Koyeb.
"""
import os
import time
import json
import logging
import subprocess
import threading
from typing import Dict, Any, List, Optional

from db import get_conn, log_event

logger = logging.getLogger(__name__)


SCHEMA = """
CREATE TABLE IF NOT EXISTS deployments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    workers INTEGER NOT NULL,
    agents INTEGER NOT NULL,
    status TEXT DEFAULT 'pending',
    command TEXT,
    output TEXT,
    reason TEXT,
    created_at REAL NOT NULL,
    completed_at REAL
);
CREATE INDEX IF NOT EXISTS idx_deploy_provider ON deployments(provider);
"""


class AutoDeployer:
    """
    Automatically scales workers based on system load.
    Monitors: queue size, CPU, RAM, agent count.
    Scales: Fly.io, Railway, Render, Koyeb.
    """

    # Scaling thresholds
    SCALE_UP_QUEUE = int(os.environ.get("CG_SCALE_UP_QUEUE", "50"))
    SCALE_UP_CPU = float(os.environ.get("CG_SCALE_UP_CPU", "70.0"))
    SCALE_UP_RAM = float(os.environ.get("CG_SCALE_UP_RAM", "80.0"))
    SCALE_DOWN_QUEUE = int(os.environ.get("CG_SCALE_DOWN_QUEUE", "5"))

    # Cloud limits (per provider, free tier)
    PROVIDER_MAX = {
        "fly": 100,
        "railway": 50,
        "render": 10,
        "koyeb": 50,
    }

    WORKERS_PER_BATCH = int(os.environ.get("CG_SCALE_BATCH", "5"))
    CHECK_INTERVAL = int(os.environ.get("CG_AUTODEPLOY_INTERVAL", "120"))

    def __init__(self):
        self.running = False
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Tokens
        self.fly_token = os.environ.get("FLY_API_TOKEN", "")
        self.railway_token = os.environ.get("RAILWAY_TOKEN", "")
        self.render_token = os.environ.get("RENDER_API_KEY", "")
        self.koyeb_token = os.environ.get("KOYEB_TOKEN", "")

        # App names
        self.fly_app = os.environ.get("FLY_APP_NAME", "marsad-worker")
        self.railway_service = os.environ.get("RAILWAY_SERVICE", "marsad-worker")
        self.koyeb_app = os.environ.get("KOYEB_APP", "marsad-worker")

        # Dry-run mode (safety default)
        self.dry_run = os.environ.get("CG_DEPLOY_DRY_RUN", "true").lower() == "true"

        # Current state
        self.current_workers: Dict[str, int] = {
            "fly": 0, "railway": 0, "render": 0, "koyeb": 0
        }

        self._ensure_schema()
        logger.info(f"[Deployer] Init (dry_run={self.dry_run}, batch={self.WORKERS_PER_BATCH})")

    def _ensure_schema(self):
        try:
            with get_conn() as conn:
                conn.executescript(SCHEMA)
                conn.commit()
        except Exception as e:
            logger.error(f"[Deployer] schema: {e}")

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
        logger.info("[Deployer] Started")

    def stop(self):
        self.running = False
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _loop(self):
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception as e:
                logger.error(f"[Deployer] tick: {e}")
            self._stop.wait(self.CHECK_INTERVAL)

    # ------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------
    def _read_load(self) -> Dict[str, float]:
        load = {"queue": 0, "cpu": 0.0, "ram": 0.0, "agents": 0, "workers_online": 0}

        # Queue size
        try:
            from db import get_task_stats
            stats = get_task_stats()
            load["queue"] = stats.get("running", 0)
        except Exception:
            pass

        # CPU/RAM
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

        # Workers online
        try:
            from distributed_manager import distributed_manager
            load["workers_online"] = distributed_manager.count_online()
        except Exception:
            pass

        return load

    # ------------------------------------------------------------
    # Decision
    # ------------------------------------------------------------
    def _decide(self, load: Dict) -> Dict:
        queue = load["queue"]
        cpu = load["cpu"]
        ram = load["ram"]

        # Scale up needed?
        if queue >= self.SCALE_UP_QUEUE or cpu >= self.SCALE_UP_CPU or ram >= self.SCALE_UP_RAM:
            provider = self._pick_provider()
            if provider:
                return {
                    "action": "scale_up",
                    "provider": provider,
                    "workers": self.WORKERS_PER_BATCH,
                    "reason": f"queue={queue}, cpu={cpu:.0f}%, ram={ram:.0f}%",
                }
            return {"action": "noop", "reason": "no_provider_available"}

        # Scale down possible?
        if queue <= self.SCALE_DOWN_QUEUE and cpu < 30 and ram < 50:
            for provider, count in self.current_workers.items():
                if count >= self.WORKERS_PER_BATCH:
                    return {
                        "action": "scale_down",
                        "provider": provider,
                        "workers": self.WORKERS_PER_BATCH,
                        "reason": f"low load (queue={queue})",
                    }

        return {"action": "noop", "reason": "balanced"}

    def _pick_provider(self) -> Optional[str]:
        """Pick provider with room to grow."""
        for provider, max_w in self.PROVIDER_MAX.items():
            current = self.current_workers.get(provider, 0)
            if current + self.WORKERS_PER_BATCH <= max_w:
                # Prefer ones we have tokens for
                if provider == "fly" and self.fly_token:
                    return provider
                if provider == "railway" and self.railway_token:
                    return provider
                if provider == "koyeb" and self.koyeb_token:
                    return provider
                if provider == "render" and self.render_token:
                    return provider
        return None

    # ------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------
    def _tick(self):
        load = self._read_load()
        decision = self._decide(load)

        if decision["action"] == "noop":
            return

        if decision["action"] == "scale_up":
            self._do_scale_up(decision["provider"], decision["workers"], decision["reason"])
        elif decision["action"] == "scale_down":
            self._do_scale_down(decision["provider"], decision["workers"], decision["reason"])

    def _do_scale_up(self, provider: str, count: int, reason: str):
        new_total = self.current_workers.get(provider, 0) + count
        cmd = self._build_command(provider, new_total)

        result = self._run(cmd)

        with self._lock:
            if result["ok"]:
                self.current_workers[provider] = new_total

        self._save_deployment(provider, new_total, count, cmd, result, reason)
        logger.info(f"[Deployer] Scale UP {provider} -> {new_total} workers ({result['status']})")

    def _do_scale_down(self, provider: str, count: int, reason: str):
        new_total = max(0, self.current_workers.get(provider, 0) - count)
        cmd = self._build_command(provider, new_total)

        result = self._run(cmd)

        with self._lock:
            if result["ok"]:
                self.current_workers[provider] = new_total

        self._save_deployment(provider, new_total, -count, cmd, result, reason)
        logger.info(f"[Deployer] Scale DOWN {provider} -> {new_total} workers")

    def _build_command(self, provider: str, count: int) -> str:
        if provider == "fly":
            return f"flyctl scale count {count} --app {self.fly_app} --yes"
        if provider == "railway":
            return f"railway scale --service {self.railway_service} --count {count}"
        if provider == "koyeb":
            return f"koyeb app update {self.koyeb_app} --replicas {count}"
        if provider == "render":
            return f"render services scale {self.railway_service} --count {count}"
        return ""

    def _run(self, cmd: str) -> Dict:
        if not cmd:
            return {"ok": False, "status": "invalid_command", "output": ""}

        if self.dry_run:
            return {
                "ok": True,
                "status": "dry_run",
                "output": f"[DRY RUN] Would execute: {cmd}",
            }

        try:
            r = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=180
            )
            return {
                "ok": r.returncode == 0,
                "status": "success" if r.returncode == 0 else "failed",
                "output": (r.stdout + r.stderr)[-1000:],
            }
        except Exception as e:
            return {"ok": False, "status": "error", "output": str(e)}

    def _save_deployment(self, provider: str, total: int, delta: int,
                        cmd: str, result: Dict, reason: str):
        try:
            with get_conn() as conn:
                conn.execute(
                    "INSERT INTO deployments "
                    "(provider, workers, agents, status, command, output, "
                    "reason, created_at, completed_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (provider, total, total * 10000, result["status"],
                     cmd, result.get("output", ""), reason,
                     time.time(), time.time())
                )
                conn.commit()
            log_event("deployer", {
                "action": "scale",
                "provider": provider,
                "total": total,
                "delta": delta,
                "status": result["status"],
                "reason": reason,
            })
        except Exception as e:
            logger.error(f"[Deployer] save failed: {e}")

    # ------------------------------------------------------------
    # Manual controls
    # ------------------------------------------------------------
    def force_scale(self, provider: str, count: int) -> Dict:
        if provider not in self.PROVIDER_MAX:
            return {"status": "error", "reason": "unknown_provider"}

        cmd = self._build_command(provider, count)
        result = self._run(cmd)

        with self._lock:
            if result["ok"]:
                self.current_workers[provider] = count

        self._save_deployment(provider, count, 0, cmd, result, "manual")
        return {"status": result["status"], "provider": provider,
                "workers": count, "output": result.get("output", "")[:500]}

    def set_dry_run(self, enabled: bool):
        self.dry_run = bool(enabled)
        return {"dry_run": self.dry_run}

    # ------------------------------------------------------------
    # Status
    # ------------------------------------------------------------
    def status(self) -> Dict[str, Any]:
        load = self._read_load()
        total_workers = sum(self.current_workers.values())
        return {
            "running": self.running,
            "dry_run": self.dry_run,
            "current_workers": dict(self.current_workers),
            "total_workers": total_workers,
            "total_capacity_agents": total_workers * 10000,
            "providers_max": dict(self.PROVIDER_MAX),
            "tokens_present": {
                "fly": bool(self.fly_token),
                "railway": bool(self.railway_token),
                "render": bool(self.render_token),
                "koyeb": bool(self.koyeb_token),
            },
            "load": load,
            "thresholds": {
                "scale_up_queue": self.SCALE_UP_QUEUE,
                "scale_up_cpu": self.SCALE_UP_CPU,
                "scale_up_ram": self.SCALE_UP_RAM,
            },
        }

    def history(self, limit: int = 20) -> List[Dict]:
        try:
            with get_conn() as conn:
                rows = conn.execute(
                    "SELECT * FROM deployments ORDER BY created_at DESC LIMIT ?",
                    (limit,)
                ).fetchall()
                return [dict(r) for r in rows]
        except Exception:
            return []


# Singleton
auto_deployer = AutoDeployer()
