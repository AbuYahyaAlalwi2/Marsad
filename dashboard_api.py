"""
CYBERGUARD OS - MARSAD Dashboard API
Flask server for the dashboard.
Run: python3 dashboard_api.py
"""
import os
import json
import time
import webbrowser
import threading
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS

# --- Paths ---
BASE = Path(__file__).resolve().parent
os.chdir(BASE)

# --- App ---
app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app)

# --- DB init ---
try:
    from db import (_ensure_db, get_database_stats, get_recent_events,
                count_agents_by_level, get_recent_tasks, get_task_stats,
                list_sources, get_today_metrics)
    _ensure_db()
    HAS_DB = True
except Exception as e:
    print(f"[Dashboard] DB unavailable: {e}")
    HAS_DB = False
    def get_database_stats(): return {}
    def get_recent_events(n=20): return []
    def count_agents_by_level(l): return 0


def get_cp_status():
    try:
        from control_plane import control_plane
        return control_plane.status()
    except Exception:
        return {}


_psutil_primed = False


def _prime_psutil():
    """First call always returns 0 - call once at startup to warm up."""
    global _psutil_primed
    if _psutil_primed:
        return
    try:
        import psutil
        psutil.cpu_percent(interval=None)  # warm-up
        psutil.cpu_percent(interval=0.05)
    except Exception:
        pass
    _psutil_primed = True


