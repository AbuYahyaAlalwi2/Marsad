"""
CYBERGUARD OS - Mission Controller
Dynamic mission system:
  - Phases: SEED -> PROVISION -> REGISTER -> UNIFY -> SCALE -> OPERATE
  - Missions: collect_code, collect_news, train_model, merge_models, signup_providers, any custom
  - Change mission at runtime: agents immediately redirect to new task
"""
import os
import time
import json
import logging
import threading
from typing import Dict, Any, List, Optional

from db import get_conn, log_event

logger = logging.getLogger(__name__)


SCHEMA = """
CREATE TABLE IF NOT EXISTS missions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_key TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    config TEXT,
    status TEXT DEFAULT 'pending',
    priority INTEGER DEFAULT 5,
    progress REAL DEFAULT 0.0,
    items_done INTEGER DEFAULT 0,
    items_failed INTEGER DEFAULT 0,
    started_at REAL,
    completed_at REAL,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_mission_status ON missions(status);

CREATE TABLE IF NOT EXISTS system_phase (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phase TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    details TEXT,
    started_at REAL,
    completed_at REAL
);
"""


# ============================================================
# Mission templates (built-in)
# ============================================================
BUILTIN_MISSIONS = {
    "collect_code": {
        "name": "جمع الأكواد البرمجية",
        "description": "جمع أكواد من GitHub, GitLab, Sourcegraph وغيرها",
        "config": {
            "platforms": ["github", "gitlab", "bitbucket", "sourcegraph"],
            "query": "python security vulnerability",
            "limit": 100,
            "target_count": 100000,
            "type": "code",
        },
    },
    "collect_news": {
        "name": "جمع الأخبار",
        "description": "جمع أخبار من RSS، مواقع، منتديات",
        "config": {
            "platforms": ["reddit", "hackernews", "medium", "rss"],
            "query": "cybersecurity",
            "limit": 50,
            "target_count": 50000,
            "type": "news",
        },
    },
    "collect_security": {
        "name": "جمع الثغرات",
        "description": "جمع ثغرات من NVD، ExploitDB، CISA، دارك ويب",
        "config": {
            "platforms": ["nvd", "exploitdb", "cisa", "packetstorm", "vulners"],
            "query": "CVE-2024",
            "limit": 200,
            "target_count": 200000,
            "type": "vulnerability",
        },
    },
    "train_model": {
        "name": "تدريب النموذج",
        "description": "تدريب النموذج على البيانات المجمعة",
        "config": {
            "type": "training",
            "epochs": 5,
            "batch_size": 32,
        },
    },
    "merge_models": {
        "name": "صهر النماذج",
        "description": "دمج نماذج البرمجة",
        "config": {
            "type": "merge",
            "strategy": "ties",
        },
    },
    "signup_providers": {
        "name": "التسجيل في المزودين",
        "description": "التسجيل في مزودي API والسحابات",
        "config": {
            "type": "signup",
            "target_count": 200,
        },
    },
}


