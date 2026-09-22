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

        # Keep-alive: prevents idle shutdown
        try:
            from keep_alive import keep_alive_manager
            import os as _os
            url = _os.environ.get("CG_KEEP_ALIVE_URL", "")
            keep_alive_manager.start(keep_alive_url=url or None)
            logger.info("[Control] Keep-alive started")
        except Exception as e:
            logger.warning(f"[Control] Keep-alive failed: {e}")

        # Autonomous Orchestrator: runs the full loop
        try:
            from orchestrator import orchestrator
            orchestrator.start()
            logger.info("[Control] Orchestrator started")
        except Exception as e:
            logger.warning(f"[Control] Orchestrator failed: {e}")

        # Auto-Scaler: grows the agent hierarchy dynamically
        try:
            from auto_scaler import auto_scaler
            auto_scaler.start()
            logger.info("[Control] Auto-Scaler started")
        except Exception as e:
            logger.warning(f"[Control] Auto-Scaler failed: {e}")

        # Email Pool: pre-creates real emails for fast provisioning
        try:
            from email_pool import email_pool
            email_pool.start()
            logger.info("[Control] Email Pool started")
        except Exception as e:
            logger.warning(f"[Control] Email Pool failed: {e}")
        # Distributed Manager: workers across clouds
        try:
            from distributed_manager import distributed_manager
            distributed_manager.start_watchdog()
            logger.info("[Control] Distributed Manager started")
        except Exception as e:
            logger.warning(f"[Control] Distributed Manager failed: {e}")
        # Million Runtime: 1M logical agents in memory
        try:
            from million_runtime import million_runtime
            million_runtime.start()
            logger.info("[Control] Million Runtime started")
        except Exception as e:
            logger.warning(f"[Control] Million Runtime failed: {e}")
        # Cloud Unifier: register all 245 providers on startup
        try:
            from cloud_unifier import register_all_providers_in_db, count_registered_providers
            r = register_all_providers_in_db()
            c = count_registered_providers()
            logger.info(f"[Control] Cloud Unifier registered: {r} | Total: {c}")
        except Exception as e:
            logger.warning(f"[Control] Cloud Unifier registration failed: {e}")
        # Auto-Deployer: scales workers across clouds automatically
        try:
            from auto_deployer import auto_deployer
            auto_deployer.start()
            logger.info("[Control] Auto-Deployer started")
        except Exception as e:
            logger.warning(f"[Control] Auto-Deployer failed: {e}")
        # Bootstrap Controller: orchestrates the 6 phases
        try:
            from bootstrap_controller import bootstrap_controller
            bootstrap_controller.start()
            logger.info("[Control] Bootstrap Controller started")
        except Exception as e:
            logger.warning(f"[Control] Bootstrap Controller failed: {e}")

        # Cloud Multiplier: doubles clouds when load rises
        try:
            from cloud_multiplier import cloud_multiplier
            cloud_multiplier.start()
            logger.info("[Control] Cloud Multiplier started")
        except Exception as e:
            logger.warning(f"[Control] Cloud Multiplier failed: {e}")
        # CF Multi-Account Manager: deploys workers on all CF accounts
        try:
            from multi_account_manager import multi_account_manager
            multi_account_manager.start()
            logger.info("[Control] CF Multi-Account Manager started")
        except Exception as e:
            logger.warning(f"[Control] CF Multi-Account failed: {e}")

        # Initial Provisioning: create accounts on free clouds
        try:
            import threading as _thr
            def _initial_provision():
                import time as _t
                _t.sleep(20)  # wait for system to settle
                try:
                    from cloud_provisioner import CloudProvisioner
                    cp = CloudProvisioner()
                    # Top 7 easy providers
                    for p in ["huggingface", "openrouter", "together",
                              "fireworks", "replicate", "cohere", "deepseek"]:
                        try:
                            r = cp.provision(p, country=None)
                            logger.info(f"[Control] Provision {p}: {r.get('status')}")
                        except Exception as _e:
                            logger.warning(f"[Control] Provision {p}: {_e}")
                        _t.sleep(5)
                except Exception as _e:
                    logger.warning(f"[Control] Initial provision failed: {_e}")
            _thr.Thread(target=_initial_provision, daemon=True).start()
            logger.info("[Control] Initial provisioning scheduled")
        except Exception as e:
            logger.warning(f"[Control] Provisioning setup failed: {e}")

        t = threading.Thread(target=self._main_loop, daemon=True)
        t.start()
        self._threads.append(t)

        logger.info("[Control] All subsystems running")

    def stop(self):
        self._running = False
        cloud_health.stop_background()
        clinic.stop_watchdog()
        try:
            from keep_alive import keep_alive_manager
            keep_alive_manager.stop()
        except Exception:
            pass
        try:
            from orchestrator import orchestrator
            orchestrator.stop()
        except Exception:
            pass
        try:
            from auto_scaler import auto_scaler
            auto_scaler.stop()
        except Exception:
            pass
        try:
            from email_pool import email_pool
            email_pool.stop()
        except Exception:
            pass
        try:
            from distributed_manager import distributed_manager
            distributed_manager.stop_watchdog()
        except Exception:
            pass
        try:
            from million_runtime import million_runtime
            million_runtime.stop()
        except Exception:
            pass
        try:
            from cloud_multiplier import cloud_multiplier
            cloud_multiplier.stop()
        except Exception:
            pass
        try:
            from multi_account_manager import multi_account_manager
            multi_account_manager.stop()
        except Exception:
            pass
        try:
            from auto_deployer import auto_deployer
            auto_deployer.stop()
        except Exception:
            pass
        try:
            from bootstrap_controller import bootstrap_controller
            bootstrap_controller.stop()
        except Exception:
            pass
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
            "orchestrator": (lambda: __import__("orchestrator").orchestrator.status())(),
            "cloud_unifier": (lambda: __import__("cloud_unifier").cloud_unifier.status())(),
            "auto_scaler": (lambda: __import__("auto_scaler").auto_scaler.status())(),
            "email_pool": (lambda: __import__("email_pool").email_pool.stats())(),
            "distributed": (lambda: __import__("distributed_manager").distributed_manager.status())(),
            "master_deploy": (lambda: __import__("master_deploy").master_deployer.status())(),
            "bootstrap": (lambda: __import__("bootstrap_controller").bootstrap_controller.status())(),
            "mission": (lambda: __import__("mission_controller").mission_controller.status())(),
            "cloud_multiplier": (lambda: __import__("cloud_multiplier").cloud_multiplier.status())(),
            "cf_multi_account": (lambda: __import__("multi_account_manager").multi_account_manager.status())(),
            "cloud_health": {
                "weak": len(cloud_health.list_weak()),
                "healthy": len(cloud_health.list_healthy()),
            },
            "clinic": clinic.status(),
            "knowledge": knowledge_bus.stats(),
            "database": db_stats,
        }


control_plane = ControlPlane()
