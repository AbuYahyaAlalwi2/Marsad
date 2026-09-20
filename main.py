"""
CYBERGUARD OS - Main Entry Point
Run: python main.py
"""
import os
import sys
import time
import signal
import logging
import threading
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
os.chdir(BASE)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("cyberguard")

try:
    from db import _ensure_db
    _ensure_db()
except Exception as e:
    logger.error(f"DB init failed: {e}")

RUNNING = True


def shutdown(sig, frame):
    global RUNNING
    RUNNING = False
    logger.info("Shutdown signal received")
    try:
        from control_plane import control_plane
        control_plane.stop()
    except Exception:
        pass


def main():
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    logger.info("=" * 60)
    logger.info("CYBERGUARD OS - Starting")
    logger.info("=" * 60)

    # 1. Control Plane
    try:
        from control_plane import control_plane
        control_plane.start()
        logger.info("[Main] Control Plane started")
    except Exception as e:
        logger.error(f"[Main] Control Plane failed: {e}")

    # 2. Worker Pool
    try:
        from worker_pool import worker_pool
        worker_pool.start()
        logger.info("[Main] Worker Pool started")
    except Exception as e:
        logger.error(f"[Main] Worker Pool failed: {e}")

    # 3. Dashboard API (threaded)
    try:
        from dashboard_api import app
        port = int(os.environ.get("PORT", "5000"))
        t = threading.Thread(
            target=lambda: app.run(host="0.0.0.0", port=port,
                                   debug=False, use_reloader=False),
            daemon=True,
        )
        t.start()
        logger.info(f"[Main] Dashboard API on :{port}")
    except Exception as e:
        logger.error(f"[Main] API server failed: {e}")

    # 4. Keep alive
    logger.info("[Main] All systems running. Press Ctrl+C to stop.")
    while RUNNING:
        time.sleep(1)

    logger.info("[Main] Shutdown complete")


if __name__ == "__main__":
    main()
