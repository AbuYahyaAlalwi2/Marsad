"""
CYBERGUARD OS - Auto Scaler
Grows the agent hierarchy automatically:
  1 -> 10 -> 100 -> 1,000 -> 10,000 -> 100,000 -> 1,000,000
Based on: queue load, CPU, RAM, idle agents.
"""
import os
import time
import logging
import threading
from typing import Dict, Any, Optional, List

from db import log_event, count_agents_by_level, insert_agent

logger = logging.getLogger(__name__)


class AutoScaler:
    """
    Watches system load and scales the agent hierarchy in stages.
    Never exceeds MAX_AGENTS (1,000,000).
    """

    STAGES = [1, 10, 100, 1000, 10000, 100000, 1000000]

    def __init__(self):
        self.stage = 0
        self.current = 0
        self.max_agents = int(os.environ.get("CG_MAX_AGENTS", "1000000"))
        self.running = False
        self.cooldown = int(os.environ.get("CG_SCALE_COOLDOWN", "60"))
        self.check_interval = int(os.environ.get("CG_SCALE_CHECK", "30"))
        self.last_scale_at = 0
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self.history: List[Dict] = []

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
        logger.info(f"[Scaler] Started (max={self.max_agents})")
        try:
            log_event("scaler", {"action": "start", "max": self.max_agents})
        except Exception:
            pass

    def stop(self):
        self.running = False
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("[Scaler] Stopped")

    # ------------------------------------------------------------
    # Loop
    # ------------------------------------------------------------
    def _loop(self):
        # Bootstrap: if DB is empty, seed initial agents
        self._bootstrap()
        
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception as e:
                logger.error(f"[Scaler] tick error: {e}")
            self._stop.wait(self.check_interval)

    def _bootstrap(self):
        """If DB has no agents, seed initial hierarchy."""
        try:
            existing = self._count_agents()
            if existing > 100:
                logger.info(f"[Scaler] Bootstrap skipped (DB has {existing} agents)")
                return
            
            bootstrap_stage = int(os.environ.get("CG_BOOTSTRAP_STAGE", "3"))
            target = self.STAGES[bootstrap_stage]
            logger.info(f"[Scaler] Bootstrap: growing to {target} agents")
            
            self._record_agents(0, target)
            self.stage = bootstrap_stage
            self.current = target
            
            try:
                log_event("scaler", {
                    "action": "bootstrap",
                    "stage": bootstrap_stage,
                    "target": target,
                })
            except Exception:
                pass
        except Exception as e:
            logger.error(f"[Scaler] bootstrap failed: {e}")

    def _tick(self):
        metrics = self._read_metrics()
        decision = self._decide(metrics)
        if decision["action"] != "noop":
            self._execute(decision)

    # ------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------
    def _read_metrics(self) -> Dict[str, Any]:
        m = {
            "cpu": 0.0,
            "ram": 0.0,
            "queue_size": 0,
            "agents_current": self._count_agents(),
            "time": time.time(),
        }
        try:
            import psutil
            m["ram"] = psutil.virtual_memory().percent
            la = os.getloadavg()[0]
            ncpu = os.cpu_count() or 1
            m["cpu"] = min(100.0, (la / ncpu) * 100.0)
        except Exception:
            pass

        try:
            from db import get_task_stats
            stats = get_task_stats()
            m["queue_size"] = stats.get("running", 0) + stats.get("total", 0) // 10
        except Exception:
            pass

        return m

    def _count_agents(self) -> int:
        try:
            total = 0
            for i in range(5):
                total += count_agents_by_level(i)
            return total
        except Exception:
            return 0

    # ------------------------------------------------------------
    # Decision
    # ------------------------------------------------------------
    def _decide(self, m: Dict) -> Dict:
        now = time.time()
        if now - self.last_scale_at < self.cooldown:
            return {"action": "noop", "reason": "cooldown", "metrics": m}

        if self.current >= self.max_agents:
            return {"action": "noop", "reason": "max_reached", "metrics": m}

        high_cpu = m["cpu"] > 60
        high_ram = m["ram"] > 70
        high_queue = m["queue_size"] > 5

        # scale up if busy
        if high_cpu or high_ram or high_queue:
            return {"action": "scale_up", "metrics": m}

        return {"action": "noop", "reason": "load_low", "metrics": m}

    # ------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------
    def _execute(self, decision: Dict):
        action = decision["action"]
        if action == "scale_up":
            self._scale_up()
        self.last_scale_at = time.time()

    def _scale_up(self):
        with self._lock:
            if self.stage >= len(self.STAGES) - 1:
                return
            self.stage += 1
            target = min(self.STAGES[self.stage], self.max_agents)

        added = target - self.current
        if added <= 0:
            return

        logger.info(f"[Scaler] Scale UP: {self.current} -> {target} (+{added})")

        # Record agents in DB (fast, batched)
        self._record_agents(self.current, target)

        self.current = target
        self.history.append({
            "at": time.time(),
            "from": self.current - added,
            "to": target,
            "reason": "load",
        })

        try:
            log_event("scaler", {
                "action": "scale_up",
                "from": self.current - added,
                "to": target,
                "stage": self.stage,
            })
        except Exception:
            pass

    def _record_agents(self, start: int, end: int):
        """Insert new agents into DB in batches."""
        batch_size = 500
        total = end - start

        # For very large counts, only record the hierarchy levels (not every agent)
        if total > 10000:
            logger.info(f"[Scaler] Large scale ({total}) - recording hierarchy levels only")
            # Just record representative agents at each level
            levels = [
                (0, 1, "root"),
                (1, min(100, end), "root"),
                (2, min(1000, end), "agent_1_0"),
                (3, min(10000, end), "agent_2_0"),
                (4, end, "agent_3_0"),
            ]
            for level, count, parent in levels:
                existing = count_agents_by_level(level)
                need = max(0, count - existing)
                # Cap DB inserts for level 4 (avoid millions of rows)
                if level == 4 and need > 5000:
                    need = 5000
                    logger.info(f"[Scaler] Level 4 capped at 5,000 DB rows (representative)")
                for i in range(need):
                    try:
                        insert_agent(
                            agent_id=f"agent_{level}_{existing + i}_{int(time.time())}",
                            level=level,
                            parent_id=parent,
                            cloud_provider="local",
                        )
                    except Exception:
                        pass
        else:
            # Small scale: record every agent
            for i in range(start, end):
                level = 4 if i >= 10000 else (3 if i >= 1000 else (2 if i >= 100 else (1 if i >= 1 else 0)))
                parent = f"agent_{level-1}_0" if level > 0 else None
                try:
                    insert_agent(
                        agent_id=f"agent_{level}_{i}_{int(time.time())}",
                        level=level,
                        parent_id=parent,
                        cloud_provider="local",
                    )
                except Exception:
                    pass

    # ------------------------------------------------------------
    # Manual controls
    # ------------------------------------------------------------
    def force_stage(self, stage: int) -> Dict:
        """Manually jump to a stage (for testing)."""
        if stage < 0 or stage >= len(self.STAGES):
            return {"status": "error", "reason": "invalid_stage"}
        with self._lock:
            self.stage = stage
            target = min(self.STAGES[stage], self.max_agents)
        added = target - self.current
        self._record_agents(self.current, target)
        self.current = target
        self.last_scale_at = time.time()
        return {"status": "ok", "stage": stage, "target": target, "added": added}

    def status(self) -> Dict[str, Any]:
        return {
            "running": self.running,
            "stage": self.stage,
            "current": self.current,
            "max_agents": self.max_agents,
            "stages": self.STAGES,
            "next_target": self.STAGES[self.stage + 1] if self.stage + 1 < len(self.STAGES) else self.max_agents,
            "cooldown": self.cooldown,
            "history": self.history[-10:],
        }


# Singleton
auto_scaler = AutoScaler()
