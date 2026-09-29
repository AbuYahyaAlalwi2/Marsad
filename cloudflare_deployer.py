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
    """يتحقق من التوكن عبر account endpoint (يدعم Account-scoped tokens)."""
    if not token:
        return {"valid": False, "output": "no token"}

    # 1) لو عندنا account_id → افحص /accounts/{id}
    if account_id:
        try:
            r = requests.get(
                f"https://api.cloudflare.com/client/v4/accounts/{account_id}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=15)
            if r.status_code == 200:
                data = r.json()
                return {"valid": True, "account": data.get("result", {}).get("name", ""),
                        "output": "account-scoped token ok"}
            # فشل → جرّب user
        except Exception as e:
            pass

    # 2) جرّب user endpoint (للـ User tokens)
    try:
        r = requests.get(
            "https://api.cloudflare.com/client/v4/user/tokens/verify",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15)
        if r.status_code == 200 and r.json().get("success"):
            return {"valid": True, "output": "user token ok"}
        err = r.json().get("errors", [{}])
        msg = err[0].get("message", "") if err else f"HTTP {r.status_code}"
        return {"valid": False, "output": msg[:200]}
    except Exception as e:
        return {"valid": False, "output": str(e)[:200]}



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
    Register a workers.dev subdomain for the account.
    Required before deploying any Worker.
    Uses PUT /accounts/{account_id}/workers/subdomain with JSON body.
    """
    if dry_run:
        return {"ok": True, "status": "dry_run", "output": "[DRY] subdomain check"}

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    import hashlib
    sub_name = "marsad-" + hashlib.md5(account_id.encode()).hexdigest()[:10]
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/workers/subdomain"

    # 1. Check if subdomain already exists
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json()
            existing = data.get("result", {}).get("subdomain", "")
            if existing:
                return {"ok": True, "status": "exists",
                        "output": f"Subdomain '{existing}.workers.dev' already registered"}
    except Exception:
        pass

    # 2. Register new subdomain via PUT
    try:
        r = requests.put(url, headers=headers, json={"subdomain": sub_name}, timeout=30)
        if r.status_code in (200, 201):
            return {"ok": True, "status": "success",
                    "output": f"Subdomain '{sub_name}.workers.dev' registered"}
        try:
            err = r.json()
            errors = err.get("errors", [])
            msg = "; ".join(f"{e.get('code')}: {e.get('message')}" for e in errors)
        except Exception:
            msg = r.text[:200]
        return {"ok": False, "status": f"http_{r.status_code}", "output": msg}
    except Exception as e:
        return {"ok": False, "status": "error", "output": str(e)}




def force_subdomain_via_dummy(token: str, account_id: str, dry_run: bool = False) -> Dict[str, Any]:
    """
    Official workaround: create a dummy worker, then delete it.
    Cloudflare allocates a subdomain automatically after this.
    """
    if dry_run:
        return {"ok": True, "status": "dry_run", "output": "[DRY] dummy worker"}

    headers = {"Authorization": f"Bearer {token}"}
    dummy_name = "marsad-dummy-init"
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/workers/scripts/{dummy_name}"

    # 1. Create dummy worker
    try:
        r = requests.put(
            url,
            headers=headers,
            files={
                "metadata": (None, json.dumps({"main_module": "worker.js", "compatibility_date": "2024-01-01"}), "application/json"),
                "worker.js": ("worker.js", "export default { fetch() { return new Response('OK'); } }", "application/javascript+module"),
            },
            timeout=30,
        )
        if r.status_code not in (200, 201):
            return {"ok": False, "status": f"create_{r.status_code}", "output": r.text[:200]}
    except Exception as e:
        return {"ok": False, "status": "create_error", "output": str(e)}

    # 2. Delete dummy worker
    try:
        requests.delete(url, headers=headers, timeout=15)
    except Exception:
        pass

    # 3. Check if subdomain was created
    import time as _t
    _t.sleep(2)
    sub_url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/workers/subdomain"
    try:
        r = requests.get(sub_url, headers=headers, timeout=15)
        data = r.json()
        subdomain = (data.get("result") or {}).get("subdomain", "NOT_SET")
        if subdomain != "NOT_SET":
            return {"ok": True, "status": "success", "output": f"Subdomain created: {subdomain}"}
        return {"ok": False, "status": "subdomain_still_missing", "output": "Subdomain not created yet"}
    except Exception as e:
        return {"ok": False, "status": "check_error", "output": str(e)}


def deploy_worker(token: str, account_id: str, worker_name: str,
                  dry_run: bool = False) -> Dict[str, Any]:
    """
    Deploy a worker script with proper multipart metadata.
    """
    if dry_run:
        return {"ok": True, "status": "dry_run",
                "output": f"[DRY] deploy {worker_name}"}
    if not token or not account_id:
        return {"ok": False, "status": "no_credentials", "output": ""}

    # Ensure subdomain exists first
    sub = ensure_subdomain(token, account_id, dry_run=False)
    if not sub.get("ok"):
        return {"ok": False, "status": sub.get("status", "subdomain_failed"),
                "output": f"Subdomain setup failed: {sub.get('output', '')}"}

    url = (f"https://api.cloudflare.com/client/v4/accounts/"
           f"{account_id}/workers/scripts/{worker_name}")

    headers = {"Authorization": f"Bearer {token}"}

    # Metadata part (JSON) - REQUIRED
    metadata = {
        "main_module": "worker.js",
        "compatibility_date": "2025-08-25",
        "compatibility_flags": ["global_fetch_strictly_public"],
    }

    # Multipart with correct content-type for ES module
    files = {
        "metadata": (None, json.dumps(metadata), "application/json"),
        "worker.js": ("worker.js", WORKER_SCRIPT, "application/javascript+module"),
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

        # Special handling for subdomain_required error
        if "10063" in error_msg or "subdomain" in error_msg.lower():
            return {"ok": False, "status": "subdomain_required",
                    "output": ("يجب تسجيل workers.dev subdomain يدوياً: "
                               "افتح dash.cloudflare.com → Workers & Pages → "
                               "Register a workers.dev subdomain")}

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
