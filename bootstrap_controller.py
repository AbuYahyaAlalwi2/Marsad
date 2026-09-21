"""
CYBERGUARD OS - Bootstrap Controller
Orchestrates the 6 phases:
  SEED -> PROVISION -> REGISTER -> UNIFY -> SCALE -> OPERATE
Then runs missions (collect, train, merge, etc.)
"""
import os
import time
import logging
import threading
from typing import Dict, Any, Optional

from db import log_event
from mission_controller import mission_controller

logger = logging.getLogger(__name__)


class BootstrapController:
    """
    Controls the full lifecycle from startup to full operation.
    """
    
    SEED_AGENTS = int(os.environ.get("CG_SEED_AGENTS", "10"))
    PROVISION_TARGET = int(os.environ.get("CG_PROVISION_TARGET", "50"))
    REGISTER_TARGET = int(os.environ.get("CG_REGISTER_TARGET", "20"))
    SCALE_TARGET = int(os.environ.get("CG_SCALE_TARGET", "1000000"))
    
    def __init__(self):
        self.running = False
        self.current_phase = "idle"
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self.phase_history = []
    
    # ------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------
    def start(self):
        if self.running:
            return
        self.running = True
        self._stop.clear()
        self._thread = threading.Thread(target=self._run_phases, daemon=True)
        self._thread.start()
        logger.info("[Bootstrap] Started")
    
    def stop(self):
        self.running = False
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
    
    # ------------------------------------------------------------
    # Main phase runner
    # ------------------------------------------------------------
    def _run_phases(self):
        try:
            self._phase_seed()
            self._phase_provision()
            self._phase_register()
            self._phase_unify()
            self._phase_scale()
            self._phase_operate()
        except Exception as e:
            logger.error(f"[Bootstrap] Error: {e}")
            mission_controller.set_phase("error", "failed", str(e))
    
    def _set_phase(self, name: str, status: str = "running", details: str = ""):
        with self._lock:
            self.current_phase = name
            self.phase_history.append({
                "phase": name,
                "status": status,
                "ts": time.time(),
            })
        mission_controller.set_phase(name, status, details)
        logger.info(f"[Bootstrap] Phase -> {name} ({status})")
    
    # ------------------------------------------------------------
    # Phase 1: SEED
    # ------------------------------------------------------------
    def _phase_seed(self):
        self._set_phase("seed", "running",
                        f"Start with {self.SEED_AGENTS} agents on Render")
        
        try:
            # Just start Mission Controller with a light mission
            from million_runtime import million_runtime
            # Ensure runtime is running but don't force 1M
            if not million_runtime.running:
                million_runtime.start()
        except Exception as e:
            logger.warning(f"[Bootstrap] Seed: {e}")
        
        time.sleep(5)
        self._set_phase("seed", "completed",
                        f"Seed agents ready: {self.SEED_AGENTS}")
    
    # ------------------------------------------------------------
    # Phase 2: PROVISION
    # ------------------------------------------------------------
    def _phase_provision(self):
        self._set_phase("provision", "running",
                        "Attempt to create accounts on cloud providers")
        
        try:
            from cloud_provisioner import CloudProvisioner
            cp = CloudProvisioner()
            
            # Try top free providers
            providers = [
                "huggingface", "openrouter", "together",
                "fireworks", "replicate", "cohere", "deepseek",
            ]
            
            created = 0
            failed = 0
            for p in providers:
                if self._stop.is_set():
                    break
                try:
                    r = cp.provision(p, country=None)
                    status = r.get("status", "unknown")
                    if status in ("success", "created"):
                        created += 1
                    else:
                        failed += 1
                    logger.info(f"[Bootstrap] {p}: {status}")
                except Exception as e:
                    failed += 1
                    logger.warning(f"[Bootstrap] {p}: {e}")
                time.sleep(2)
            
            details = f"Created: {created}, Failed: {failed}"
            self._set_phase("provision", "completed", details)
        except Exception as e:
            logger.error(f"[Bootstrap] Provision: {e}")
            self._set_phase("provision", "failed", str(e))
    
    # ------------------------------------------------------------
    # Phase 3: REGISTER
    # ------------------------------------------------------------
    def _phase_register(self):
        self._set_phase("register", "running",
                        "Register workers on clouds")
        
        try:
            from distributed_manager import distributed_manager
            from db import get_conn
            
            # Get all registered cloud accounts
            with get_conn() as conn:
                rows = conn.execute(
                    "SELECT provider_key FROM api_providers WHERE status='active' "
                    "LIMIT ?", (self.REGISTER_TARGET,)
                ).fetchall()
            
            registered = 0
            for r in rows:
                if self._stop.is_set():
                    break
                try:
                    node_id = f"worker-{r['provider_key']}"
                    distributed_manager.register_worker(
                        node_id=node_id,
                        provider=r["provider_key"],
                        region="auto",
                        endpoint="",
                        capacity=10000,
                    )
                    registered += 1
                except Exception:
                    pass
            
            self._set_phase("register", "completed",
                            f"Registered {registered} workers")
        except Exception as e:
            logger.error(f"[Bootstrap] Register: {e}")
            self._set_phase("register", "failed", str(e))
    
    # ------------------------------------------------------------
    # Phase 4: UNIFY
    # ------------------------------------------------------------
    def _phase_unify(self):
        self._set_phase("unify", "running",
                        "Unify clouds into single logical block")
        
        try:
            from cloud_unifier import register_all_providers_in_db, count_registered_providers
            register_all_providers_in_db()
            counts = count_registered_providers()
            self._set_phase("unify", "completed",
                            f"Unified: {counts}")
        except Exception as e:
            self._set_phase("unify", "failed", str(e))
    
    # ------------------------------------------------------------
    # Phase 5: SCALE
    # ------------------------------------------------------------
    def _phase_scale(self):
        self._set_phase("scale", "running",
                        f"Scale agents to {self.SCALE_TARGET:,}")
        
        try:
            from auto_scaler import auto_scaler
            # Bootstrap to stage 4 (10K) first
            auto_scaler.force_stage(4)
            time.sleep(3)
            # Then to stage 6 (1M) — but only if fast
            # Actually, we let it grow naturally; but for demo, push to 6
            # In production, don't force — let it grow by load
            auto_scaler.force_stage(6)
            self._set_phase("scale", "completed",
                            f"Scaled to {auto_scaler.current:,} agents")
        except Exception as e:
            self._set_phase("scale", "failed", str(e))
    
    # ------------------------------------------------------------
    # Phase 6: OPERATE
    # ------------------------------------------------------------
    def _phase_operate(self):
        self._set_phase("operate", "running",
                        "Start missions (collect, train, merge)")
        
        # Start default mission
        try:
            mission_controller.start_mission("collect_code",
                                             {"target_count": 100000})
            logger.info("[Bootstrap] Default mission started: collect_code")
        except Exception as e:
            logger.error(f"[Bootstrap] mission start: {e}")
        
        self._set_phase("operate", "running",
                        "Missions running. System fully operational.")
    
    # ------------------------------------------------------------
    # Status
    # ------------------------------------------------------------
    def status(self) -> Dict[str, Any]:
        return {
            "running": self.running,
            "current_phase": self.current_phase,
            "phase_history": self.phase_history[-10:],
            "mission": mission_controller.status(),
            "config": {
                "seed_agents": self.SEED_AGENTS,
                "provision_target": self.PROVISION_TARGET,
                "register_target": self.REGISTER_TARGET,
                "scale_target": self.SCALE_TARGET,
            },
        }


# Singleton
bootstrap_controller = BootstrapController()