def safe_status():
    """Full dashboard status."""
    _prime_psutil()

    cp = get_cp_status()
    db = {}
    try:
        db = get_database_stats()
    except Exception:
        pass

    # CPU / RAM / DISK (Termux-friendly)
    metrics = {"cpu": 0, "ram": 0, "disk": 0, "net": 0}
    try:
        import psutil as _ps
        import os as _os

        # RAM
        try:
            metrics["ram"] = round(_ps.virtual_memory().percent, 1)
        except Exception:
            pass

        # Disk (Termux home, not /)
        try:
            home = _os.path.expanduser("~")
            metrics["disk"] = round(_ps.disk_usage(home).percent, 1)
        except Exception:
            try:
                metrics["disk"] = round(_ps.disk_usage("/data/data/com.termux/files/home").percent, 1)
            except Exception:
                pass

        # CPU from load average / cpu count
        try:
            la = _os.getloadavg()[0]
            ncpu = _os.cpu_count() or 1
            pct = (la / ncpu) * 100.0
            metrics["cpu"] = round(min(100.0, pct), 1)
        except Exception:
            pass

        # Network (best-effort)
        try:
            n1 = _ps.net_io_counters()
            import time as _t
            _t.sleep(0.1)
            n2 = _ps.net_io_counters()
            delta = (n2.bytes_sent - n1.bytes_sent) + (n2.bytes_recv - n1.bytes_recv)
            metrics["net"] = min(100.0, round(delta / 102.4, 1))
        except Exception:
            metrics["net"] = 0
    except Exception as e:
        print(f"[status] metrics error: {e}")

    # Agents per level
    agents = {"total": 0, "level_1": 0, "level_2": 0, "level_3": 0, "level_4": 0, "level_5": 0}
    try:
        for i in range(5):
            c = count_agents_by_level(i)
            if i == 0:
                agents["level_1"] = c
            elif i == 1:
                agents["level_2"] = c
            elif i == 2:
                agents["level_3"] = c
            elif i == 3:
                agents["level_4"] = c
            elif i == 4:
                agents["level_5"] = c
            agents["total"] += c
    except Exception:
        pass

    # Real task stats
    task_stats = {"total": 0, "completed": 0, "failed": 0, "running": 0, "success_rate": 0.0}
    try:
        task_stats = get_task_stats()
    except Exception:
        pass

    # Real sources count
    sources_count = 0
    try:
        sources_count = len(list_sources())
    except Exception:
        pass

    # Storage: DB + data dir + merged models
    storage_bytes = 0
    try:
        import os as _os
        total = 0
        for sub in ("data", "models", "datasets"):
            root = str(BASE / sub)
            if not _os.path.isdir(root):
                continue
            for dirpath, _, filenames in _os.walk(root):
                for fn in filenames:
                    try:
                        total += _os.path.getsize(_os.path.join(dirpath, fn))
                    except Exception:
                        pass
        # DB itself
        try:
            from config import DB_PATH
            if _os.path.isfile(DB_PATH):
                total += _os.path.getsize(DB_PATH)
        except Exception:
            pass
        storage_bytes = total
    except Exception:
        pass

    # Today's metrics
    today_metrics = {}
    try:
        today_metrics = get_today_metrics()
    except Exception:
        pass

    # Real cloud counts (DB + fallback to in-memory unifier)
    cloud_stats = {"active": 0, "available": 0, "total": 0, "weak": 0}
    try:
        from cloud_unifier import count_registered_providers, cloud_unifier
        db_counts = count_registered_providers()
        cloud_stats.update(db_counts)
        # Fallback: if DB empty, use in-memory count
        if cloud_stats["total"] == 0:
            mem = cloud_unifier.count()
            cloud_stats["total"] = mem.get("total", 0)
            cloud_stats["active"] = mem.get("with_account", 0)
            cloud_stats["available"] = mem.get("free", 0)
        from cloud_health import cloud_health
        cloud_stats["weak"] = len(cloud_health.list_weak())
    except Exception:
        pass

    return {
        "timestamp": datetime.now().isoformat(),
        "running": cp.get("running", False),
        "queue_backend": cp.get("queue_backend", "unknown"),
        "uptime_seconds": cp.get("uptime_seconds", 0),
        "metrics": metrics,
        "agents": agents,
        "cloud_stats": cloud_stats,
        "cloud_health": cp.get("cloud_health", {"healthy": 0, "weak": 0}),
        "clinic": cp.get("clinic", {"tracked": 0, "quarantined": 0}),
        "knowledge": cp.get("knowledge", {"total_entries": 0}),
        "database": db,
        "tasks": task_stats,
        "sources_count": sources_count,
        "auto_scaler": (lambda: __import__("auto_scaler").auto_scaler.status())(),
        "email_pool": (lambda: __import__("email_pool").email_pool.stats())(),
        "million_runtime": (lambda: __import__("million_runtime").million_runtime.status())(),
        "cloud_multiplier": (lambda: __import__("cloud_multiplier").cloud_multiplier.status())(),
        "bootstrap": (lambda: __import__("bootstrap_controller").bootstrap_controller.status())(),
        "mission": (lambda: __import__("mission_controller").mission_controller.status())(),
        "auto_deployer": (lambda: __import__("auto_deployer").auto_deployer.status())(),
        "hf_token_present": bool(os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")),
        "github_token_present": bool(os.environ.get("GITHUB_TOKEN")),
        "storage_bytes": storage_bytes,
        "today": today_metrics,
    }


@app.route("/")
def index():
    return render_template("dashboard.html")


@app.route("/api/status")
def api_status():
    return jsonify(safe_status())


@app.route("/api/agents")
def api_agents():
    try:
        levels = {f"level_{i}": count_agents_by_level(i) for i in range(5)}
        return jsonify({"levels": levels})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/events")
def api_events():
    try:
        limit = int(request.args.get("limit", 20))
        events = get_recent_events(limit)
        return jsonify({"events": events})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/cloud/health")
def api_cloud_health():
    try:
        from cloud_health import cloud_health
        return jsonify({
            "healthy": cloud_health.list_healthy(),
            "weak": cloud_health.list_weak(),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/knowledge/stats")
def api_knowledge():
    try:
        from knowledge_sharing import knowledge_bus
        return jsonify(knowledge_bus.stats())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/clinic/status")
def api_clinic():
    try:
        from self_healing import clinic
        return jsonify(clinic.status())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/queue/info")
def api_queue():
    try:
        from queue_manager import get_backend
        return jsonify({"backend": get_backend()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/providers")
def api_providers():
    try:
        from db import list_providers
        providers = list_providers()
        return jsonify({"providers": providers, "count": len(providers)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500




@app.route("/api/tasks/recent")
def api_tasks_recent():
    try:
        limit = int(request.args.get("limit", 10))
        tasks = get_recent_tasks(limit)
        # Format for JS
        formatted = []
        for t in tasks:
            from datetime import datetime as _dt
            ts = _dt.fromtimestamp(t.get("started_at", 0)).strftime("%H:%M:%S")
            status_ar = {
                "completed": "مكتملة",
                "running": "جاري التنفيذ",
                "failed": "فاشلة",
                "pending": "بالانتظار"
            }.get(t.get("status"), t.get("status"))
            formatted.append({
                "time": ts,
                "title": t.get("title", ""),
                "status": t.get("status"),
                "status_ar": status_ar,
            })
        return jsonify({"tasks": formatted})
    except Exception as e:
        return jsonify({"error": str(e), "tasks": []}), 500


@app.route("/api/tasks/stats")
def api_tasks_stats():
    try:
        return jsonify(get_task_stats())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/sources")
def api_sources():
    try:
        sources = list_sources()
        from datetime import datetime as _dt
        formatted = []
        for s in sources:
            last = s.get("last_update") or 0
            if last:
                delta = int(time.time() - last)
                if delta < 60:
                    ago = f"منذ {delta} ثانية"
                elif delta < 3600:
                    ago = f"منذ {delta // 60} دقيقة"
                else:
                    ago = f"منذ {delta // 3600} ساعة"
            else:
                ago = "—"
            formatted.append({
                "name": s.get("name"),
                "platform": s.get("platform"),
                "status": s.get("status"),
                "items": s.get("items_collected", 0),
                "last": ago,
            })
        return jsonify({"sources": formatted})
    except Exception as e:
        return jsonify({"error": str(e), "sources": []}), 500


@app.route("/api/metrics/today")
def api_metrics_today():
    try:
        return jsonify(get_today_metrics())
    except Exception as e:
        return jsonify({"error": str(e)}), 500




@app.route("/api/cloud/unified")
def api_cloud_unified():
    try:
        from cloud_unifier import cloud_unifier
        return jsonify({
            "counts": cloud_unifier.count(),
            "status": cloud_unifier.status(),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/orchestrator/status")
def api_orch_status():
    try:
        from orchestrator import orchestrator
        return jsonify(orchestrator.status())
    except Exception as e:
        return jsonify({"error": str(e)}), 500




@app.route("/api/scaler/status")
def api_scaler_status():
    try:
        from auto_scaler import auto_scaler
        return jsonify(auto_scaler.status())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/scaler/force/<int:stage>", methods=["POST"])
def api_scaler_force(stage):
    try:
        from auto_scaler import auto_scaler
        return jsonify(auto_scaler.force_stage(stage))
    except Exception as e:
        return jsonify({"error": str(e)}), 500




@app.route("/api/email_pool/stats")
def api_email_pool_stats():
    try:
        from email_pool import email_pool
        return jsonify(email_pool.stats())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/email_pool/demand")
def api_email_pool_demand():
    try:
        from email_pool import email_pool
        return jsonify(email_pool.get_demand_report())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/email_pool/expand", methods=["POST"])
def api_email_pool_expand():
    try:
        from email_pool import email_pool
        return jsonify(email_pool.expand_for_clouds())
    except Exception as e:
        return jsonify({"error": str(e)}), 500




# ============================================================
# Distributed Workers API
# ============================================================

@app.route("/api/worker/register", methods=["POST"])
def api_worker_register():
    try:
        from distributed_manager import distributed_manager
        data = request.json or {}
        return jsonify(distributed_manager.register_worker(
            node_id=data.get("node_id", "unknown"),
            provider=data.get("provider", "unknown"),
            region=data.get("region", "auto"),
            endpoint=data.get("endpoint", ""),
            capacity=data.get("capacity", 10000),
        ))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/worker/heartbeat", methods=["POST"])
def api_worker_heartbeat():
    try:
        from distributed_manager import distributed_manager
        data = request.json or {}
        return jsonify(distributed_manager.heartbeat(
            node_id=data.get("node_id", "unknown"),
            cpu=data.get("cpu", 0),
            ram=data.get("ram", 0),
            active_agents=data.get("active_agents", 0),
            queue_size=data.get("queue_size", 0),
        ))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/distributed/status")
def api_distributed_status():
    try:
        from distributed_manager import distributed_manager
        return jsonify(distributed_manager.status())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/distributed/workers")
def api_distributed_workers():
    try:
        from distributed_manager import distributed_manager
        return jsonify({"workers": distributed_manager.list_workers()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500




@app.route("/api/master/plan")
def api_master_plan():
    try:
        from master_deploy import master_deployer
        return jsonify(master_deployer.plan())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/master/status")
def api_master_status():
    try:
        from master_deploy import master_deployer
        return jsonify(master_deployer.status())
    except Exception as e:
        return jsonify({"error": str(e)}), 500




@app.route("/api/million/status")
def api_million_status():
    try:
        from million_runtime import million_runtime
        return jsonify(million_runtime.status())
    except Exception as e:
        return jsonify({"error": str(e)}), 500




@app.route("/api/deployer/status")
def api_deployer_status():
    try:
        from auto_deployer import auto_deployer
        return jsonify(auto_deployer.status())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/deployer/history")
def api_deployer_history():
    try:
        from auto_deployer import auto_deployer
        return jsonify({"history": auto_deployer.history(20)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/deployer/force", methods=["POST"])
def api_deployer_force():
    try:
        from auto_deployer import auto_deployer
        data = request.json or {}
        return jsonify(auto_deployer.force_scale(
            provider=data.get("provider", "fly"),
            count=data.get("count", 10),
        ))
    except Exception as e:
        return jsonify({"error": str(e)}), 500




# ============================================================
# Mission Controller API
# ============================================================

@app.route("/api/mission/status")
def api_mission_status():
    try:
        from mission_controller import mission_controller
        return jsonify(mission_controller.status())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/mission/list")
def api_mission_list():
    try:
        from mission_controller import mission_controller
        return jsonify({"missions": mission_controller.list_missions()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/mission/start", methods=["POST"])
def api_mission_start():
    try:
        from mission_controller import mission_controller
        data = request.json or {}
        key = data.get("mission", "collect_code")
        config = data.get("config", {})
        return jsonify(mission_controller.start_mission(key, config))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/mission/stop", methods=["POST"])
def api_mission_stop():
    try:
        from mission_controller import mission_controller
        return jsonify(mission_controller.stop_mission())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/mission/custom", methods=["POST"])
def api_mission_custom():
    """Create and start a custom mission instantly."""
    try:
        from mission_controller import mission_controller, BUILTIN_MISSIONS
        import json as _json
        data = request.json or {}
        key = data.get("mission_key", f"custom_{int(time.time())}")
        name = data.get("name", "مهمة مخصصة")
        description = data.get("description", "")
        config = data.get("config", {"type": "generic", "target_count": 1000})

        # Save mission to DB
        from db import get_conn
        with get_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO missions "
                "(mission_key, name, description, config, status, created_at) "
                "VALUES (?, ?, ?, ?, 'pending', ?)",
                (key, name, description, _json.dumps(config), time.time())
            )
            conn.commit()

        # Register as built-in for immediate use
        BUILTIN_MISSIONS[key] = {
            "name": name,
            "description": description,
            "config": config,
        }

        # Start it
        result = mission_controller.start_mission(key, config)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/bootstrap/status")
def api_bootstrap_status():
    try:
        from bootstrap_controller import bootstrap_controller
        return jsonify(bootstrap_controller.status())
    except Exception as e:
        return jsonify({"error": str(e)}), 500




# ============================================================
# Cloud Multiplier API
# ============================================================

@app.route("/api/multiplier/status")
def api_multiplier_status():
    try:
        from cloud_multiplier import cloud_multiplier
        return jsonify(cloud_multiplier.status())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/multiplier/double", methods=["POST"])
def api_multiplier_double():
    try:
        from cloud_multiplier import cloud_multiplier
        return jsonify(cloud_multiplier.force_double())
    except Exception as e:
        return jsonify({"error": str(e)}), 500




# ============================================================
# Cloudflare Multi-Account API
# ============================================================

@app.route("/api/cf/status")
def api_cf_status():
    try:
        from multi_account_manager import multi_account_manager
        return jsonify(multi_account_manager.status())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/cf/verify")
def api_cf_verify():
    try:
        from multi_account_manager import multi_account_manager
        return jsonify(multi_account_manager.verify_all())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/cf/deploy", methods=["POST"])
def api_cf_deploy():
    try:
        from multi_account_manager import multi_account_manager
        data = request.json or {}
        return jsonify(multi_account_manager.deploy_all(
            workers_per_account=data.get("workers_per_account", 10),
            dry_run=data.get("dry_run", False),
        ))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/cf/diagnose")
def api_cf_diagnose():
    """Show subdomain status + raw errors for each account."""
    import requests as _rq
    try:
        from multi_account_manager import multi_account_manager
        results = []
        for a in multi_account_manager.accounts:
            token = a["token"]
            account = a["account_id"]
            name = a["name"]

            # Check subdomain status
            sub_url = f"https://api.cloudflare.com/client/v4/accounts/{account}/workers/subdomain"
            sub_headers = {"Authorization": f"Bearer {token}"}
            try:
                sub_r = _rq.get(sub_url, headers=sub_headers, timeout=15)
                sub_data = sub_r.json()
                sub_status = sub_data.get("result", {}).get("subdomain", "NOT_SET")
            except Exception as e:
                sub_status = f"error: {e}"

            # Try deploy
            deploy_url = f"https://api.cloudflare.com/client/v4/accounts/{account}/workers/scripts/diag-{name}"
            metadata = {"main_module": "worker.js", "compatibility_date": "2024-01-01"}
            files = {
                "metadata": (None, __import__("json").dumps(metadata), "application/json"),
                "worker.js": ("worker.js", "export default { fetch() { return new Response('ok'); } }", "application/javascript+module"),
            }
            try:
                dep_r = _rq.put(deploy_url, headers=sub_headers, files=files, timeout=30)
                try:
                    dep_json = dep_r.json()
                    dep_errors = dep_json.get("errors", [])
                except Exception:
                    dep_errors = []
                results.append({
                    "account": name,
                    "subdomain": sub_status,
                    "deploy_status": dep_r.status_code,
                    "deploy_errors": dep_errors,
                })
            except Exception as e:
                results.append({
                    "account": name,
                    "subdomain": sub_status,
                    "deploy_error": str(e),
                })
        return jsonify({"results": results})
    except Exception as e:
        return jsonify({"error": str(e)}), 500




@app.route("/api/cf/check_subdomains")
def api_cf_check_subdomains():
    """Check workers.dev subdomain status for each account."""
    import requests as _rq
    try:
        from multi_account_manager import multi_account_manager
        results = []
        for a in multi_account_manager.accounts:
            token = a["token"]
            account = a["account_id"]
            name = a["name"]
            url = f"https://api.cloudflare.com/client/v4/accounts/{account}/workers/subdomain"
            headers = {"Authorization": f"Bearer {token}"}
            try:
                r = _rq.get(url, headers=headers, timeout=15)
                data = r.json()
                subdomain = data.get("result", {}).get("subdomain", "NOT_SET")
                results.append({
                    "account": name,
                    "account_id": account[:10] + "...",
                    "subdomain": subdomain,
                    "status_code": r.status_code,
                })
            except Exception as e:
                results.append({"account": name, "error": str(e)})
        return jsonify({"results": results})
    except Exception as e:
        return jsonify({"error": str(e)}), 500



@app.route("/api/cf/force_subdomain")
def api_cf_force_subdomain():
    """Try to create subdomain via PUT for each account - show raw error."""
    import requests as _rq
    import hashlib
    try:
        from multi_account_manager import multi_account_manager
        results = []
        for a in multi_account_manager.accounts:
            token = a["token"]
            account = a["account_id"]
            name = a["name"]

            sub_name = "marsad-" + hashlib.md5(account.encode()).hexdigest()[:8]
            url = f"https://api.cloudflare.com/client/v4/accounts/{account}/workers/subdomain"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            # 1. Check current state
            try:
                g = _rq.get(url, headers=headers, timeout=15)
                g_data = g.json()
                current = (g_data.get("result") or {}).get("subdomain", "NONE")
            except Exception as e:
                current = f"error: {e}"

            # 2. Try to create
            try:
                p = _rq.put(url, headers=headers, json={"subdomain": sub_name}, timeout=30)
                try:
                    p_data = p.json()
                    errors = p_data.get("errors", [])
                except Exception:
                    errors = []
                results.append({
                    "account": name,
                    "current_subdomain": current,
                    "put_status": p.status_code,
                    "put_success": p_data.get("success") if 'p_data' in dir() else None,
                    "put_errors": errors,
                    "raw": p.text[:250] if p.status_code != 200 else "OK",
                })
            except Exception as e:
                results.append({
                    "account": name,
                    "current_subdomain": current,
                    "put_error": str(e),
                })

        return jsonify({"results": results})
    except Exception as e:
        return jsonify({"error": str(e)}), 500



# ============================================================
# Cloudflare Subdomain Creation (Async)
# ============================================================

@app.route("/api/cf/force_subdomain_dummy")
def api_cf_force_subdomain_dummy():
    """Force subdomain creation via dummy worker - runs in BACKGROUND."""
    import threading as _thr
    import json as _json
    from pathlib import Path as _P
    import time as _t

    status_file = _P("/tmp/subdomain_status.json")

    def _worker():
        try:
            from multi_account_manager import multi_account_manager
            from cloudflare_deployer import force_subdomain_via_dummy
            results = []
            for a in multi_account_manager.accounts:
                r = force_subdomain_via_dummy(a["token"], a["account_id"])
                results.append({
                    "account": a["name"],
                    "result": r.get("status"),
                    "output": r.get("output", "")[:100],
                })
                _t.sleep(1)
            status_file.write_text(_json.dumps({"results": results}))
        except Exception as e:
            status_file.write_text(_json.dumps({"error": str(e)}))

    if status_file.exists():
        try:
            status_file.unlink()
        except Exception:
            pass

    _thr.Thread(target=_worker, daemon=True).start()

    return jsonify({
        "status": "started",
        "message": "Running in background. Check /api/cf/subdomain_status in 60 seconds."
    })


@app.route("/api/cf/subdomain_status")
def api_cf_subdomain_status():
    """Check background subdomain creation status."""
    from pathlib import Path as _P
    import json as _json

    status_file = _P("/tmp/subdomain_status.json")
    if status_file.exists():
        try:
            return jsonify(_json.loads(status_file.read_text()))
        except Exception:
            pass
    return jsonify({"status": "running_or_not_started"})


@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "marsad-dashboard"})


def _open_browser(port):
    """Open the dashboard in the default browser after server starts."""
    import time as _t
    _t.sleep(1.5)
    url = f"http://localhost:{port}"
    try:
        webbrowser.open(url)
        print(f"[Dashboard] Browser opened: {url}")
    except Exception as e:
        print(f"[Dashboard] Could not open browser: {e}")
        print(f"[Dashboard] Open manually: {url}")


# ============================================================
# Auto-start Control Plane + Worker Pool when run standalone
# ============================================================
def _auto_start_subsystems():
    """Start control_plane and worker_pool in background."""
    try:
        from control_plane import control_plane
        control_plane.start()
        print("[Dashboard] Control Plane started")
    except Exception as e:
        print(f"[Dashboard] Control Plane failed: {e}")

    try:
        from worker_pool import worker_pool
        worker_pool.start()
        print("[Dashboard] Worker Pool started")
    except Exception as e:
        print(f"[Dashboard] Worker Pool failed: {e}")


def _open_browser(port):
    """Open the dashboard in the default browser after server starts."""
    import time as _t
    _t.sleep(1.5)
    url = f"http://localhost:{port}"
    try:
        webbrowser.open(url)
        print(f"[Dashboard] Browser opened: {url}")
    except Exception as e:
        print(f"[Dashboard] Could not open browser: {e}")
        print(f"[Dashboard] Open manually: {url}")


# ============================================================
# Self-Ping: prevents Render free tier from sleeping
# ============================================================
import threading as _th
import requests as _rq


def _self_ping_loop():
    """Ping self every 5 min to stay awake."""
    time.sleep(60)  # wait for startup
    import os
    while True:
        try:
            # Get own URL from env or default
            url = os.environ.get("CG_SELF_URL", "")
            if not url:
                # Try Render's provided URL
                url = os.environ.get("RENDER_EXTERNAL_URL", "")
            if not url:
                # Fallback
                port = os.environ.get("PORT", "10000")
                url = f"http://localhost:{port}"
            
            url = url.rstrip("/") + "/api/status"
            r = _rq.get(url, timeout=15)
            print(f"[SelfPing] {url} -> {r.status_code}", flush=True)
        except Exception as e:
            print(f"[SelfPing] error: {e}", flush=True)
        time.sleep(300)  # 5 minutes


def _start_self_ping():
    t = _th.Thread(target=_self_ping_loop, daemon=True)
    t.start()
    print("[SelfPing] Started", flush=True)


if __name__ == "__main__":
    _prime_psutil()
    port = int(os.environ.get("PORT", "5000"))

    print(f"""
    ╔══════════════════════════════════════════════════════════╗
    ║           MARSAD DASHBOARD - Flask Server                ║
    ║  http://0.0.0.0:{port:<42}║
    ╚══════════════════════════════════════════════════════════╝
    """)

    # Auto-start subsystems
    if os.environ.get("CG_NO_AUTOSTART", "false").lower() != "true":
        _auto_start_subsystems()

    # Auto-open browser
    if os.environ.get("CG_NO_BROWSER", "false").lower() != "true":
        threading.Thread(target=_open_browser, args=(port,), daemon=True).start()

    if os.environ.get("CG_SELF_PING", "true").lower() == "true":
        _start_self_ping()

    app.run(host="0.0.0.0", port=port, debug=False)





@app.route("/api/cf/diagnose")
def api_cf_diagnose():
    """Diagnose Cloudflare tokens - show raw API errors."""
    import requests as _rq
    try:
        from multi_account_manager import multi_account_manager
        results = []
        for a in multi_account_manager.accounts:
            token = a["token"]
            account = a["account_id"]
            url = f"https://api.cloudflare.com/client/v4/accounts/{account}/workers/scripts/test-diag"
            headers = {"Authorization": f"Bearer {token}"}
            metadata = {"main_module": "worker.js", "compatibility_date": "2024-01-01"}
            files = {
                "metadata": (None, __import__("json").dumps(metadata), "application/json"),
                "worker.js": ("worker.js", "export default { fetch() { return new Response('ok'); } }", "application/javascript"),
            }
            try:
                r = _rq.put(url, headers=headers, files=files, timeout=30)
                try:
                    parsed = r.json()
                    errors = parsed.get("errors", [])
                except Exception:
                    errors = []
                results.append({
                    "account": a["name"],
                    "http_status": r.status_code,
                    "errors": errors,
                    "raw": r.text[:400],
                })
            except Exception as e:
                results.append({"account": a["name"], "error": str(e)})
        return jsonify({"results": results})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


