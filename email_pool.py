"""
CYBERGUARD OS - Warm Email Pool (Real emails via mail.tm)
Pre-creates real temporary emails so provisioning is instant.
Uses mail.tm API directly - real working emails, no simulation.
"""
import os
import time
import logging
import random
import threading
import requests
from typing import Dict, Any, Optional

from db import get_conn, log_event

logger = logging.getLogger(__name__)


POOL_SCHEMA = """
CREATE TABLE IF NOT EXISTS email_pool (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password TEXT,
    token TEXT,
    service TEXT,
    used INTEGER DEFAULT 0,
    created_at REAL NOT NULL,
    used_at REAL
);
CREATE INDEX IF NOT EXISTS idx_email_pool_used ON email_pool(used);
"""


class EmailPool:
    """Pre-created real emails via mail.tm."""

    def __init__(self):
        self.target_size = int(os.environ.get("CG_EMAIL_POOL_SIZE", "50"))
        self.refill_threshold = int(os.environ.get("CG_EMAIL_POOL_REFILL", "20"))
        self.running = False
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._ensure_schema()

    def _ensure_schema(self):
        try:
            with get_conn() as conn:
                conn.executescript(POOL_SCHEMA)
                conn.commit()
        except Exception as e:
            logger.error(f"[EmailPool] schema failed: {e}")

    # ------------------------------------------------------------
    # Pool counts
    # ------------------------------------------------------------
    def count_available(self) -> int:
        try:
            with get_conn() as conn:
                row = conn.execute(
                    "SELECT COUNT(*) as c FROM email_pool WHERE used = 0"
                ).fetchone()
                return row["c"] if row else 0
        except Exception:
            return 0

    def count_total(self) -> int:
        try:
            with get_conn() as conn:
                row = conn.execute("SELECT COUNT(*) as c FROM email_pool").fetchone()
                return row["c"] if row else 0
        except Exception:
            return 0

    def stats(self) -> Dict[str, int]:
        return {
            "available": self.count_available(),
            "total": self.count_total(),
            "target": self.target_size,
        }

    # ------------------------------------------------------------
    # Produce - real mail.tm
    # ------------------------------------------------------------
    def _create_mail_tm(self) -> Optional[Dict[str, Any]]:
        """Create a real mail.tm account."""
        try:
            session = requests.Session()
            session.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })

            # 1. Get domain
            r = session.get("https://api.mail.tm/domains", timeout=20)
            if r.status_code != 200:
                return None
            domains = r.json().get("hydra:member", [])
            if not domains:
                return None
            domain = domains[0]["domain"]

            # 2. Create account
            username = f"marsad_{random.randint(100000, 999999)}_{int(time.time()) % 10000}"
            password = f"Mr{random.randint(100000, 999999)}!X{random.randint(10, 99)}"
            address = f"{username}@{domain}"

            r = session.post(
                "https://api.mail.tm/accounts",
                json={"address": address, "password": password},
                timeout=20,
            )
            if r.status_code not in (200, 201):
                return None

            # 3. Get token
            r = session.post(
                "https://api.mail.tm/token",
                json={"address": address, "password": password},
                timeout=20,
            )
            token = r.json().get("token") if r.status_code == 200 else None

            return {
                "email": address,
                "password": password,
                "token": token,
                "service": "mail.tm",
                "real": True,
            }
        except Exception as e:
            logger.warning(f"[EmailPool] mail.tm failed: {e}")
            return None

        try:
            r = requests.get(
                timeout=15,
            )
            emails = r.json()
            if not emails:
                return None
            address = emails[0]
            login, domain = address.split("@")
            return {
                "email": address,
                "login": login,
                "domain": domain,
                "real": True,
            }
        except Exception as e:
            return None

    def produce_one(self) -> Optional[Dict[str, Any]]:
        """Create one real email and add it to the pool."""
        email_data = self._create_mail_tm()
        if not email_data:
            return None

        try:
            with get_conn() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO email_pool "
                    "(email, password, token, service, used, created_at) "
                    "VALUES (?, ?, ?, ?, 0, ?)",
                    (
                        email_data.get("email"),
                        email_data.get("password"),
                        email_data.get("token"),
                        email_data.get("service", "unknown"),
                        time.time(),
                    )
                )
                conn.commit()
            logger.info(f"[EmailPool] + {email_data.get('email')} ({email_data.get('service')})")
            return email_data
        except Exception as e:
            logger.warning(f"[EmailPool] insert failed: {e}")
            return None

    def consume_one(self) -> Optional[Dict[str, Any]]:
        """Get an unused email and mark it used."""
        with self._lock:
            try:
                with get_conn() as conn:
                    row = conn.execute(
                        "SELECT * FROM email_pool WHERE used = 0 "
                        "ORDER BY created_at ASC LIMIT 1"
                    ).fetchone()

                    if not row:
                        logger.info("[EmailPool] Pool empty, creating on-demand...")
                        return self.produce_one()

                    conn.execute(
                        "UPDATE email_pool SET used = 1, used_at = ? WHERE id = ?",
                        (time.time(), row["id"])
                    )
                    conn.commit()
                    return dict(row)
            except Exception as e:
                logger.error(f"[EmailPool] consume failed: {e}")
                return None

    # ------------------------------------------------------------
    # Background refill
    # ------------------------------------------------------------
    def start(self):
        if self.running:
            return
        self.running = True
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info(f"[EmailPool] Started (target={self.target_size})")

    def stop(self):
        self.running = False
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _loop(self):
        while not self._stop.is_set():
            try:
                self._refill()
            except Exception as e:
                logger.error(f"[EmailPool] refill error: {e}")
            self._stop.wait(60)

    def _refill(self):
        current = self.count_available()
        if current >= self.target_size:
            return
        need = self.target_size - current
        logger.info(f"[EmailPool] Refilling: need {need} (have {current})")

        for i in range(need):
            if self._stop.is_set():
                break
            self.produce_one()
            time.sleep(2)

    def refill_now(self, count: int = 10) -> int:
        added = 0
        for i in range(count):
            if self.produce_one():
                added += 1
            time.sleep(1.5)
        return added


