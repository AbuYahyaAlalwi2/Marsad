"""MARSAD real dashboard.

The dashboard is the only web process. It reads persisted state and the SQLite
 database, and delegates natural-language commands to the real chat engine.
It never invents provider, agent, task, or cloud results.
"""
import json
import os
import signal
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import streamlit as st

try:
    import psutil
except ImportError:
    psutil = None

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
os.chdir(BASE_DIR)
STATE_FILE = Path(os.getenv("MARSAD_STATE_FILE", BASE_DIR / "marsad_state.json"))
PID_FILE = BASE_DIR / "data" / "autorun.pid"
LOG_FILE = BASE_DIR / "data" / "autorun.log"

try:
    from db import _ensure_db, get_database_stats, get_recent_events, list_providers
    _ensure_db()
    DB_READY = True
except Exception as exc:
    DB_READY = False
    DB_ERROR = str(exc)


def read_state():
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8")) if STATE_FILE.exists() else {}
    except (OSError, ValueError):
        return {}


def process_alive():
    if not PID_FILE.exists():
        return False
    try:
        pid = int(PID_FILE.read_text(encoding="utf-8").strip())
        return psutil.pid_exists(pid) if psutil else True
    except (OSError, ValueError):
        return False


def start_engine():
    if process_alive():
        return True, "المحرك يعمل بالفعل."
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    log = LOG_FILE.open("a", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, str(BASE_DIR / "autorun.py")],
        cwd=str(BASE_DIR),
        stdout=log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        env={**os.environ, "CG_DB_PATH": os.getenv("CG_DB_PATH", "/tmp/cyberguard.db")},
    )
    PID_FILE.write_text(str(proc.pid), encoding="utf-8")
    return True, f"تم تشغيل المحرك الحقيقي، PID={proc.pid}"


def stop_engine():
    if not PID_FILE.exists():
        return True, "المحرك متوقف."
    try:
        pid = int(PID_FILE.read_text(encoding="utf-8").strip())
        os.kill(pid, signal.SIGTERM)
        PID_FILE.unlink(missing_ok=True)
        return True, "تم إيقاف المحرك."
    except (OSError, ValueError) as exc:
        return False, f"تعذر الإيقاف: {exc}"


def normalize_command(value):
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("command", "text", "message", "query", "input"):
            if isinstance(value.get(key), str):
                return value[key].strip()
    return str(value).strip()


def execute_text(command):
    """Send a natural-language command to the local engine, without fake fallback."""
    command = normalize_command(command)
    if not command:
        return {"status": "error", "error": "الأمر فارغ."}
    try:
        from chat.interface import chat
        result = chat.handle(command)
        return result if isinstance(result, dict) else {"status": "success", "result": result}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def metrics():
    if not psutil:
        return None
    return {
        "cpu": psutil.cpu_percent(interval=0.1),
        "ram": psutil.virtual_memory().percent,
        "disk": psutil.disk_usage(str(BASE_DIR)).percent,
    }


st.set_page_config(page_title="MARSAD", page_icon="◈", layout="wide")
st.markdown("""<style>
.stApp{background:#050b18;color:#e8eefc}.block-container{max-width:1500px}
.card{background:#0a1528;border:1px solid #182944;border-radius:14px;padding:18px}
</style>""", unsafe_allow_html=True)

state = read_state()
resource = metrics()
running = process_alive() or bool(state.get("running"))

with st.sidebar:
    st.title("◈ MARSAD")
    st.caption("لوحة تشغيل حقيقية — لا توجد أرقام وهمية")
    st.success("النظام يعمل" if running else "النظام متوقف") if running else st.error("النظام متوقف")
    if st.button("🟢 تشغيل المحرك", use_container_width=True):
        ok, message = start_engine()
        st.toast(message, icon="✅" if ok else "⚠️")
        st.rerun()
    if st.button("🔴 إيقاف المحرك", use_container_width=True):
        ok, message = stop_engine()
        st.toast(message, icon="✅" if ok else "⚠️")
        st.rerun()
    if resource:
        st.metric("CPU", f"{resource['cpu']:.0f}%")
        st.metric("RAM", f"{resource['ram']:.0f}%")
        st.metric("Disk", f"{resource['disk']:.0f}%")

st.title("لوحة تحكم MARSAD")
st.caption(f"{datetime.now():%Y-%m-%d %H:%M:%S} • المضيف: {socket.gethostname()}")

if not DB_READY:
    st.error(f"قاعدة البيانات غير متاحة: {DB_ERROR}")

stats = get_database_stats() if DB_READY else {}
providers = list_providers() if DB_READY else []
col1, col2, col3, col4 = st.columns(4)
col1.metric("المحرك", "يعمل" if running else "متوقف")
col2.metric("مزودو API المسجلون", len(providers))
col3.metric("العينات", stats.get("samples_count", 0))
col4.metric("المهام", stats.get("tasks_count", 0))

left, right = st.columns([2, 1])
with left:
    st.subheader("الأمر الطبيعي")
    st.caption("اكتب أمرًا نصيًا؛ لا حاجة لكتابة كود. التنفيذ يتم عبر المحرك المحلي.")
    command = st.text_area("مثال: اجمع الأكواد المسموحة ونظف المكرر", height=120)
    if st.button("تنفيذ الأمر", type="primary"):
        with st.spinner("جاري التنفيذ..."):
            result = execute_text(command)
        if result.get("status") in {"success", "completed", "ok"}:
            st.success("تم التنفيذ حسب النتيجة التي أعادها المحرك.")
        else:
            st.error("لم يكتمل التنفيذ.")
        st.json(result)

with right:
    st.subheader("الحالة الفعلية")
    st.write(f"المحرك: **{'متصل' if running else 'غير متصل'}**")
    st.write(f"قاعدة البيانات: **{'متصلة' if DB_READY else 'غير متصلة'}**")
    st.write("لا يتم اعتبار أي مزود متصلًا إلا إذا سجله المحرك ببيانات حقيقية.")

st.divider()
tab1, tab2, tab3 = st.tabs(["النشاط", "مزودو API", "السجلات"])
with tab1:
    activity = state.get("activity", [])
    if activity:
        st.dataframe(activity[-50:], use_container_width=True, hide_index=True)
    else:
        st.info("لا يوجد نشاط مسجل من المحرك.")
with tab2:
    if providers:
        st.dataframe(providers, use_container_width=True, hide_index=True)
    else:
        st.info("لا يوجد مزودون مسجلون فعليًا.")
with tab3:
    events = get_recent_events(100) if DB_READY else []
    if events:
        st.json(events)
    elif LOG_FILE.exists():
        st.code(LOG_FILE.read_text(encoding="utf-8", errors="replace")[-10000:])
    else:
        st.info("لا توجد سجلات.")

if st.button("↻ تحديث"):
    st.rerun()
