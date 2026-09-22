"""
CYBERGUARD OS - Multi-Account Manager
Manages N Cloudflare accounts (from different people).
Distributes workers across all accounts.
"""
import os
import re
import time
import json
import logging
import threading
from typing import Dict, List, Any, Optional

from db import get_conn, log_event

logger = logging.getLogger(__name__)


SCHEMA = """
CREATE TABLE IF NOT EXISTS cf_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT UNIQUE NOT NULL,
    token TEXT NOT NULL,
    name TEXT,
    owner TEXT,
    workers_count INTEGER DEFAULT 0,
    agents_capacity INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active',
    last_check REAL,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cf_status ON cf_accounts(status);
"""


class MultiAccountManager:
    """
    Manages multiple Cloudflare accounts.
    Auto-detects accounts from environment variables:
      CF_TOKEN_1 + CF_ACCOUNT_1
      CF_TOKEN_2 + CF_ACCOUNT_2
      ...
    Also supports legacy: CLOUDFLARE_API_TOKEN + CLOUDFLARE_ACCOUNT_ID
    """

    WORKERS_PER_ACCOUNT = int(os.environ.get("CF_WORKERS_PER_ACCOUNT", "10"))
    AGENTS_PER_WORKER = 10000

    def __init__(self):
        self.accounts: List[Dict] = []
        self.running = False
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._ensure_schema()

    def _ensure_schema(self):
        try:
            with get_conn() as conn:
                conn.executescript(SCHEMA)
                conn.commit()
        except Exception as e:
            logger.error(f"[CF-Multi] schema: {e}")

    # ------------------------------------------------------------
    # Auto-detect accounts from env
    # ------------------------------------------------------------
    def discover_accounts(self) -> List[Dict]:
        """Scan environment for CF_TOKEN_N / CF_ACCOUNT_N pairs."""
        found = []

        # 1. Legacy single account
        single_token = os.environ.get("CLOUDFLARE_API_TOKEN", "")
        single_account = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
        if single_token and single_account:
            found.append({
                "name": "primary",
                "owner": "owner_1",
                "token": single_token,
                "account_id": single_account,
            })

        # 2. Numbered accounts (CF_TOKEN_1, CF_ACCOUNT_1, etc.)
        for i in range(1, 101):  # Support up to 100 accounts
            token = os.environ.get(f"CF_TOKEN_{i}", "")
            account = os.environ.get(f"CF_ACCOUNT_{i}", "")
            if token and account:
                found.append({
                    "name": f"cf_{i}",
                    "owner": f"owner_{i}",
                    "token": token,
                    "account_id": account,
                })

        # 3. JSON blob (CF_ACCOUNTS = '[...]')
        json_blob = os.environ.get("CF_ACCOUNTS", "")
        if json_blob:
            try:
                parsed = json.loads(json_blob)
                if isinstance(parsed, list):
                    for i, a in enumerate(parsed):
                        if a.get("token") and a.get("account_id"):
                            found.append({
                                "name": a.get("name", f"json_{i+1}"),
                                "owner": a.get("owner", f"owner_{i+1}"),
                                "token": a["token"],
                                "account_id": a["account_id"],
                            })
            except Exception as e:
                logger.warning(f"[CF-Multi] CF_ACCOUNTS parse: {e}")

        # Deduplicate by account_id
        seen = set()
        unique = []
        for a in found:
            aid = a["account_id"]
            if aid in seen:
                continue
            seen.add(aid)
            unique.append(a)

        logger.info(f"[CF-Multi] Discovered {len(unique)} account(s)")
        return unique

    def sync_accounts(self) -> Dict[str, int]:
        """Sync discovered accounts to DB."""
        discovered = self.discover_accounts()
        added = 0

        for a in discovered:
            try:
                with get_conn() as conn:
                    existing = conn.execute(
                        "SELECT id FROM cf_accounts WHERE account_id = ?",
                        (a["account_id"],)
                    ).fetchone()
                    if not existing:
                        conn.execute(
                            "INSERT INTO cf_accounts "
                            "(account_id, token, name, owner, status, created_at) "
                            "VALUES (?, ?, ?, ?, 'active', ?)",
                            (a["account_id"], a["token"], a["name"],
                             a["owner"], time.time())
                        )
                        added += 1
                    else:
                        # Update token (may have changed)
                        conn.execute(
                            "UPDATE cf_accounts SET token = ?, status = 'active' "
                            "WHERE account_id = ?",
                            (a["token"], a["account_id"])
                        )
                conn.commit()
            except Exception as e:
                logger.warning(f"[CF-Multi] sync {a['name']}: {e}")

        with self._lock:
            self.accounts = discovered

        logger.info(f"[CF-Multi] Synced {len(discovered)} accounts (+{added} new)")
        return {"total": len(discovered), "added": added}

    # ------------------------------------------------------------
    # Verify accounts
    # ------------------------------------------------------------
    def verify_all(self) -> Dict[str, Any]:
        """Verify all accounts with Cloudflare API."""
        try:
            from cloudflare_deployer import verify_token
        except Exception as e:
            return {"error": str(e)}

        results = []
        for a in self.accounts:
            v = verify_token(a["token"])
            results.append({
                "name": a["name"],
                "account_id": a["account_id"][:8] + "...",
                "verified": v.get("ok", False),
                "status": v.get("status", "unknown"),
            })
        return {"accounts": results, "total": len(results)}

    # ------------------------------------------------------------
    # Deploy across all accounts
    # ------------------------------------------------------------
    def deploy_all(self, workers_per_account: int = None,
                   dry_run: bool = False) -> Dict[str, Any]:
        """Deploy N workers per account."""
        try:
            from cloudflare_deployer import deploy_worker
        except Exception as e:
            return {"error": str(e)}

        n = workers_per_account or self.WORKERS_PER_ACCOUNT
        results = []

        for a in self.accounts:
            account_results = []
            for i in range(n):
                worker_name = f"marsad-agent-{i+1}"
                r = deploy_worker(
                    token=a["token"],
                    account_id=a["account_id"],
                    worker_name=worker_name,
                    dry_run=dry_run,
                )
                account_results.append({
                    "worker": worker_name,
                    "status": r.get("status"),
                })
                if not r.get("ok"):
                    break
                time.sleep(0.3)  # rate limit

            # Update DB
            try:
                with get_conn() as conn:
                    conn.execute(
                        "UPDATE cf_accounts SET workers_count = ?, "
                        "agents_capacity = ?, last_check = ? "
                        "WHERE account_id = ?",
                        (len(account_results),
                         len(account_results) * self.AGENTS_PER_WORKER,
                         time.time(), a["account_id"])
                    )
                conn.commit()
            except Exception:
                pass

            results.append({
                "account": a["name"],
                "workers_deployed": len(account_results),
                "agents_capacity": len(account_results) * self.AGENTS_PER_WORKER,
                "details": account_results[:3],  # sample
            })

        total_workers = sum(r["workers_deployed"] for r in results)
        total_agents = sum(r["agents_capacity"] for r in results)

        log_event("cf_multi", {
            "action": "deploy_all",
            "accounts": len(self.accounts),
            "workers": total_workers,
            "agents": total_agents,
        })

        return {
            "accounts": len(self.accounts),
            "total_workers": total_workers,
            "total_agents": total_agents,
            "results": results,
        }

    # ------------------------------------------------------------
    # Auto deploy loop
    # ------------------------------------------------------------
    def start(self):
        if self.running:
            return
        self.running = True
        self._stop.clear()
        self.sync_accounts()  # discover on start
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info("[CF-Multi] Started")

    def stop(self):
        self.running = False
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _loop(self):
        # Initial deploy after startup
        time.sleep(30)
        try:
            self.deploy_all(dry_run=False)
        except Exception as e:
            logger.error(f"[CF-Multi] initial deploy: {e}")

        while not self._stop.is_set():
            self._stop.wait(600)  # every 10 minutes
            try:
                self.sync_accounts()
            except Exception as e:
                logger.error(f"[CF-Multi] resync: {e}")

    # ------------------------------------------------------------
    # Status
    # ------------------------------------------------------------
    def status(self) -> Dict[str, Any]:
        try:
            with get_conn() as conn:
                rows = conn.execute(
                    "SELECT account_id, name, owner, workers_count, "
                    "agents_capacity, status FROM cf_accounts"
                ).fetchall()
                accounts = [dict(r) for r in rows]
        except Exception:
            accounts = []

        total_workers = sum(a.get("workers_count", 0) for a in accounts)
        total_agents = sum(a.get("agents_capacity", 0) for a in accounts)

        return {
            "running": self.running,
            "accounts_discovered": len(self.accounts),
            "accounts_in_db": len(accounts),
            "total_workers": total_workers,
            "total_agents": total_agents,
            "accounts": [
                {
                    "name": a["name"],
                    "owner": a.get("owner"),
                    "account_id_preview": a["account_id"][:8] + "...",
                    "workers": a.get("workers_count", 0),
                    "agents": a.get("agents_capacity", 0),
                    "status": a.get("status"),
                }
                for a in accounts
            ],
        }


# Singleton
multi_account_manager = MultiAccountManager()
