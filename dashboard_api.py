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
import importlib

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
    """Full dashboard status - hardened with error handling."""
    try:
        _prime_psutil()
        cp = get_cp_status()
        db = {}
        try:
            db = get_database_stats()
        except Exception:
            pass

        # Metrics
        metrics = {"cpu": 0, "ram": 0, "disk": 0, "net": 0}
        try:
            import psutil
            metrics["cpu"] = round(psutil.cpu_percent(interval=0.1), 1)
            metrics["ram"] = round(psutil.virtual_memory().percent, 1)
            metrics["disk"] = round(psutil.disk_usage(str(BASE)).percent, 1)
            try:
                n1 = psutil.net_io_counters()
                import time as _t
                _t.sleep(0.1)
                n2 = psutil.net_io_counters()
                delta = (n2.bytes_sent - n1.bytes_sent) + (n2.bytes_recv - n1.bytes_recv)
                metrics["net"] = min(100.0, round(delta / 102.4, 1))
            except Exception:
                metrics["net"] = 0
        except Exception:
            pass

        # Agents
        agents = {"total": 0, "level_1": 0, "level_2": 0, "level_3": 0, "level_4": 0, "level_5": 0}
        try:
            for i in range(5):
                c = count_agents_by_level(i)
                if i == 0: agents["level_1"] = c
                elif i == 1: agents["level_2"] = c
                elif i == 2: agents["level_3"] = c
                elif i == 3: agents["level_4"] = c
                elif i == 4: agents["level_5"] = c
                agents["total"] += c
        except Exception:
            pass

        # Cloud stats
        cloud_stats = {"active": 0, "available": 0, "total": 0, "weak": 0}
        try:
            from cloud_unifier import count_registered_providers
            cloud_stats.update(count_registered_providers())
            from cloud_health import cloud_health
            cloud_stats["weak"] = len(cloud_health.list_weak())
        except Exception:
            pass

        # Task stats
        task_stats = {"total": 0, "completed": 0, "failed": 0, "running": 0, "success_rate": 0.0}
        try:
            task_stats = get_task_stats()
        except Exception:
            pass

        # Sources count
        sources_count = 0
        try:
            sources_count = len(list_sources())
        except Exception:
            pass

        # Today's metrics
        today_metrics = {}
        try:
            today_metrics = get_today_metrics()
        except Exception:
            pass

        # Storage bytes
        storage_bytes = 0
        try:
            import os as _os
            for sub in ("data", "models", "datasets"):
                root = str(BASE / sub)
                if not _os.path.isdir(root): continue
                for dirpath, _, filenames in _os.walk(root):
                    for fn in filenames:
                        try: storage_bytes += _os.path.getsize(_os.path.join(dirpath, fn))
                        except Exception: pass
            try:
                from config import DB_PATH
                if _os.path.isfile(DB_PATH): storage_bytes += _os.path.getsize(DB_PATH)
            except Exception: pass
        except Exception:
            pass

        # ابدأ بكل ما يرجعه control_plane
        result = dict(cp) if cp else {}

        result.update({
            "timestamp": datetime.now().isoformat(),
            "running": cp.get("running", False),
            "queue_backend": cp.get("queue_backend", "unknown"),
            "uptime_seconds": cp.get("uptime_seconds", 0),
            "metrics": metrics,
            "agents": agents,
            "cloud_stats": cloud_stats,
            "database": db,
            "tasks": task_stats,
            "sources_count": sources_count,
            "hf_token_present": bool(os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")),
            "github_token_present": bool(os.environ.get("GITHUB_TOKEN")),
            "storage_bytes": storage_bytes,
            "today": today_metrics,
        })

        # أضف الوحدات الإضافية بأمان
        extras = {
            "auto_scaler": "auto_scaler.auto_scaler",
            "email_pool": "email_pool.email_pool",
            "million_runtime": "million_runtime.million_runtime",
            "cloud_multiplier": "cloud_multiplier.cloud_multiplier",
            "bootstrap": "bootstrap_controller.bootstrap_controller",
            "mission": "mission_controller.mission_controller",
            "auto_deployer": "auto_deployer.auto_deployer",
            "free_merger": "free_merger.free_merger",
            "cf_multi_account": "multi_account_manager.multi_account_manager",
            "orchestrator": "orchestrator.orchestrator",
            "cloud_unifier": "cloud_unifier.cloud_unifier",
            "distributed": "distributed_manager.distributed_manager",
            "gpu_pool": "gpu_pool.pool_manager.gpu_pool",
        }
        import importlib
        for key, path in extras.items():
            try:
                module_path, attr_name = path.rsplit(".", 1)
                module = importlib.import_module(module_path)
                obj = getattr(module, attr_name)
                if hasattr(obj, "status"):
                    result[key] = obj.status()
                elif hasattr(obj, "stats"):
                    result[key] = obj.stats()
            except Exception as e:
                result[key] = {"error": str(e)[:100]}

        # تأكد من إمكانية التسلسل
        import json as _json
        try:
            _json.dumps(result, default=str)
        except Exception:
            clean = {}
            for k, v in result.items():
                try:
                    _json.dumps(v, default=str)
                    clean[k] = v
                except Exception:
                    clean[k] = str(v)[:200]
            return clean

        return result

    except Exception as e:
        # في حال حدوث أي خطأ غير متوقع، نعيد استجابة طارئة
        import traceback
        return {
            "status": "error",
            "message": "safe_status failed",
            "error": str(e),
            "trace": traceback.format_exc()[:500],
            "running": True,
            "timestamp": datetime.now().isoformat(),
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


@app.route("/api/saturn/test")
def api_saturn_test():
    """يختبر المصادقة على Saturn Cloud (كل الحسابات)."""
    try:
        import httpx
        from core.account_pool import account_pool
        results = []
        for acc in account_pool.accounts:
            if acc.platform != "saturn":
                continue
            token = acc.creds.get("key", "")
            try:
                r = httpx.get(
                    "https://app.community.saturnenterprise.io/me",
                    headers={"Authorization": f"token {token}"},
                    timeout=15, follow_redirects=True)
                results.append({
                    "account": acc.name(),
                    "status": r.status_code,
                    "ok": r.status_code == 200,
                    "preview": r.text[:120] if not r.ok else "authenticated",
                })
            except Exception as e:
                results.append({
                    "account": acc.name(),
                    "error": str(e)[:120],
                })
        return jsonify({"count": len(results), "results": results})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/accounts/status")
def api_accounts_status():
    """حالة مجموعة الحسابات (Cloudflare/Kaggle/Saturn/Fly/Railway...)."""
    try:
        from core.account_pool import account_pool
        return jsonify({
            "stats": account_pool.stats(),
            "total": len(account_pool.accounts),
            "accounts": [a.name() for a in account_pool.accounts],
        })
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




@app.route("/api/cf/whoami")
def api_cf_whoami():
    """Show which accounts each token actually has access to."""
    import requests as _rq
    try:
        from multi_account_manager import multi_account_manager
        results = []
        for a in multi_account_manager.accounts:
            token = a["token"]
            given_account = a["account_id"]
            name = a["name"]

            # Query user details + accounts
            try:
                r = _rq.get(
                    "https://api.cloudflare.com/client/v4/accounts",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=15,
                )
                data = r.json()
                real_accounts = [
                    {"id": acc.get("id"), "name": acc.get("name")}
                    for acc in (data.get("result") or [])
                ]
                match = any(acc["id"] == given_account for acc in real_accounts)
                results.append({
                    "variable": name,
                    "given_account_id": given_account[:12] + "...",
                    "match": match,
                    "real_accounts": real_accounts,
                    "http_status": r.status_code,
                })
            except Exception as e:
                results.append({
                    "variable": name,
                    "given_account_id": given_account[:12] + "...",
                    "error": str(e),
                })
        return jsonify({"results": results})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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


@app.route("/api/gpu/status")
def api_gpu_status():
    try:
        from gpu_pool.pool_manager import gpu_pool
        return jsonify(gpu_pool.status())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/gpu/merge", methods=["POST"])
def api_gpu_merge():
    try:
        from gpu_pool.unified_executor import unified_executor
        data = request.json or {}
        result = unified_executor.execute("merge", data)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/gpu/train", methods=["POST"])
def api_gpu_train():
    try:
        from gpu_pool.unified_executor import unified_executor
        data = request.json or {}
        result = unified_executor.execute("train", data)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/ping")
def api_ping():
    import subprocess
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5
        ).stdout.strip()
    except Exception:
        commit = "unknown"
    return jsonify({
        "status": "ok",
        "commit": commit,
        "gpu_routes": [
            str(r) for r in __import__("flask").current_app.url_map.iter_rules()
            if "gpu" in str(r)
        ],
    })


@app.route("/api/diag/kaggle")
def api_diag_kaggle():
    """تشخيص مباشر لكاغل - يعرض كل التفاصيل."""
    import traceback
    result = {
        "kaggle_installed": False,
        "credentials": {},
        "push_attempt": {},
    }
    
    # 1. هل kaggle مثبت؟
    try:
        from kaggle.api.kaggle_api_extended import KaggleApi
        result["kaggle_installed"] = True
    except ImportError as e:
        result["kaggle_error"] = str(e)
        return jsonify(result)
    
    # 2. الإعدادات
    import os
    result["credentials"] = {
        "KAGGLE_USERNAME": os.environ.get("KAGGLE_USERNAME", "")[:20],
        "KAGGLE_KEY_length": len(os.environ.get("KAGGLE_KEY", "")),
        "KAGGLE_CONFIG_DIR": os.environ.get("KAGGLE_CONFIG_DIR", "not_set"),
    }
    
    # من gpu_pool
    try:
        from gpu_pool.pool_manager import gpu_pool
        kaggle_providers = [p for p in gpu_pool.providers if p.name.startswith("kaggle_")]
        result["providers_found"] = len(kaggle_providers)
        if kaggle_providers:
            kp = kaggle_providers[0]
            result["first_provider"] = {
                "name": kp.name,
                "username": kp.username[:20],
                "token_length": len(kp.token),
            }
    except Exception as e:
        result["pool_error"] = str(e)
        return jsonify(result)
    
    # 3. جرّب رفع دفتر تجريبي
    try:
        import json, tempfile, os
        from pathlib import Path
        
        kp = kaggle_providers[0]
        kaggle_dir = Path(tempfile.gettempdir()) / f"auth_diag_{kp.name}"
        kaggle_dir.mkdir(parents=True, exist_ok=True)
        (kaggle_dir / "kaggle.json").write_text(json.dumps({
            "username": kp.username,
            "key": kp.token,
        }))
        os.environ["KAGGLE_CONFIG_DIR"] = str(kaggle_dir)
        os.environ["KAGGLE_USERNAME"] = kp.username
        os.environ["KAGGLE_KEY"] = kp.token
        
        # اكتب دفتر تجريبي
        test_dir = Path(tempfile.gettempdir()) / "diag_kernel"
        test_dir.mkdir(exist_ok=True)
        
        (test_dir / "kernel-metadata.json").write_text(json.dumps({
            "id": f"{kp.username}/marsad-diag-test",
            "title": "Marsad Diag Test",
            "code_file": "test.ipynb",
            "language": "python",
            "kernel_type": "notebook",
            "is_private": True,
            "enable_gpu": False,
            "enable_internet": True,
            "dataset_sources": [],
            "competition_sources": [],
            "kernel_sources": [],
        }, indent=2))
        
        (test_dir / "test.ipynb").write_text(json.dumps({
            "cells": [{"cell_type": "code", "source": ["print('hi')"], 
                       "metadata": {}, "outputs": [], "execution_count": None}],
            "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
            "nbformat": 4, "nbformat_minor": 5,
        }))
        
        api = KaggleApi()
        api.authenticate()
        
        result["push_attempt"]["username"] = kp.username
        result["push_attempt"]["test_dir"] = str(test_dir)
        
        try:
            api.kernels_push(str(test_dir))
            result["push_attempt"]["result"] = "SUCCESS"
        except Exception as push_err:
            result["push_attempt"]["result"] = "FAILED"
            result["push_attempt"]["error"] = str(push_err)[:500]
            result["push_attempt"]["traceback"] = traceback.format_exc()[-800:]
    except Exception as e:
        result["push_attempt"]["error"] = str(e)[:300]
        result["push_attempt"]["traceback"] = traceback.format_exc()[-800:]
    
    return jsonify(result)

@app.route("/api/diag/kaggle_full")
def api_diag_kaggle_full():
    """يختبر kaggle_deployer.run() مباشرة."""
    try:
        from gpu_pool.pool_manager import gpu_pool
        from gpu_pool.kaggle_deployer import kaggle_deployer
        
        kp = [p for p in gpu_pool.providers if p.name.startswith("kaggle_")]
        if not kp:
            return jsonify({"error": "no kaggle provider"})
        
        provider = kp[0]
        result = kaggle_deployer.run(
            provider=provider,
            task_type="merge",
            payload={"base_model": "cognitivecomputations/dolphin-2.9-llama3-8b"},
        )
        return jsonify({
            "provider": provider.name,
            "username": provider.username,
            "result": result,
        })
    except Exception as e:
        import traceback
        return jsonify({"error": str(e)[:300], "traceback": traceback.format_exc()[-1000:]}), 500

@app.route("/api/diag/kaggle_async")
def api_diag_kaggle_async():
    """يشغّل kaggle_deployer.run() في الخلفية."""
    import threading as _thr
    from pathlib import Path as _P
    import json as _json

    result_file = _P("/tmp/kaggle_async_result.json")

    def _worker():
        try:
            from gpu_pool.pool_manager import gpu_pool
            from gpu_pool.kaggle_deployer import kaggle_deployer
            kp = [p for p in gpu_pool.providers if p.name.startswith("kaggle_")]
            if not kp:
                result_file.write_text(_json.dumps({"error": "no kaggle provider"}))
                return
            provider = kp[0]
            result = kaggle_deployer.run(
                provider=provider,
                task_type="merge",
                payload={"base_model": "cognitivecomputations/dolphin-2.9-llama3-8b"},
            )
            result_file.write_text(_json.dumps({
                "provider": provider.name,
                "username": provider.username,
                "result": result,
            }, default=str))
        except Exception as e:
            import traceback
            result_file.write_text(_json.dumps({
                "error": str(e)[:300],
                "traceback": traceback.format_exc()[-1500:],
            }))

    if result_file.exists():
        try:
            result_file.unlink()
        except Exception:
            pass

    _thr.Thread(target=_worker, daemon=True).start()
    return jsonify({"status": "started"})


@app.route("/api/diag/kaggle_async_result")
def api_diag_kaggle_async_result():
    from pathlib import Path as _P
    import json as _json
    f = _P("/tmp/kaggle_async_result.json")
    if f.exists():
        try:
            return jsonify(_json.loads(f.read_text()))
        except Exception:
            pass
    return jsonify({"status": "not_ready"})
@app.route("/api/gpu/kaggle_status/<kernel_slug>")
def api_kaggle_status(kernel_slug):
    try:
        from gpu_pool.kaggle_deployer import kaggle_deployer
        from gpu_pool.pool_manager import gpu_pool
        kp = [p for p in gpu_pool.providers if p.name.startswith("kaggle_")]
        if not kp:
            return jsonify({"error": "no kaggle provider"}), 404

        provider = kp[0]
        kaggle_deployer._setup_credentials(provider)

        from kaggle.api.kaggle_api_extended import KaggleApi
        api = KaggleApi()
        api.authenticate()

        status = api.kernels_status(f"{provider.username}/{kernel_slug}")
        return jsonify({
            "kernel": kernel_slug,
            "status": str(status),
            "username": provider.username,
        })
    except Exception as e:
        return jsonify({"error": str(e)[:300]}), 500



@app.route("/api/diag/saturn_urls")
def api_diag_saturn_urls():
    """يجرّب كل روابط ساتورن الممكنة."""
    import os
    import requests as _rq
    
    token = os.environ.get("SATURN_API_KEY_1", "")
    if not token:
        return jsonify({"error": "no_token"})
    
    urls = [
        "https://app.compute.studio/api/user/profile",
        "https://api.compute.studio/api/user/profile",
        "https://api.saturncloud.io/api/user/profile",
        "https://api.saturncloud.io/user/profile",
        "https://unity.saturnenterprise.io/api/user/profile",
        "https://saturnenterprise.io/api/user/profile",
        "https://api.saturnenterprise.io/user/profile",
        "https://app.compute.studio/api/v1/user/profile",
    ]
    
    results = {}
    for url in urls:
        try:
            r = _rq.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
                allow_redirects=True,
            )
            results[url] = {
                "status": r.status_code,
                "response": r.text[:150],
                "url_final": r.url,
            }
        except Exception as e:
            results[url] = {"error": str(e)[:100]}
    
    return jsonify({"token_length": len(token), "results": results})
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




@app.route("/api/merger/status")
def api_merger_status():
    try:
        from free_merger import free_merger
        return jsonify(free_merger.status())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/merger/run", methods=["POST"])
def api_merger_run():
    try:
        from free_merger import free_merger
        return jsonify(free_merger.merge(strategy="auto"))
    except Exception as e:
        return jsonify({"error": str(e)}), 500




@app.route("/api/diag/saturn")
def api_diag_saturn():
    """يختبر اتصال ساتورن من Render."""
    import os
    import requests as _rq
    token = os.environ.get("SATURN_API_KEY_1", "")
    if not token:
        return jsonify({"error": "no_token", "length": 0})

    results = {"token_length": len(token)}

    # جرّب 4 روابط
    urls = [
        "https://app.compute.studio/api/user/profile",
        "https://api.compute.studio/user/profile",
        "https://api.saturncloud.io/user/profile",
        "https://unity.saturnenterprise.io/api/user/profile",
    ]

    for url in urls:
        try:
            r = _rq.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=10)
            results[url] = {
                "status": r.status_code,
                "response": r.text[:150],
            }
        except Exception as e:
            results[url] = {"error": str(e)[:100]}

    return jsonify(results)


