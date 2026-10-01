"""Scheduler — ملخصات دورية للمالك عبر Telegram."""
from __future__ import annotations
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


class Scheduler:
    """يرسل ملخصات دورية."""

    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._last_hour = 0
        self._last_day = 0

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info("[scheduler] started")

    def stop(self):
        self._stop.set()

    def _loop(self):
        while not self._stop.is_set():
            try:
                now = datetime.now()
                hour_key = now.hour
                day_key = now.day

                # كل ساعة
                if hour_key != self._last_hour and now.minute >= 5:
                    self._send_hourly()
                    self._last_hour = hour_key

                # كل يوم 8 صباحاً
                if day_key != self._last_day and now.hour == 8:
                    self._send_daily()
                    self._last_day = day_key

            except Exception as e:
                logger.warning(f"[scheduler] tick error: {e}")

            time.sleep(60)

    def _send_hourly(self):
        try:
            from tools.notifier import notify_hourly
            import httpx
            try:
                r = httpx.get(
                    "https://huggingface.co/datasets/AbuYahya2/"
                    "marsad-endpoints/raw/main/status.json",
                    timeout=15)
                if r.status_code == 200:
                    notify_hourly(r.json())
                else:
                    notify_hourly({"round": "?", "tier": "?", "last_score": "?"})
            except Exception:
                notify_hourly({"round": "?", "tier": "?", "last_score": "?"})
        except Exception as e:
            logger.warning(f"[scheduler] hourly failed: {e}")

    def _send_daily(self):
        try:
            from tools.notifier import send, S
            from core.account_pool import account_pool
            stats = account_pool.stats()
            lines = [f"{S['start']} <b>تقرير يومي</b>", ""]
            for k, v in stats.items():
                lines.append(f"{S['div']} {k}: {v['count']} ({v['active']})")
            send("\n".join(lines))
        except Exception as e:
            logger.warning(f"[scheduler] daily failed: {e}")


scheduler = Scheduler()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    scheduler._send_daily()
    print("✓ scheduler test done")
