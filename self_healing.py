"""
CYBERGUARD OS - Self-Healing (Clinic)
Watches agents. If they die, diagnose, fix, or replace.
"""
import time
import logging
import threading
from typing import Dict, List, Optional, Any

from db import log_event, update_agent_status
from config import (
    SELF_HEALING_ENABLED, SELF_HEALING_HEARTBEAT,
    SELF_HEALING_MAX_RESTARTS, SELF_HEALING_QUARANTINE,
)

logger = logging.getLogger(__name__)


class AgentClinic:
    def __init__(self):
        self.heartbeats: Dict[str, float] = {}
        self.restarts: Dict[str, int] = {}
        self.quarantine: List[str] = []
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def heartbeat(self, agent_id: str):
        with self._lock:
            self.heartbeats[agent_id] = time.time()

    def report_failure(self, agent_id: str, reason: str = "unknown") -> Dict:
        logger.warning(f"[Clinic] {agent_id} failed: {reason}")
        try:
            log_event("clinic", {"agent_id": agent_id, "reason": reason,
                                 "action": "reported"})
        except Exception:
            pass

        with self._lock:
            self.restarts[agent_id] = self.restarts.get(agent_id, 0) + 1
            count = self.restarts[agent_id]

        if count > SELF_HEALING_MAX_RESTARTS:
            self.quarantine_agent(agent_id, reason="max_restarts_exceeded")
            return {"status": "quarantined", "agent_id": agent_id,
                    "restarts": count}

        result = self._heal(agent_id, reason)
        return {"status": "healing_attempted", "agent_id": agent_id,
                "restarts": count, "result": result}

    def quarantine_agent(self, agent_id: str, reason: str = ""):
        with self._lock:
            if agent_id not in self.quarantine:
                self.quarantine.append(agent_id)
        try:
            update_agent_status(agent_id, "quarantined")
        except Exception:
            pass
        logger.error(f"[Clinic] {agent_id} QUARANTINED ({reason})")
        try:
            log_event("clinic", {"agent_id": agent_id, "reason": reason,
                                 "action": "quarantined"})
        except Exception:
            pass

    def list_quarantine(self) -> List[str]:
        with self._lock:
            return list(self.quarantine)

    def status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "tracked": len(self.heartbeats),
                "quarantined": len(self.quarantine),
                "restarts": dict(self.restarts),
                "quarantine_list": list(self.quarantine),
            }

    def start_watchdog(self):
        if not SELF_HEALING_ENABLED:
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._watchdog, daemon=True)
        self._thread.start()
        logger.info("[Clinic] Watchdog started")

    def stop_watchdog(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _watchdog(self):
        while not self._stop.is_set():
            try:
                self._scan_dead()
            except Exception as e:
                logger.error(f"[Clinic] scan error: {e}")
            self._stop.wait(SELF_HEALING_HEARTBEAT)

    def _scan_dead(self):
        now = time.time()
        stale_threshold = SELF_HEALING_HEARTBEAT * 3
        with self._lock:
            stale = [aid for aid, ts in self.heartbeats.items()
                     if now - ts > stale_threshold]
        for aid in stale:
            self.report_failure(aid, reason="heartbeat_timeout")

    def _heal(self, agent_id: str, reason: str) -> Dict[str, Any]:
        steps = []
        try:
            update_agent_status(agent_id, "active")
            steps.append("status_reset")
        except Exception as e:
            steps.append(f"status_reset_failed:{e}")

        try:
            from agents.hierarchy import hierarchy
            hierarchy.assign_task(agent_id, "restart", {})
            steps.append("restart_dispatched")
        except Exception as e:
            steps.append(f"restart_failed:{e}")

        try:
            from agents.hierarchy import hierarchy
            if hasattr(hierarchy, "replace_agent"):
                new_id = hierarchy.replace_agent(agent_id)
                steps.append(f"replaced_with:{new_id}")
        except Exception as e:
            steps.append(f"replace_failed:{e}")

        try:
            log_event("clinic", {"agent_id": agent_id, "reason": reason,
                                 "action": "healed", "steps": steps})
        except Exception:
            pass
        return {"agent_id": agent_id, "steps": steps}


clinic = AgentClinic()
