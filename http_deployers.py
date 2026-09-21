"""
CYBERGUARD OS - HTTP API Deployers
Deploy to clouds via HTTP APIs (no CLI needed).
Works from anywhere: Render, Termux, Docker, etc.
"""
import logging
import requests
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def _dry(fn_output: str) -> Dict:
    return {"ok": True, "status": "dry_run", "output": f"[DRY] {fn_output}"}


# ============================================================
# Railway (GraphQL API)
# ============================================================
def deploy_railway(token: str, service_name: str, count: int, dry_run: bool = False) -> Dict:
    if dry_run:
        return _dry(f"railway scale {service_name} -> {count}")
    if not token:
        return {"ok": False, "status": "no_token", "output": ""}

    url = "https://backboard.railway.app/graphql/v2"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    # 1. Get projects + services + environments
    query = """
    query {
      me {
        projects {
          edges {
            node {
              id
              name
              services { edges { node { id name } } }
              environments { edges { node { id name } } }
            }
          }
        }
      }
    }
    """
    try:
        r = requests.post(url, headers=headers, json={"query": query}, timeout=30)
        if r.status_code != 200:
            return {"ok": False, "status": f"http_{r.status_code}",
                    "output": r.text[:500]}
        data = r.json()
        if "errors" in data:
            return {"ok": False, "status": "graphql_error",
                    "output": str(data["errors"])[:500]}

        projects = data.get("data", {}).get("me", {}).get("projects", {}).get("edges", [])
        if not projects:
            return {"ok": False, "status": "no_projects", "output": ""}

        # 2. Find the target service
        found = None
        for edge in projects:
            proj = edge["node"]
            services = proj.get("services", {}).get("edges", [])
            envs = proj.get("environments", {}).get("edges", [])
            for s in services:
                if s["node"]["name"] == service_name:
                    found = {
                        "project_id": proj["id"],
                        "service_id": s["node"]["id"],
                        "environment_id": envs[0]["node"]["id"] if envs else None,
                    }
                    break
            if found:
                break

        if not found or not found["environment_id"]:
            return {"ok": False, "status": "service_not_found",
                    "output": f"Service '{service_name}' not found in Railway"}

        # 3. Scale replicas
        mutation = """
        mutation serviceInstanceUpdate($serviceId: String!, $environmentId: String!, $input: ServiceInstanceUpdateInput!) {
          serviceInstanceUpdate(serviceId: $serviceId, environmentId: $environmentId, input: $input)
        }
        """
        variables = {
            "serviceId": found["service_id"],
            "environmentId": found["environment_id"],
            "input": {"numReplicas": count},
        }
        r = requests.post(
            url, headers=headers,
            json={"query": mutation, "variables": variables},
            timeout=30,
        )
        if r.status_code != 200:
            return {"ok": False, "status": f"http_{r.status_code}",
                    "output": r.text[:500]}
        data = r.json()
        if "errors" in data:
            return {"ok": False, "status": "graphql_error",
                    "output": str(data["errors"])[:500]}

        return {
            "ok": True,
            "status": "success",
            "output": f"Railway '{service_name}' scaled to {count}",
        }
    except Exception as e:
        return {"ok": False, "status": "error", "output": str(e)}


# ============================================================
# Koyeb (REST API)
# ============================================================
def deploy_koyeb(token: str, service_name: str, count: int, dry_run: bool = False) -> Dict:
    if dry_run:
        return _dry(f"koyeb scale {service_name} -> {count}")
    if not token:
        return {"ok": False, "status": "no_token", "output": ""}

    url = "https://app.koyeb.com/v1/services"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    try:
        # 1. Find service
        r = requests.get(url, headers=headers, timeout=30)
        if r.status_code != 200:
            return {"ok": False, "status": f"http_{r.status_code}",
                    "output": r.text[:500]}
        data = r.json()
        services = data.get("services", [])
        target = None
        for s in services:
            if s.get("name") == service_name:
                target = s
                break
        if not target:
            return {"ok": False, "status": "service_not_found",
                    "output": f"Service '{service_name}' not in Koyeb"}

        # 2. Scale
        update_url = f"https://app.koyeb.com/v1/services/{target['id']}"
        payload = {
            "definition": {
                "scaling": {
                    "min": count,
                    "max": count,
                }
            }
        }
        r = requests.put(update_url, headers=headers, json=payload, timeout=30)
        if r.status_code not in (200, 201, 202):
            return {"ok": False, "status": f"http_{r.status_code}",
                    "output": r.text[:500]}
        return {"ok": True, "status": "success",
                "output": f"Koyeb '{service_name}' scaled to {count}"}
    except Exception as e:
        return {"ok": False, "status": "error", "output": str(e)}


# ============================================================
# Fly.io (Machines API)
# ============================================================
def deploy_fly(token: str, app_name: str, count: int, dry_run: bool = False) -> Dict:
    if dry_run:
        return _dry(f"fly scale {app_name} -> {count}")
    if not token:
        return {"ok": False, "status": "no_token", "output": ""}

    url = f"https://api.machines.dev/v1/apps/{app_name}/machines"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    try:
        r = requests.get(url, headers=headers, timeout=30)
        if r.status_code != 200:
            return {"ok": False, "status": f"http_{r.status_code}",
                    "output": r.text[:500]}
        machines = r.json()
        current = len(machines) if isinstance(machines, list) else 0

        diff = count - current
        if diff > 0:
            # Create more machines
            created = 0
            for _ in range(diff):
                cr = requests.post(
                    url, headers=headers,
                    json={"config": {"image": "cyberguard/worker:latest"}},
                    timeout=30,
                )
                if cr.status_code in (200, 201):
                    created += 1
            return {"ok": True, "status": "success",
                    "output": f"Fly created {created} machines (total {current + created})"}
        elif diff < 0:
            # Destroy some
            destroyed = 0
            for m in machines[:abs(diff)]:
                dr = requests.delete(
                    f"{url}/{m['id']}", headers=headers, timeout=30
                )
                if dr.status_code in (200, 204):
                    destroyed += 1
            return {"ok": True, "status": "success",
                    "output": f"Fly destroyed {destroyed} machines"}
        return {"ok": True, "status": "success", "output": f"Fly already at {count}"}
    except Exception as e:
        return {"ok": False, "status": "error", "output": str(e)}


# ============================================================
# Render (REST API)
# ============================================================
def deploy_render(token: str, service_id: str, count: int, dry_run: bool = False) -> Dict:
    if dry_run:
        return _dry(f"render scale {service_id} -> {count}")
    if not token:
        return {"ok": False, "status": "no_token", "output": ""}

    url = f"https://api.render.com/v1/services/{service_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    try:
        r = requests.patch(
            url, headers=headers,
            json={"numInstances": count},
            timeout=30,
        )
        if r.status_code in (200, 202):
            return {"ok": True, "status": "success",
                    "output": f"Render scaled to {count}"}
        return {"ok": False, "status": f"http_{r.status_code}",
                "output": r.text[:500]}
    except Exception as e:
        return {"ok": False, "status": "error", "output": str(e)}


# ============================================================
# Router
# ============================================================
def deploy(provider: str, token: str, name: str, count: int,
          dry_run: bool = False) -> Dict:
    """Route to correct deployer."""
    if provider == "railway":
        return deploy_railway(token, name, count, dry_run)
    if provider == "koyeb":
        return deploy_koyeb(token, name, count, dry_run)
    if provider == "fly":
        return deploy_fly(token, name, count, dry_run)
    if provider == "render":
        return deploy_render(token, name, count, dry_run)
    return {"ok": False, "status": "unknown_provider", "output": ""}
