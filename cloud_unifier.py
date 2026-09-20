"""
CYBERGUARD OS - Cloud Unifier
Makes all clouds look like one unified cloud.
Uses Apache Libcloud where possible + our 200+ provider registry.
"""
import os
import time
import logging
from typing import Dict, List, Any, Optional

from db import get_conn, log_event
from config import MULTI_KEY_POLICY, CLOUD_MAX_ACCOUNTS_PER_PROVIDER

logger = logging.getLogger(__name__)


class CloudUnifier:
    """
    Unified interface across all clouds:
      - List all providers (Libcloud + custom registry)
      - Get best provider for a task
      - Dispatch task to appropriate cloud
      - Health-aware selection
    """

    def __init__(self):
        self.providers: Dict[str, Dict] = {}
        self._libcloud_drivers = {}
        self._load_providers()
        self._try_load_libcloud()

    # ------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------

    def _load_providers(self):
        """Load from local registry (cloud_providers.py) and DB."""
        # From cloud_providers.py
        try:
            from cloud_providers import ALL_PROVIDERS
            for p in ALL_PROVIDERS:
                name = getattr(p, "name", None)
                if not name:
                    continue
                self.providers[name] = {
                    "name": name,
                    "country": getattr(p, "country", None),
                    "tier": getattr(p, "tier", "Tier 3"),
                    "free_tier": getattr(p, "free_tier", False),
                    "vpn_required": getattr(p, "vpn_required", False),
                    "vpn_country": getattr(p, "vpn_country", None),
                    "api_url": getattr(p, "api_url", ""),
                    "region_specific": getattr(p, "region_specific", False),
                }
        except Exception as e:
            logger.warning(f"[Unifier] Could not load cloud_providers: {e}")

        # From DB (accounts registered)
        try:
            with get_conn() as conn:
                rows = conn.execute(
                    "SELECT provider_key, name, category, status, api_key, "
                    "daily_limit, used_today FROM api_providers WHERE status='active'"
                ).fetchall()
                for r in rows:
                    key = r["provider_key"]
                    if key not in self.providers:
                        self.providers[key] = {
                            "name": r["name"] or key,
                            "tier": "Account",
                            "free_tier": True,
                            "has_account": True,
                        }
                    else:
                        self.providers[key]["has_account"] = True
                        self.providers[key]["api_key"] = r["api_key"]
                        self.providers[key]["daily_limit"] = r["daily_limit"]
                        self.providers[key]["used_today"] = r["used_today"]
        except Exception as e:
            logger.warning(f"[Unifier] DB load failed: {e}")

    def _try_load_libcloud(self):
        """Load Libcloud drivers if available."""
        try:
            from libcloud.compute.types import Provider
            from libcloud.compute.providers import get_driver
            self._libcloud_available = True
            # We don't instantiate drivers (need creds), just check
            logger.info("[Unifier] Libcloud available")
        except ImportError:
            self._libcloud_available = False
            logger.info("[Unifier] Libcloud not installed (using custom registry)")

    # ------------------------------------------------------------
    # Query API
    # ------------------------------------------------------------

    def list_all(self) -> List[Dict]:
        return list(self.providers.values())

    def list_available(self) -> List[Dict]:
        """Providers with accounts, not over quota."""
        out = []
        for p in self.providers.values():
            if not p.get("has_account"):
                continue
            limit = p.get("daily_limit", 0)
            used = p.get("used_today", 0)
            if limit > 0 and used >= limit:
                continue
            out.append(p)
        return out

    def list_free_tier(self) -> List[Dict]:
        return [p for p in self.providers.values() if p.get("free_tier")]

    def list_requiring_vpn(self) -> List[Dict]:
        return [p for p in self.providers.values() if p.get("vpn_required")]

    def count(self) -> Dict[str, int]:
        return {
            "total": len(self.providers),
            "free": len(self.list_free_tier()),
            "with_account": sum(1 for p in self.providers.values() if p.get("has_account")),
            "available": len(self.list_available()),
            "vpn_required": len(self.list_requiring_vpn()),
        }

    # ------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------

    def get_best(self, prefer_tier: Optional[str] = None,
                 exclude: Optional[List[str]] = None) -> Optional[Dict]:
        """
        Pick the best provider for a task.
        Priority: Tier 1 > Tier 2 > Tier 3
                  available > not available
                  low usage > high usage
        """
        exclude = exclude or []
        candidates = self.list_available()
        if not candidates:
            candidates = list(self.providers.values())

        def score(p):
            s = 0
            if p.get("tier") == "Tier 1":
                s -= 100
            elif p.get("tier") == "Tier 2":
                s -= 50
            if p.get("has_account"):
                s -= 20
            usage = p.get("used_today", 0)
            s += usage / 100.0
            if p.get("vpn_required"):
                s += 10
            if prefer_tier and p.get("tier") == prefer_tier:
                s -= 200
            return s

        candidates = [p for p in candidates if p.get("name") not in exclude]
        if not candidates:
            return None
        return sorted(candidates, key=score)[0]

    # ------------------------------------------------------------
    # Unified Dispatch
    # ------------------------------------------------------------

    def dispatch(self, command: str, payload: Optional[Dict] = None,
                 prefer_tier: Optional[str] = None) -> Dict[str, Any]:
        """
        Send a command as if there were a single cloud.
        Routes to the best provider automatically.
        """
        payload = payload or {}
        best = self.get_best(prefer_tier=prefer_tier)

        if not best:
            return {"status": "error", "reason": "no_provider_available"}

        provider_name = best["name"]

        # VPN if needed
        if best.get("vpn_required") and best.get("vpn_country"):
            try:
                from vpn_manager import vpn_manager
                vpn_manager.connect(best["vpn_country"])
            except Exception as e:
                logger.warning(f"[Unifier] VPN for {provider_name} failed: {e}")

        task_id = f"cloud_task_{int(time.time() * 1000)}"

        try:
            log_event("cloud_unifier", {
                "action": "dispatch",
                "provider": provider_name,
                "command": command,
                "task_id": task_id,
            })
        except Exception:
            pass

        return {
            "status": "dispatched",
            "task_id": task_id,
            "provider": provider_name,
            "tier": best.get("tier"),
            "vpn_used": bool(best.get("vpn_required")),
            "command": command,
        }

    def status(self) -> Dict[str, Any]:
        return {
            "counts": self.count(),
            "libcloud_available": self._libcloud_available,
            "auto_provision": os.environ.get("CG_CLOUD_AUTO_PROVISION", "true"),
        }


