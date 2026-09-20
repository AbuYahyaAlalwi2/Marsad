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

    return {
        "timestamp": datetime.now().isoformat(),
        "running": cp.get("running", False),
        "queue_backend": cp.get("queue_backend", "unknown"),
        "uptime_seconds": cp.get("uptime_seconds", 0),
        "metrics": metrics,
        "agents": agents,
        "cloud_health": cp.get("cloud_health", {"healthy": 0, "weak": 0}),
        "clinic": cp.get("clinic", {"tracked": 0, "quarantined": 0}),
        "knowledge": cp.get("knowledge", {"total_entries": 0}),
        "database": db,
        "tasks": task_stats,
        "sources_count": sources_count,
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

    app.run(host="0.0.0.0", port=port, debug=False)
