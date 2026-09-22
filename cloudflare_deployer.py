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


def verify_token(token: str) -> Dict[str, Any]:
    """Verify Cloudflare API token."""
    try:
        r = requests.get(
            "https://api.cloudflare.com/client/v4/user/tokens/verify",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        data = r.json()
        return {
            "ok": data.get("success", False),
            "status": data.get("result", {}).get("status"),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


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


def deploy_worker(token: str, account_id: str, worker_name: str,
                  dry_run: bool = False) -> Dict[str, Any]:
    """Deploy a worker script."""
    if dry_run:
        return {"ok": True, "status": "dry_run",
                "output": f"[DRY] deploy {worker_name} on {account_id[:8]}..."}
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
        "metadata": (None, json.dumps(metadata), "application/json"),
        "worker.js": ("worker.js", WORKER_SCRIPT, "application/javascript"),
    }

    try:
        r = requests.put(url, headers=headers, files=files, timeout=60)
        if r.status_code in (200, 201):
            return {"ok": True, "status": "success",
                    "output": f"Worker '{worker_name}' deployed to {account_id[:8]}..."}
        return {"ok": False, "status": f"http_{r.status_code}",
                "output": r.text[:300]}
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
