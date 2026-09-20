"""
CYBERGUARD OS - Cloud Health Monitor
"""
import time
import logging
import threading
import requests
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict

from db import get_conn, log_event
from config import (
    CLOUD_HEALTH_INTERVAL, CLOUD_MAX_LATENCY_MS,
    CLOUD_MAX_ERROR_RATE, CLOUD_MIN_FREE_QUOTA,
    CLOUD_AUTO_PROVISION,
)

logger = logging.getLogger(__name__)


@dataclass
class ProviderHealth:
    provider: str
    latency_ms: float = 0.0
    error_rate: float = 0.0
    quota_used: float = 0.0
    status: str = "unknown"
    last_check: float = field(default_factory=time.time)
    consecutive_failures: int = 0
    consecutive_success: int = 0
    notes: str = ""


class CloudHealthMonitor:
    def __init__(self):
        self.health: Dict[str, ProviderHealth] = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def check_provider(self, provider_name: str) -> Dict[str, Any]:
        info = self._get_provider_info(provider_name)
        if not info:
            return {"provider": provider_name, "status": "not_found"}

        health = ProviderHealth(provider=provider_name)
        url = info.get("api_url") or info.get("env_key") or ""
        health.latency_ms = self._measure_latency(url)
        health.quota_used = self._get_quota_used(provider_name)
        health.error_rate = self._get_error_rate(provider_name)

        weak = (
            health.latency_ms > CLOUD_MAX_LATENCY_MS
            or health.error_rate > CLOUD_MAX_ERROR_RATE
            or health.quota_used > (1.0 - CLOUD_MIN_FREE_QUOTA)
        )
        health.status = "weak" if weak else "healthy"

        with self._lock:
            old = self.health.get(provider_name)
            if old:
                if weak:
                    health.consecutive_failures = old.consecutive_failures + 1
                    health.consecutive_success = 0
                else:
                    health.consecutive_success = old.consecutive_success + 1
                    health.consecutive_failures = 0
            self.health[provider_name] = health

        try:
            log_event("cloud_health", {
                "provider": provider_name,
                "status": health.status,
                "latency_ms": health.latency_ms,
                "quota_used": health.quota_used,
                "error_rate": health.error_rate,
            })
        except Exception:
            pass

        if weak and CLOUD_AUTO_PROVISION:
            self._trigger_provision(provider_name)

        return asdict(health)

    def check_all(self) -> Dict[str, Dict]:
        results = {}
        for name in self._list_providers():
            try:
                results[name] = self.check_provider(name)
            except Exception as e:
                logger.error(f"[Health] {name} check failed: {e}")
        return results

    def list_weak(self) -> List[str]:
        with self._lock:
            return [n for n, h in self.health.items() if h.status == "weak"]

    def list_healthy(self) -> List[str]:
        with self._lock:
            return [n for n, h in self.health.items() if h.status == "healthy"]

    def start_background(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info("[Health] Background monitor started")

    def stop_background(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _loop(self):
        while not self._stop.is_set():
            try:
                self.check_all()
            except Exception as e:
                logger.error(f"[Health] loop error: {e}")
            self._stop.wait(CLOUD_HEALTH_INTERVAL)

    def _measure_latency(self, url: Optional[str]) -> float:
        if not url or not url.startswith("http"):
            return 0.0
        try:
            start = time.time()
            requests.head(url, timeout=5, allow_redirects=True)
            return (time.time() - start) * 1000.0
        except Exception:
            return 9999.0

    def _get_quota_used(self, provider: str) -> float:
        try:
            with get_conn() as conn:
                row = conn.execute(
                    "SELECT used_today, daily_limit FROM api_providers WHERE provider_key = ?",
                    (provider,)
                ).fetchone()
                if row and row["daily_limit"]:
                    return row["used_today"] / row["daily_limit"]
        except Exception:
            pass
        return 0.0

    def _get_error_rate(self, provider: str) -> float:
        try:
            with get_conn() as conn:
                total = conn.execute(
                    "SELECT COUNT(*) as c FROM events WHERE channel LIKE ?",
                    (f"%{provider}%",)
                ).fetchone()["c"]
                if total == 0:
                    return 0.0
                errors = conn.execute(
                    "SELECT COUNT(*) as c FROM events WHERE channel LIKE ? "
                    "AND (payload LIKE '%error%' OR payload LIKE '%failed%')",
                    (f"%{provider}%",)
                ).fetchone()["c"]
                return errors / total
        except Exception:
            return 0.0

    def _list_providers(self) -> List[str]:
        try:
            with get_conn() as conn:
                rows = conn.execute(
                    "SELECT provider_key FROM api_providers WHERE status = 'active'"
                ).fetchall()
                return [r["provider_key"] for r in rows]
        except Exception:
            return []

    def _get_provider_info(self, name: str) -> Optional[Dict]:
        try:
            with get_conn() as conn:
                row = conn.execute(
                    "SELECT * FROM api_providers WHERE provider_key = ?", (name,)
                ).fetchone()
                return dict(row) if row else None
        except Exception:
            return None

    def _trigger_provision(self, provider: str):
        try:
            from queue_manager import enqueue_cloud_provision
            enqueue_cloud_provision(provider)
            logger.info(f"[Health] Provision triggered for {provider}")
        except Exception as e:
            logger.error(f"[Health] provision trigger failed: {e}")


cloud_health = CloudHealthMonitor()