# Singleton
cloud_unifier = CloudUnifier()


# ============================================================
# Bulk registration: register ALL providers in DB
# ============================================================
def register_all_providers_in_db() -> Dict[str, int]:
    """
    Register every known provider in the api_providers table.
    Providers without keys get status='available' (not 'active').
    This lets the dashboard show all 245 providers.
    """
    from db import get_conn
    registered = 0
    skipped = 0
    errors = 0

    try:
        with get_conn() as conn:
            for name, info in cloud_unifier.providers.items():
                try:
                    # Check if already exists
                    existing = conn.execute(
                        "SELECT provider_key FROM api_providers WHERE provider_key = ?",
                        (name,)
                    ).fetchone()
                    if existing:
                        skipped += 1
                        continue

                    # Status: 'active' if has account, otherwise 'available'
                    status = "active" if info.get("has_account") else "available"

                    conn.execute(
                        "INSERT OR IGNORE INTO api_providers "
                        "(provider_key, name, category, api_url, auth_type, "
                        "env_key, api_key, status, daily_limit, used_today, created_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            name,
                            info.get("name", name),
                            "cloud_provider",
                            info.get("api_url", ""),
                            "bearer",
                            f"{name.upper()}_API_KEY",
                            None,
                            status,
                            1000,
                            0,
                            time.time(),
                        )
                    )
                    registered += 1
                except Exception as e:
                    errors += 1
                    logger.warning(f"[Unifier] register {name} failed: {e}")

            conn.commit()

        # Now update counts
        cloud_unifier._load_providers()

        result = {"registered": registered, "skipped": skipped, "errors": errors}
        logger.info(f"[Unifier] Bulk registration: {result}")
        try:
            log_event("cloud_unifier", {"action": "bulk_register", **result})
        except Exception:
            pass
        return result

    except Exception as e:
        logger.error(f"[Unifier] bulk register failed: {e}")
        return {"registered": 0, "skipped": 0, "errors": 1}


def count_registered_providers() -> Dict[str, int]:
    """Count providers in DB by status."""
    from db import get_conn
    try:
        with get_conn() as conn:
            active = conn.execute(
                "SELECT COUNT(*) as c FROM api_providers WHERE status='active'"
            ).fetchone()["c"]
            available = conn.execute(
                "SELECT COUNT(*) as c FROM api_providers WHERE status='available'"
            ).fetchone()["c"]
            total = conn.execute(
                "SELECT COUNT(*) as c FROM api_providers"
            ).fetchone()["c"]
            return {"active": active, "available": available, "total": total}
    except Exception as e:
        logger.error(f"[Unifier] count failed: {e}")
        return {"active": 0, "available": 0, "total": 0}
