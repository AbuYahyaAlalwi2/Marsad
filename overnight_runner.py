"""
CYBERGUARD OS - Overnight Runner
Runs everything autonomously all night:
  - Wakelock (keeps Termux alive)
  - Bootstraps 1M agents
  - Registers worker node
  - Runs aggressive orchestration
  - Fills email pool
  - Auto-provisions clouds
"""
import os
import sys
import time
import signal
import logging
import threading
import subprocess
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
os.chdir(BASE)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(BASE / "data" / "overnight.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("overnight")

RUNNING = True


def acquire_wakelock():
    """Prevent Android from killing Termux."""
    try:
        subprocess.run(["termux-wake-lock"], check=False, timeout=5)
        logger.info("[Overnight] Wakelock acquired")
    except Exception as e:
        logger.warning(f"[Overnight] Wakelock failed: {e}")


def release_wakelock():
    try:
        subprocess.run(["termux-wake-unlock"], check=False, timeout=5)
    except Exception:
        pass


def bootstrap_agents():
    """Force agents to stage 6 (1M)."""
    try:
        from auto_scaler import auto_scaler
        logger.info("[Overnight] Bootstrapping to 1,000,000 agents...")
        t0 = time.time()
        r = auto_scaler.force_stage(6)
        elapsed = time.time() - t0
        logger.info(f"[Overnight] Bootstrap done in {elapsed:.1f}s: {r}")
    except Exception as e:
        logger.error(f"[Overnight] Bootstrap failed: {e}")


def register_local_worker():
    """Register this device as a local worker node."""
    try:
        from distributed_manager import distributed_manager
        r = distributed_manager.register_worker(
            node_id="termux-local",
            provider="termux",
            region="local",
            endpoint="local",
            capacity=1000000,
        )
        logger.info(f"[Overnight] Local worker registered: {r}")
    except Exception as e:
        logger.error(f"[Overnight] Worker register failed: {e}")


def start_control_plane():
    try:
        from control_plane import control_plane
        control_plane.start()
        logger.info("[Overnight] Control Plane started")
    except Exception as e:
        logger.error(f"[Overnight] Control Plane failed: {e}")


def start_worker_pool():
    try:
        from worker_pool import worker_pool
        worker_pool.start(worker_count=4)
        worker_pool.deploy_agents(100)
        logger.info("[Overnight] Worker Pool started")
    except Exception as e:
        logger.error(f"[Overnight] Worker Pool failed: {e}")


def force_full_cycle():
    """Force collect + provision + train + merge + upload."""
    try:
        from collect.multi_platform import collector
        logger.info("[Overnight] Collecting data...")
        collector.collect_all(query="security vulnerability", limit=20)
        logger.info("[Overnight] Collection done")
    except Exception as e:
        logger.error(f"[Overnight] Collect failed: {e}")

    try:
        from cloud_provisioner import CloudProvisioner
        logger.info("[Overnight] Provisioning cloud accounts...")
        cp = CloudProvisioner()
        # Try top 5 free providers
        for provider in ["huggingface", "openrouter", "together", "fireworks", "replicate"]:
            try:
                r = cp.provision(provider, country=None)
                logger.info(f"[Overnight] {provider}: {r.get('status')}")
            except Exception as e:
                logger.warning(f"[Overnight] {provider} failed: {e}")
    except Exception as e:
        logger.error(f"[Overnight] Provision failed: {e}")

    try:
        from model_merger import model_merger
        logger.info("[Overnight] Merging models...")
        model_merger.merge_all()
        logger.info("[Overnight] Merge done")
    except Exception as e:
        logger.error(f"[Overnight] Merge failed: {e}")


def run_loop():
    """Main loop: run full cycle every 5 minutes."""
    cycle = 0
    while RUNNING:
        cycle += 1
        logger.info(f"[Overnight] ===== Cycle {cycle} =====")

        # Refresh email pool
        try:
            from email_pool import email_pool
            email_pool.refill_now(3)
        except Exception as e:
            logger.warning(f"[Overnight] Email refill: {e}")

        # Full cycle every 2 cycles
        if cycle % 2 == 0:
            force_full_cycle()

        # Heartbeat local worker
        try:
            from distributed_manager import distributed_manager
            import psutil
            try:
                cpu = psutil.cpu_percent(interval=0.1)
                ram = psutil.virtual_memory().percent
            except Exception:
                cpu, ram = 0, 0
            distributed_manager.heartbeat(
                node_id="termux-local",
                cpu=cpu, ram=ram,
                active_agents=1000000,
                queue_size=0,
            )
        except Exception:
            pass

        # Sleep 5 minutes
        for _ in range(300):
            if not RUNNING:
                break
            time.sleep(1)


def shutdown(sig, frame):
    global RUNNING
    RUNNING = False
    logger.info("[Overnight] Shutdown signal received")
    release_wakelock()


def main():
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    logger.info("=" * 60)
    logger.info("CYBERGUARD OS - OVERNIGHT MODE")
    logger.info("=" * 60)

    acquire_wakelock()
    bootstrap_agents()
    register_local_worker()
    start_control_plane()
    start_worker_pool()

    logger.info("[Overnight] All systems GO. Running until shutdown.")
    run_loop()

    logger.info("[Overnight] Stopped cleanly")


if __name__ == "__main__":
    main()
