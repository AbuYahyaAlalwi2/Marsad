# dashboard.py
# MARSAD — مدمج مع النظام الحقيقي
# Run: streamlit run dashboard.py

import os
import sys
import json
import time
import signal
import socket
import subprocess
from pathlib import Path
from datetime import datetime

import streamlit as st

try:
    import psutil
except ImportError:
    psutil = None

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
os.chdir(BASE_DIR)

STATE_FILE = Path(os.getenv("MARSAD_STATE_FILE", BASE_DIR / "marsad_state.json"))
CHAT_URL = os.getenv("MARSAD_CHAT_URL", "").strip()
START_COMMAND = os.getenv("MARSAD_START_COMMAND", f"{sys.executable} {BASE_DIR / 'autorun.py'}").strip()
STOP_COMMAND = os.getenv("MARSAD_STOP_COMMAND", "").strip()

# DB init early
try:
    from db import _ensure_db, log_event, get_recent_events, get_memory_size_gb, count_agents_by_level, get_database_stats, list_providers
    _ensure_db()
    HAS_DB = True
except Exception:
    HAS_DB = False
    def log_event(*a, **k): pass
    def get_recent_events(n=20): return []
    def get_memory_size_gb(): return 0.0
    def count_agents_by_level(l): return 0
    def get_database_stats(): return {}
    def list_providers(): return []

try:
    from secure_vault import secure_vault
    HAS_VAULT = True
except Exception:
    HAS_VAULT = False
    secure_vault = None

try:
    from marsad_state_writer import write_state, mark_running, update_from_db
    HAS_WRITER = True
except Exception:
    HAS_WRITER = False