class MissionController:
    """
    Manages dynamic missions and system phases.
    """
    
    def __init__(self):
        self.current_mission: Optional[str] = None
        self.current_config: Dict = {}
        self.mission_running = False
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._ensure_schema()
        self._register_builtin_missions()

    def _ensure_schema(self):
        try:
            with get_conn() as conn:
                conn.executescript(SCHEMA)
                conn.commit()
        except Exception as e:
            logger.error(f"[Mission] schema: {e}")

    def _register_builtin_missions(self):
        """Register all built-in missions if not already there."""
        for key, m in BUILTIN_MISSIONS.items():
            try:
                with get_conn() as conn:
                    existing = conn.execute(
                        "SELECT id FROM missions WHERE mission_key = ?", (key,)
                    ).fetchone()
                    if not existing:
                        conn.execute(
                            "INSERT INTO missions (mission_key, name, description, "
                            "config, status, created_at) VALUES (?, ?, ?, ?, 'pending', ?)",
                            (key, m["name"], m["description"],
                             json.dumps(m["config"]), time.time())
                        )
                    conn.commit()
            except Exception as e:
                logger.warning(f"[Mission] register {key}: {e}")
        logger.info(f"[Mission] Registered {len(BUILTIN_MISSIONS)} built-in missions")

    # ------------------------------------------------------------
    # Phase management
    # ------------------------------------------------------------
    def set_phase(self, phase: str, status: str = "running",
                  details: str = ""):
        """Update system phase."""
        try:
            with get_conn() as conn:
                # Close previous
                conn.execute(
                    "UPDATE system_phase SET status = 'completed', "
                    "completed_at = ? WHERE status = 'running'",
                    (time.time(),)
                )
                # Start new
                conn.execute(
                    "INSERT INTO system_phase (phase, status, details, started_at) "
                    "VALUES (?, ?, ?, ?)",
                    (phase, status, details, time.time())
                )
                conn.commit()
            logger.info(f"[Mission] Phase -> {phase} ({status})")
            try:
                log_event("mission_phase", {"phase": phase, "status": status,
                                            "details": details})
            except Exception:
                pass
        except Exception as e:
            logger.error(f"[Mission] set_phase: {e}")

    def get_current_phase(self) -> Dict:
        try:
            with get_conn() as conn:
                row = conn.execute(
                    "SELECT * FROM system_phase ORDER BY id DESC LIMIT 1"
                ).fetchone()
                return dict(row) if row else {"phase": "idle", "status": "idle"}
        except Exception:
            return {"phase": "idle", "status": "idle"}

    def get_phase_history(self, limit: int = 10) -> List[Dict]:
        try:
            with get_conn() as conn:
                rows = conn.execute(
                    "SELECT * FROM system_phase ORDER BY id DESC LIMIT ?",
                    (limit,)
                ).fetchall()
                return [dict(r) for r in rows]
        except Exception:
            return []

    # ------------------------------------------------------------
    # Mission management
    # ------------------------------------------------------------
    def start_mission(self, mission_key: str, custom_config: Dict = None) -> Dict:
        """Start a mission. If a mission is running, it stops and new starts."""
        # Stop current
        if self.mission_running:
            logger.info(f"[Mission] Switching from {self.current_mission} to {mission_key}")
            self._stop.set()
            if self._thread:
                self._thread.join(timeout=5)

        # Get mission config
        if mission_key in BUILTIN_MISSIONS:
            config = BUILTIN_MISSIONS[mission_key]["config"].copy()
        else:
            # Custom mission from DB
            try:
                with get_conn() as conn:
                    row = conn.execute(
                        "SELECT * FROM missions WHERE mission_key = ?",
                        (mission_key,)
                    ).fetchone()
                    if not row:
                        return {"status": "error", "reason": "mission_not_found"}
                    config = json.loads(row["config"] or "{}")
            except Exception as e:
                return {"status": "error", "error": str(e)}

        if custom_config:
            config.update(custom_config)

        with self._lock:
            self.current_mission = mission_key
            self.current_config = config
            self.mission_running = True

        # Mark in DB
        try:
            with get_conn() as conn:
                conn.execute(
                    "UPDATE missions SET status = 'running', started_at = ?, "
                    "progress = 0.0, items_done = 0, items_failed = 0 "
                    "WHERE mission_key = ?",
                    (time.time(), mission_key)
                )
                conn.commit()
        except Exception:
            pass

        # Start thread
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._mission_loop,
            args=(mission_key, config),
            daemon=True,
        )
        self._thread.start()

        logger.info(f"[Mission] Started: {mission_key}")
        try:
            log_event("mission", {"action": "start", "key": mission_key,
                                  "config": config})
        except Exception:
            pass

        return {
            "status": "started",
            "mission": mission_key,
            "config": config,
        }

    def stop_mission(self) -> Dict:
        """Stop current mission."""
        if not self.mission_running:
            return {"status": "no_mission"}
        self._stop.set()
        self.mission_running = False
        mission = self.current_mission
        self.current_mission = None
        logger.info(f"[Mission] Stopped: {mission}")
        return {"status": "stopped", "mission": mission}

    def _mission_loop(self, mission_key: str, config: Dict):
        """Main loop for a mission."""
        target = config.get("target_count", 100000)
        platforms = config.get("platforms", [])
        query = config.get("query", "default")
        limit = config.get("limit", 50)
        mission_type = config.get("type", "generic")

        items_done = 0
        items_failed = 0
        cycle = 0

        while not self._stop.is_set():
            cycle += 1
            logger.info(f"[Mission:{mission_key}] Cycle {cycle}, "
                        f"done={items_done}/{target}")
            
            try:
                result = self._execute_cycle(
                    mission_key, mission_type, platforms, query, limit
                )
                items_done += result.get("success", 0)
                items_failed += result.get("failed", 0)

                # Update progress
                progress = min(100.0, (items_done / max(1, target)) * 100)
                self._update_progress(mission_key, progress,
                                      items_done, items_failed)

                if progress >= 100:
                    logger.info(f"[Mission:{mission_key}] COMPLETED")
                    self._complete_mission(mission_key)
                    break

            except Exception as e:
                logger.error(f"[Mission] cycle error: {e}")
                items_failed += 1

            # Update DB progress every cycle
            self._stop.wait(30)

        self.mission_running = False

    def _execute_cycle(self, mission_key: str, mission_type: str,
                       platforms: List, query: str, limit: int) -> Dict:
        """Execute one cycle based on mission type."""
        success = 0
        failed = 0

        if mission_type == "code":
            try:
                from collect.multi_platform import collector
                for platform in platforms:
                    try:
                        r = collector.collect_from_specific_platform(
                            platform, query, limit
                        )
                        success += 1
                    except Exception:
                        failed += 1
            except Exception as e:
                logger.warning(f"[Mission] code collect: {e}")
                failed += 1

        elif mission_type == "news":
            try:
                # Use generic collection
                from collect.multi_platform import collector
                r = collector.collect_all(query=query, limit=limit)
                success += len(r) if isinstance(r, dict) else 1
            except Exception:
                failed += 1

        elif mission_type == "vulnerability":
            try:
                from agents.vuln_intel_agent import vuln_intel_agent
                r = vuln_intel_agent.run_cycle()
                success += r.get("collected", 0)
            except Exception as e:
                logger.warning(f"[Mission] vuln: {e}")
                failed += 1

        elif mission_type == "training":
            try:
                from core.memory import memory
                memory._auto_process()
                success += 1
            except Exception:
                failed += 1

        elif mission_type == "merge":
            try:
                from model_merger import model_merger
                model_merger.merge_all()
                success += 1
            except Exception:
                failed += 1

        elif mission_type == "signup":
            try:
                from cloud_provisioner import CloudProvisioner
                cp = CloudProvisioner()
                providers = ["huggingface", "openrouter", "together"]
                for p in providers:
                    try:
                        r = cp.provision(p)
                        if r.get("status") in ("success", "created"):
                            success += 1
                        else:
                            failed += 1
                    except Exception:
                        failed += 1
            except Exception:
                failed += 1

        else:
            # Generic: collect from any platform
            try:
                from collect.multi_platform import collector
                r = collector.collect_all(query=query, limit=limit)
                success += len(r) if isinstance(r, dict) else 1
            except Exception:
                failed += 1

        return {"success": success, "failed": failed}

    def _update_progress(self, mission_key: str, progress: float,
                         done: int, failed: int):
        try:
            with get_conn() as conn:
                conn.execute(
                    "UPDATE missions SET progress = ?, items_done = ?, "
                    "items_failed = ? WHERE mission_key = ?",
                    (progress, done, failed, mission_key)
                )
                conn.commit()
        except Exception:
            pass

    def _complete_mission(self, mission_key: str):
        try:
            with get_conn() as conn:
                conn.execute(
                    "UPDATE missions SET status = 'completed', "
                    "completed_at = ?, progress = 100.0 WHERE mission_key = ?",
                    (time.time(), mission_key)
                )
                conn.commit()
            try:
                log_event("mission", {"action": "complete", "key": mission_key})
            except Exception:
                pass
        except Exception:
            pass

    # ------------------------------------------------------------
    # List
    # ------------------------------------------------------------
    def list_missions(self) -> List[Dict]:
        try:
            with get_conn() as conn:
                rows = conn.execute(
                    "SELECT * FROM missions ORDER BY priority ASC, id ASC"
                ).fetchall()
                return [dict(r) for r in rows]
        except Exception:
            return []

    def status(self) -> Dict[str, Any]:
        return {
            "current_mission": self.current_mission,
            "mission_running": self.mission_running,
            "current_config": self.current_config,
            "current_phase": self.get_current_phase(),
            "phase_history": self.get_phase_history(5),
            "available_missions": list(BUILTIN_MISSIONS.keys()),
        }


# Singleton
mission_controller = MissionController()
