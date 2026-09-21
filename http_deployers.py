"""
CYBERGUARD OS - HTTP API Deployers
Deploy to clouds via HTTP APIs (no CLI needed).
"""
import logging
import requests
from typing import Dict

logger = logging.getLogger(__name__)


def _dry(msg: str) -> Dict:
    return {"ok": True, "status": "dry_run", "output": f"[DRY] {msg}"}


# ============================================================
# Railway (GraphQL API) - multi-shape query
# ============================================================
RAILWAY_QUERIES = [
    """
    query {
      me {
        workspaces {
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
    }
    """,
    """
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
    """,
    """
    query {
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
    """,
]


def _extract_projects(d: dict):
    """Extract project edges from any query shape."""
    projects = []
    me = (d.get("data") or {}).get("me") or {}

    ws = me.get("workspaces") or []
    if isinstance(ws, list):
        for w in ws:
            edges = ((w or {}).get("projects") or {}).get("edges") or []
            projects.extend(edges)

    if not projects:
        edges = (me.get("projects") or {}).get("edges") or []
        projects.extend(edges)

    if not projects:
        edges = ((d.get("data") or {}).get("projects") or {}).get("edges") or []
        projects.extend(edges)

    return projects


def deploy_railway(token: str, service_name: str, count: int,
                   dry_run: bool = False) -> Dict:
    if dry_run:
        return _dry(f"railway {service_name} -> {count}")
    if not token:
        return {"ok": False, "status": "no_token", "output": ""}

    url = "https://backboard.railway.app/graphql/v2"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    # 1. Try every query shape until one returns projects
    projects = []
    last_error = ""
    for q in RAILWAY_QUERIES:
        try:
            r = requests.post(url, headers=headers,
                              json={"query": q}, timeout=30)
            if r.status_code != 200:
                last_error = f"http_{r.status_code}: {r.text[:200]}"
                continue
            data = r.json()
            if "errors" in data:
                last_error = str(data["errors"])[:200]
                continue
            projects = _extract_projects(data)
            if projects:
                break
        except Exception as e:
            last_error = str(e)
            continue

    if not projects:
        return {"ok": False, "status": "no_projects",
                "output": f"No projects found. Last error: {last_error}"}

    # 2. Find target service (or fallback)
    found = None
    fallback = None
    for edge in projects:
        proj = edge.get("node") or {}
        services = (proj.get("services") or {}).get("edges") or []
        envs = (proj.get("environments") or {}).get("edges") or []
        env_id = (envs[0].get("node") or {}).get("id") if envs else None

        for s in services:
            node = s.get("node") or {}
            svc = {
                "project_name": proj.get("name", ""),
                "service_id": node.get("id"),
                "service_name": node.get("name"),
                "environment_id": env_id,
            }
            if node.get("name") == service_name:
                found = svc
                break
            if proj.get("name") == service_name and fallback is None:
                fallback = svc
            if fallback is None:
                fallback = svc
        if found:
            break

    if not found:
        found = fallback

    if not found or not found.get("environment_id"):
        return {"ok": False, "status": "service_not_found",
                "output": "No services found. Create a service in Railway first."}

    # 3. Scale
    mutation = """
    mutation serviceInstanceUpdate(
      $serviceId: String!,
      $environmentId: String!,
      $input: ServiceInstanceUpdateInput!
    ) {
      serviceInstanceUpdate(
        serviceId: $serviceId,
        environmentId: $environmentId,
        input: $input
      )
    }
    """
    variables = {
        "serviceId": found["service_id"],
        "environmentId": found["environment_id"],
        "input": {"numReplicas": count},
    }
    try:
        r = requests.post(url, headers=headers,
                          json={"query": mutation, "variables": variables},
                          timeout=30)
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
            "output": f"Railway '{found['service_name']}' scaled to {count}",
        }
    except Exception as e:
        return {"ok": False, "status": "error", "output": str(e)}


