"""
CYBERGUARD OS - Cloudflare Deployer
Deploys Workers to Cloudflare via API (no CLI).
Supports N accounts.
"""
import os
import json
import time
import logging
import requests
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


WORKER_SCRIPT = r'''
// Marsad Worker - Cloudflare Edge Agent
// Handles agent heartbeats and task dispatch
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname;

    if (path === "/status") {
      return new Response(JSON.stringify({
        status: "ok",
        worker: "marsad",
        ts: Date.now(),
        region: request.cf?.colo || "unknown",
      }), { headers: { "content-type": "application/json" } });
    }

    if (path === "/heartbeat") {
      return new Response(JSON.stringify({
        ok: true,
        ts: Date.now(),
      }), { headers: { "content-type": "application/json" } });
    }

    if (path === "/task") {
      return new Response(JSON.stringify({
        task: null,
        message: "no_tasks_available",
      }), { headers: { "content-type": "application/json" } });
    }

    return new Response("Marsad Worker Active", { status: 200 });
  }
}
'''


def verify_token(token: str, account_id: str = None) -> Dict[str, Any]:
    """
    Verify Cloudflare API token.
    Tries BOTH user-owned AND account-owned endpoints.
    """
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Try user-owned endpoint first
    try:
        r = requests.get(
            "https://api.cloudflare.com/client/v4/user/tokens/verify",
            headers=headers, timeout=10,
        )
        data = r.json()
        if data.get("success") and data.get("result", {}).get("status") == "active":
            return {
                "ok": True,
                "status": "active",
                "type": "user_owned",
            }
    except Exception:
        pass

    # 2. Try account-owned endpoint (requires account_id)
    if account_id:
        try:
            r = requests.get(
                f"https://api.cloudflare.com/client/v4/accounts/{account_id}/tokens/verify",
                headers=headers, timeout=10,
            )
            data = r.json()
            if data.get("success"):
                return {
                    "ok": True,
                    "status": "active",
                    "type": "account_owned",
                }
        except Exception:
            pass

    return {"ok": False, "status": "unknown", "type": "invalid"}


def list_accounts(token: str) -> Dict[str, Any]:
    """List all accounts associated with token."""
    try:
        r = requests.get(
            "https://api.cloudflare.com/client/v4/accounts",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        if r.status_code != 200:
            return {"ok": False, "error": f"http_{r.status_code}"}
        data = r.json()
        return {
            "ok": True,
            "accounts": data.get("result", []),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def list_workers(token: str, account_id: str) -> Dict[str, Any]:
    """List all workers in an account."""
    try:
        r = requests.get(
            f"https://api.cloudflare.com/client/v4/accounts/{account_id}/workers/scripts",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        if r.status_code != 200:
            return {"ok": False, "error": f"http_{r.status_code}", "workers": []}
        data = r.json()
        workers = [w.get("id") for w in data.get("result", [])]
        return {"ok": True, "workers": workers, "count": len(workers)}
    except Exception as e:
        return {"ok": False, "error": str(e), "workers": []}




def ensure_subdomain(token: str, account_id: str, dry_run: bool = False) -> Dict[str, Any]:
    """
    Register a workers.dev subdomain for the account (required before deploying).
    Uses PUT /accounts/{account_id}/workers/subdomain
    """
    if dry_run:
        return {"ok": True, "status": "dry_run", "output": "[DRY] subdomain check"}

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    # Generate a unique subdomain name
    import hashlib
    sub_name = "marsad-" + hashlib.md5(account_id.encode()).hexdigest()[:8]

    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/workers/subdomain"
    try:
        r = requests.put(url, headers=headers, json={"subdomain": sub_name}, timeout=30)
        if r.status_code in (200, 201):
            return {"ok": True, "status": "success",
                    "output": f"Subdomain '{sub_name}.workers.dev' ready"}
        # If already exists, try GET to confirm
        r2 = requests.get(url, headers=headers, timeout=15)
        if r2.status_code == 200:
            return {"ok": True, "status": "exists",
                    "output": "Subdomain already registered"}
        # Return detailed error
        try:
            err = r.json()
            msg = "; ".join(e.get("message", "") for e in err.get("errors", []))
        except Exception:
            msg = r.text[:200]
        return {"ok": False, "status": f"http_{r.status_code}", "output": msg}
    except Exception as e:
        return {"ok": False, "status": "error", "output": str(e)}


def deploy_worker(token: str, account_id: str, worker_name: str,
                  dry_run: bool = False) -> Dict[str, Any]:
    """
    Deploy a worker script.
    Automatically ensures the workers.dev subdomain is registered first.
    """
    # Ensure subdomain is set up before deploying
    sub = ensure_subdomain(token, account_id, dry_run=dry_run)
    if not sub.get("ok") and sub.get("status") not in ("exists", "dry_run"):
        return {"ok": False, "status": sub.get("status", "subdomain_failed"),
                "output": f"Subdomain setup failed: {sub.get('output', '')}"}

    # Now deploy the actual worker
    if not token or not account_id:
        return {"ok": False, "status": "no_credentials", "output": ""}

    url = (f"https://api.cloudflare.com/client/v4/accounts/"
           f"{account_id}/workers/scripts/{worker_name}")
    headers = {"Authorization": f"Bearer {token}"}
    metadata = {
        "main_module": "worker.js",
        "compatibility_date": "2024-01-01",
    }
    files = {
        "metadata": (None, __import__("json").dumps(metadata), "application/json"),
        "worker.js": ("worker.js", WORKER_SCRIPT, "application/javascript"),
    }

    try:
        r = requests.put(url, headers=headers, files=files, timeout=60)
        if r.status_code in (200, 201):
            return {"ok": True, "status": "success",
                    "output": f"Worker '{worker_name}' deployed to {account_id[:8]}..."}

        # Extract detailed error
        try:
            error_data = r.json()
            errors = error_data.get("errors", [])
            error_msg = "; ".join(
                f"{e.get('code', '?')}: {e.get('message', '?')}"
                for e in errors
            ) if errors else r.text[:300]
        except Exception:
            error_msg = r.text[:300]

        return {"ok": False, "status": f"http_{r.status_code}",
                "output": error_msg}
    except Exception as e:
        return {"ok": False, "status": "error", "output": str(e)}


def delete_worker(token: str, account_id: str, worker_name: str) -> Dict[str, Any]:
    """Delete a worker script."""
    try:
        r = requests.delete(
            f"https://api.cloudflare.com/client/v4/accounts/{account_id}/workers/scripts/{worker_name}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        return {"ok": r.status_code in (200, 204), "status": f"http_{r.status_code}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}