# Singleton
email_pool = EmailPool()


# ============================================================
# Dynamic capacity management
# ============================================================
def ensure_capacity(self, needed: int) -> Dict[str, int]:
    """
    Ensure pool has at least `needed` emails available.
    Grows target_size if needed, triggers immediate production.
    """
    current = self.count_available()
    if current >= needed:
        return {"status": "ok", "available": current, "needed": needed}

    # Grow target
    new_target = max(self.target_size, needed + 20)  # buffer of 20
    self.target_size = new_target
    logger.info(f"[EmailPool] Target grew: {new_target}")

    # Produce in background
    deficit = needed - current
    threading.Thread(
        target=self._produce_n,
        args=(deficit,),
        daemon=True,
    ).start()

    return {
        "status": "growing",
        "available": current,
        "needed": needed,
        "new_target": new_target,
        "producing": deficit,
    }


def _produce_n(self, count: int):
    """Produce N emails (internal, throttled)."""
    for i in range(count):
        if self._stop.is_set():
            break
        self.produce_one()
        time.sleep(1.5)


def expand_for_clouds(self, buffer: int = 20) -> Dict[str, int]:
    """
    Compute max demand from:
      - MULTI_KEY_POLICY (LLM providers)
      - cloud_unifier (cloud providers)
      - API_PROVIDERS from config
    then grow the pool to match.
    """
    try:
        from config import MULTI_KEY_POLICY, API_PROVIDERS

        demand = 0
        sources = []

        # 1. LLM providers from MULTI_KEY_POLICY
        for name, policy in MULTI_KEY_POLICY.items():
            if name == "default":
                continue
            if policy.get("allows_multi"):
                mx = policy.get("max_accounts", 1)
                demand += mx
                sources.append(f"llm:{name}({mx})")

        # 2. Cloud providers from API_PROVIDERS
        for name, cfg in API_PROVIDERS.items():
            demand += 1
            sources.append(f"api:{name}")

        # 3. Estimate cloud demand (top 50 free cloud providers)
        try:
            from cloud_unifier import cloud_unifier
            free = cloud_unifier.list_free_tier()
            cloud_count = min(len(free), 50)  # cap
            demand += cloud_count
            sources.append(f"cloud_free:{cloud_count}")
        except Exception:
            pass

        needed = demand + buffer
        logger.info(f"[EmailPool] Demand: {demand} + buffer {buffer} = {needed}")

        result = ensure_capacity(self, needed)
        result["sources"] = sources[:10]
        return result

    except Exception as e:
        logger.error(f"[EmailPool] expand_for_clouds failed: {e}")
        return {"status": "error", "error": str(e)}


def get_demand_report(self) -> Dict[str, Any]:
    """Report current demand vs availability."""
    try:
        from config import MULTI_KEY_POLICY, API_PROVIDERS

        breakdown = []
        total = 0

        # LLM providers
        for name, policy in MULTI_KEY_POLICY.items():
            if name == "default":
                continue
            if policy.get("allows_multi"):
                mx = policy.get("max_accounts", 1)
                breakdown.append({"type": "llm", "provider": name, "max": mx})
                total += mx

        # API providers
        for name in API_PROVIDERS.keys():
            breakdown.append({"type": "api", "provider": name, "max": 1})
            total += 1

        # Cloud providers (free)
        try:
            from cloud_unifier import cloud_unifier
            free = cloud_unifier.list_free_tier()
            cloud_top = free[:50]
            for info in cloud_top:
                breakdown.append({
                    "type": "cloud",
                    "provider": info.get("name", "?"),
                    "max": 1,
                })
            total += len(cloud_top)
        except Exception:
            pass

        return {
            "total_demand": total,
            "providers_counted": len(breakdown),
            "available": self.count_available(),
            "target": self.target_size,
            "deficit": max(0, total - self.count_available()),
            "breakdown": breakdown[:15],
        }
    except Exception as e:
        return {"error": str(e)}


# Attach as methods
EmailPool.ensure_capacity = ensure_capacity
EmailPool._produce_n = _produce_n
EmailPool.expand_for_clouds = expand_for_clouds
EmailPool.get_demand_report = get_demand_report
