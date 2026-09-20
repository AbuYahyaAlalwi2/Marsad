"""يكتب حالة حقيقية لـ marsad_state.json ليقرأها الداشبورد"""
import json
import time
import os
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).resolve().parent
STATE_FILE = BASE / "marsad_state.json"

def write_state(**kwargs):
    data = {}
    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    data.update(kwargs)
    data["updated_at"] = datetime.now().isoformat()
    data["running"] = kwargs.get("running", data.get("running", False))
    # activity ring
    act = data.get("activity", [])
    if "activity_msg" in kwargs:
        act.append({"time": datetime.now().strftime("%H:%M:%S"), "message": kwargs.pop("activity_msg")})
        data["activity"] = act[-50:]
    STATE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def mark_running(running: bool, msg: str = None):
    write_state(running=running, activity_msg=msg or ("تشغيل" if running else "إيقاف"))

def update_from_db():
    try:
        from db import count_agents_by_level, get_database_stats, get_recent_events
        agents = sum(count_agents_by_level(i) for i in range(5))
        stats = get_database_stats()
        events = get_recent_events(20)
        logs = []
        for e in events:
            logs.append(f"{e.get('created_at','')} | {e.get('event_type','')} | {str(e.get('payload',''))[:80]}")
        write_state(
            agents=agents,
            sources=stats.get("datasets_count", 0),
            tasks_completed=stats.get("tasks_count", 0) if "tasks_count" in stats else stats.get("samples_count", 0),
            errors=0,
            logs=logs,
            engines={
                "hierarchy": "active" if agents else "idle",
                "vault": "ready",
                "autorun": "on" if Path(BASE / "data" / "autorun.pid").exists() else "off",
            }
        )
    except Exception as e:
        write_state(activity_msg=f"state update error: {e}")