st.set_page_config(
    page_title="MARSAD",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&display=swap');
html, body, [class*="css"] { font-family: "Cairo", sans-serif; }
.stApp { background: #050b18; color: #e8eefc; }
.block-container { max-width: 1500px; padding-top: 1rem; padding-bottom: 2rem; }
[data-testid="stSidebar"] { background: #07101f; border-left: 1px solid #182640; }
.card {
    background: linear-gradient(145deg, #0a1528, #08111f);
    border: 1px solid #182944; border-radius: 14px; padding: 18px; min-height: 100%;
}
.metric {
    background: #0a1528; border: 1px solid #182944; border-radius: 14px; padding: 16px;
}
.metric-title { color: #8b9ab5; font-size: 13px; }
.metric-value { color: #f3f7ff; font-size: 28px; font-weight: 800; margin-top: 3px; }
.muted { color: #7e8ca7; font-size: 12px; }
.brand { text-align: center; padding: 8px 0 22px; }
.brand-icon {
    width: 72px; height: 72px; margin: auto; border-radius: 20px;
    display: flex; align-items: center; justify-content: center;
    font-size: 35px; font-weight: 800; color: #b78cff;
    border: 1px solid #6334b8;
    background: radial-gradient(circle, #24104e, #0b1425 68%);
    box-shadow: 0 0 30px rgba(139,92,246,.18);
}
.brand-name { font-size: 25px; font-weight: 800; letter-spacing: 4px; margin-top: 8px; }
.status { text-align: center; padding: 9px; border-radius: 10px; margin: 8px 0 18px; font-weight: 700; font-size: 13px; }
.online { color: #35e58b; background: rgba(16,185,129,.08); border: 1px solid rgba(16,185,129,.25); }
.offline { color: #ff6677; background: rgba(239,68,68,.08); border: 1px solid rgba(239,68,68,.25); }
.chat-box { background: #081323; border: 1px solid #1b2b47; border-radius: 14px; padding: 14px; }
hr { border-color: #182944; }
</style>
""", unsafe_allow_html=True)

def load_state():
    if not STATE_FILE.exists():
        return {}
    try:
        with STATE_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def is_autorun_alive():
    pid_file = BASE_DIR / "data" / "autorun.pid"
    if not pid_file.exists():
        return False
    try:
        pid = int(pid_file.read_text().strip())
        if psutil:
            return psutil.pid_exists(pid)
        os.kill(pid, 0)
        return True
    except Exception:
        return False

def start_autorun():
    data_dir = BASE_DIR / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    log_path = data_dir / "autorun.log"
    # kill old if any
    stop_autorun()
    proc = subprocess.Popen(
        [sys.executable, str(BASE_DIR / "autorun.py")],
        stdout=open(log_path, "a"),
        stderr=subprocess.STDOUT,
        cwd=str(BASE_DIR),
        start_new_session=True,
        env={**os.environ, "CG_DB_PATH": str(data_dir / "cyberguard.db")},
    )
    (data_dir / "autorun.pid").write_text(str(proc.pid))
    if HAS_WRITER:
        mark_running(True, f"Autorun started PID {proc.pid}")
        update_from_db()
    log_event("dashboard", {"action": "autorun_start", "pid": proc.pid})
    return True, f"تم التشغيل — PID {proc.pid}"

def stop_autorun():
    pid_file = BASE_DIR / "data" / "autorun.pid"
    if not pid_file.exists():
        if HAS_WRITER:
            mark_running(False, "Stop requested (no pid)")
        return True, "لا توجد عملية نشطة"
    try:
        pid = int(pid_file.read_text().strip())
        os.kill(pid, signal.SIGTERM)
        time.sleep(0.5)
        try:
            os.kill(pid, signal.SIGKILL)
        except Exception:
            pass
        pid_file.unlink(missing_ok=True)
        if HAS_WRITER:
            mark_running(False, f"Stopped PID {pid}")
        log_event("dashboard", {"action": "autorun_stop", "pid": pid})
        return True, f"أُوقف PID {pid}"
    except Exception as e:
        return False, str(e)

def fmt_number(value):
    if value is None:
        return "—"
    try:
        return f"{int(value):,}"
    except Exception:
        return str(value)

def system_metrics():
    if psutil is None:
        return None
    cpu = psutil.cpu_percent(interval=0.15)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage(str(BASE_DIR))
    return {"cpu": cpu, "ram": ram.percent, "disk": disk.percent}

def system_uptime():
    if psutil is None:
        return "—"
    try:
        seconds = int(time.time() - psutil.boot_time())
        days, rem = divmod(seconds, 86400)
        hours, rem = divmod(rem, 3600)
        minutes = rem // 60
        return f"{days}ي {hours}س {minutes}د"
    except Exception:
        return "—"

def send_chat(message):
    if CHAT_URL:
        try:
            import requests
            response = requests.post(CHAT_URL, json={"message": message}, timeout=60)
            response.raise_for_status()
            data = response.json()
            return str(data.get("reply", data.get("response", data)))
        except Exception as exc:
            return f"تعذر الاتصال: {exc}"
    # fallback: local brain if available
    try:
        from core.brain import brain
        return str(brain.think(message) if hasattr(brain, "think") else "المحرك المحلي غير جاهز بالكامل.")
    except Exception:
        return "ضع MARSAD_CHAT_URL أو فعّل core.brain للدردشة الحقيقية."

# refresh real state from DB
if HAS_WRITER and HAS_DB:
    try:
        update_from_db()
    except Exception:
        pass

state = load_state()
metrics = system_metrics()
running = is_autorun_alive() or bool(state.get("running", False))
status_text = "النظام يعمل" if running else "النظام متوقف"
status_class = "online" if running else "offline"

# real counts
try:
    agents_count = sum(count_agents_by_level(i) for i in range(5)) if HAS_DB else state.get("agents")
except Exception:
    agents_count = state.get("agents")
db_stats = get_database_stats() if HAS_DB else {}
providers = list_providers() if HAS_DB else []
vault_platforms = secure_vault.list_platforms() if HAS_VAULT else {}

# ------------------------------------------------------------
# Sidebar
# ------------------------------------------------------------
with st.sidebar:
    st.markdown("""
    <div class="brand">
        <div class="brand-icon">◈</div>
        <div class="brand-name">MARSAD</div>
        <div class="muted">منصة المراقبة الذكية</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f'<div class="status {status_class}">● {status_text}</div>', unsafe_allow_html=True)

    st.caption("التنقل")
    pages = [
        "لوحة التحكم", "المراقبة المباشرة", "الوكلاء", "مصادر البيانات",
        "المهام", "التقارير", "السجلات", "الخزنة", "الدردشة",
    ]
    if "page" not in st.session_state:
        st.session_state.page = "لوحة التحكم"
    for page in pages:
        if st.button(page, use_container_width=True,
                     type="primary" if st.session_state.page == page else "secondary",
                     key=f"nav_{page}"):
            st.session_state.page = page
            st.rerun()

    st.divider()
    st.caption("التحكم — ضغطة واحدة")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🟢 تشغيل دائم", use_container_width=True, key="start"):
            ok, msg = start_autorun()
            st.toast(msg, icon="✅" if ok else "⚠️")
            time.sleep(0.3)
            st.rerun()
    with c2:
        if st.button("🔴 إيقاف", use_container_width=True, key="stop"):
            ok, msg = stop_autorun()
            st.toast(msg, icon="✅" if ok else "⚠️")
            time.sleep(0.3)
            st.rerun()

    st.divider()
    st.caption("موارد الجهاز")
    if metrics:
        st.write(f"CPU — {metrics['cpu']:.0f}%")
        st.progress(min(metrics["cpu"] / 100, 1.0))
        st.write(f"RAM — {metrics['ram']:.0f}%")
        st.progress(min(metrics["ram"] / 100, 1.0))
        st.write(f"Disk — {metrics['disk']:.0f}%")
        st.progress(min(metrics["disk"] / 100, 1.0))
    else:
        st.info("ثبّت psutil لإظهار موارد الجهاز.")
    st.caption(f"وقت تشغيل الجهاز: {system_uptime()}")

# ------------------------------------------------------------
# Header
# ------------------------------------------------------------
top1, top2 = st.columns([5, 1])
with top1:
    st.title(st.session_state.page)
    st.caption(f"آخر تحديث: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} • المضيف: {socket.gethostname()}")
with top2:
    if st.button("↻ تحديث", use_container_width=True):
        if HAS_WRITER:
            update_from_db()
        st.rerun()

page = st.session_state.page

# ------------------------------------------------------------
# Dashboard
# ------------------------------------------------------------
if page == "لوحة التحكم":
    m1, m2, m3, m4 = st.columns(4)
    dashboard_metrics = [
        ("الوكلاء", agents_count if agents_count is not None else state.get("agents")),
        ("المصادر", db_stats.get("datasets_count", state.get("sources"))),
        ("المهام / عينات", db_stats.get("samples_count", state.get("tasks_completed"))),
        ("منصات الخزنة", len(vault_platforms) if vault_platforms else state.get("errors")),
    ]
    for col, (title, value) in zip([m1, m2, m3, m4], dashboard_metrics):
        with col:
            st.markdown(f"""
                <div class="metric">
                    <div class="metric-title">{title}</div>
                    <div class="metric-value">{fmt_number(value)}</div>
                    <div class="muted">من بيانات النظام الفعلية</div>
                </div>
            """, unsafe_allow_html=True)

    st.write("")
    left, center, right = st.columns([1.5, 2, 1.5])

    with left:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("حالة النظام")
        if metrics:
            st.write(f"CPU: **{metrics['cpu']:.0f}%**")
            st.write(f"RAM: **{metrics['ram']:.0f}%**")
            st.write(f"Disk: **{metrics['disk']:.0f}%**")
        st.write(f"الحالة: **{status_text}**")
        st.write(f"الذاكرة: **{get_memory_size_gb():.2f} GB**")
        st.write(f"وقت التشغيل: **{system_uptime()}**")
        st.markdown("</div>", unsafe_allow_html=True)

    with center:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("النشاط المباشر")
        activity = state.get("activity", [])
        events = get_recent_events(8) if HAS_DB else []
        if activity:
            for item in activity[-8:][::-1]:
                if isinstance(item, dict):
                    st.write(f"**{item.get('time', '')}** — {item.get('message', '')}")
                else:
                    st.write(str(item))
        elif events:
            for e in events:
                st.write(f"**{e.get('event_type', '')}** — {str(e.get('payload', ''))[:90]}")
        else:
            st.info("لا توجد أحداث مسجلة. اضغط تشغيل دائم.")
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("المحركات")
        engines = state.get("engines") or {
            "autorun": "on" if running else "off",
            "hierarchy": "active" if agents_count else "idle",
            "vault": "ready" if HAS_VAULT else "missing",
            "db": "ok" if HAS_DB else "fail",
        }
        for name, value in engines.items():
            st.write(f"{name}: **{value}**")
        st.markdown("</div>", unsafe_allow_html=True)

elif page == "المراقبة المباشرة":
    st.subheader("المراقبة المباشرة")
    if metrics:
        a, b, c = st.columns(3)
        a.metric("CPU", f"{metrics['cpu']:.0f}%")
        b.metric("RAM", f"{metrics['ram']:.0f}%")
        c.metric("Disk", f"{metrics['disk']:.0f}%")
    else:
        st.warning("psutil غير مثبت.")
    st.info("قياسات حقيقية من الجهاز فقط.")

elif page == "الوكلاء":
    st.subheader("الوكلاء")
    agents = state.get("agent_list", [])
    if not agents and HAS_DB:
        levels = {f"Level {i}": count_agents_by_level(i) for i in range(5)}
        st.json(levels)
        st.caption(f"الإجمالي: {agents_count}")
    elif agents:
        st.dataframe(agents, use_container_width=True, hide_index=True)
    else:
        st.info("لا توجد بيانات وكلاء. شغّل النظام أولاً.")

elif page == "مصادر البيانات":
    st.subheader("مصادر البيانات")
    sources = state.get("source_list", [])
    if sources:
        st.dataframe(sources, use_container_width=True, hide_index=True)
    else:
        st.write("إحصائيات قاعدة البيانات:")
        st.json(db_stats or {})
        st.info("لا قائمة مصادر مفصّلة بعد — تُملأ عند الجمع.")

elif page == "المهام":
    st.subheader("المهام")
    tasks = state.get("task_list", [])
    if tasks:
        st.dataframe(tasks, use_container_width=True, hide_index=True)
    else:
        st.info("لا مهام مسجلة بعد.")

elif page == "التقارير":
    st.subheader("التقارير")
    reports = state.get("reports", [])
    if reports:
        st.dataframe(reports, use_container_width=True, hide_index=True)
    else:
        st.info("لا تقارير جاهزة.")

elif page == "السجلات":
    st.subheader("السجلات")
    logs = state.get("logs", [])
    events = get_recent_events(100) if HAS_DB else []
    if logs:
        st.code("\n".join(map(str, logs[-200:])), language="text")
    elif events:
        lines = [f"{e.get('created_at','')} | {e.get('event_type','')} | {str(e.get('payload',''))[:120]}" for e in events]
        st.code("\n".join(lines), language="text")
    else:
        st.info("لا سجلات بعد.")
    # autorun log
    logf = BASE_DIR / "data" / "autorun.log"
    if logf.exists():
        st.subheader("سجل Autorun")
        st.code(logf.read_text(encoding="utf-8", errors="ignore")[-4000:], language="text")

elif page == "الخزنة":
    st.subheader("الخزنة الآمنة للمفاتيح")
    if not HAS_VAULT:
        st.error("وحدة secure_vault غير متاحة")
    else:
        platforms = secure_vault.list_platforms()
        st.write(f"**عدد المنصات:** {len(platforms)}")
        st.json(platforms)
        st.subheader("عرض مقنّع")
        st.json(secure_vault.export_masked())
        st.caption("المفاتيح مشفرة في data/secure_vault.enc — لا تُعرض صراحة.")

elif page == "الدردشة":
    st.subheader("محادثة MARSAD")
    st.caption("مرتبطة بالمحرك الحقيقي عند توفر brain أو MARSAD_CHAT_URL.")
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    for msg in st.session_state.chat_messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
    prompt = st.chat_input("اكتب أمراً أو سؤالاً لـ MARSAD")
    if prompt:
        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        with st.spinner("جاري الاتصال..."):
            reply = send_chat(prompt)
        st.session_state.chat_messages.append({"role": "assistant", "content": reply})
        st.rerun()

st.markdown("---")
st.caption("MARSAD • مدمج مع النظام الحقيقي • القيم من DB / vault / psutil / autorun فقط.")