# ============================================================
# Koyeb (REST API)
# ============================================================
def deploy_koyeb(token: str, service_name: str, count: int,
                 dry_run: bool = False) -> Dict:
    if dry_run:
        return _dry(f"koyeb {service_name} -> {count}")
    if not token:
        return {"ok": False, "status": "no_token", "output": ""}

    url = "https://app.koyeb.com/v1/services"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    try:
        r = requests.get(url, headers=headers, timeout=30)
        if r.status_code != 200:
            return {"ok": False, "status": f"http_{r.status_code}",
                    "output": r.text[:500]}
        services = (r.json() or {}).get("services", []) or []
        target = None
        for s in services:
            if s.get("name") == service_name:
                target = s
                break
        if not target and services:
            target = services[0]  # fallback
        if not target:
            return {"ok": False, "status": "service_not_found",
                    "output": f"No services in Koyeb"}

        update_url = f"https://app.koyeb.com/v1/services/{target['id']}"
        payload = {"definition": {"scaling": {"min": count, "max": count}}}
        r = requests.put(update_url, headers=headers, json=payload, timeout=30)
        if r.status_code not in (200, 201, 202):
            return {"ok": False, "status": f"http_{r.status_code}",
                    "output": r.text[:500]}
        return {"ok": True, "status": "success",
                "output": f"Koyeb '{target.get('name')}' scaled to {count}"}
    except Exception as e:
        return {"ok": False, "status": "error", "output": str(e)}


# ============================================================
# Fly.io (Machines API)
# ============================================================
def deploy_fly(token: str, app_name: str, count: int,
               dry_run: bool = False) -> Dict:
    if dry_run:
        return _dry(f"fly {app_name} -> {count}")
    if not token:
        return {"ok": False, "status": "no_token", "output": ""}

    url = f"https://api.machines.dev/v1/apps/{app_name}/machines"
    headers = {"Authorization": f"Bearer {token}",
               "Content-Type": "application/json"}
    try:
        r = requests.get(url, headers=headers, timeout=30)
        if r.status_code != 200:
            return {"ok": False, "status": f"http_{r.status_code}",
                    "output": r.text[:500]}
        machines = r.json()
        current = len(machines) if isinstance(machines, list) else 0
        diff = count - current

        if diff > 0:
            created = 0
            for _ in range(diff):
                cr = requests.post(
                    url, headers=headers,
                    json={"config": {"image": "cyberguard/worker:latest"}},
                    timeout=30)
                if cr.status_code in (200, 201):
                    created += 1
            return {"ok": True, "status": "success",
                    "output": f"Fly +{created} machines (total {current + created})"}
        if diff < 0:
            destroyed = 0
            for m in machines[:abs(diff)]:
                dr = requests.delete(f"{url}/{m['id']}",
                                     headers=headers, timeout=30)
                if dr.status_code in (200, 204):
                    destroyed += 1
            return {"ok": True, "status": "success",
                    "output": f"Fly -{destroyed} machines"}
        return {"ok": True, "status": "success",
                "output": f"Fly already at {count}"}
    except Exception as e:
        return {"ok": False, "status": "error", "output": str(e)}


# ============================================================
# Render (REST API)
# ============================================================
def deploy_render(token: str, service_id: str, count: int,
                  dry_run: bool = False) -> Dict:
    if dry_run:
        return _dry(f"render {service_id} -> {count}")
    if not token:
        return {"ok": False, "status": "no_token", "output": ""}

    url = f"https://api.render.com/v1/services/{service_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    try:
        r = requests.patch(url, headers=headers,
                           json={"numInstances": count}, timeout=30)
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
    if provider == "railway":
        return deploy_railway(token, name, count, dry_run)
    if provider == "koyeb":
        return deploy_koyeb(token, name, count, dry_run)
    if provider == "fly":
        return deploy_fly(token, name, count, dry_run)
    if provider == "render":
        return deploy_render(token, name, count, dry_run)
    return {"ok": False, "status": "unknown_provider", "output": ""}
