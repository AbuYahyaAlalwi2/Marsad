import os, json, time, requests, streamlit as st
from datetime import datetime
from huggingface_hub import HfApi

st.set_page_config(page_title="MARSAD", page_icon="◈", layout="wide", initial_sidebar_state="expanded")

RAILWAY_URL = "https://marsad-sandbox-production.up.railway.app"
HF_REPO = "AbuYahyaAlalwi2/marsad-security-dataset-v1"
HF_TOKEN = os.environ.get("HF_TOKEN", "")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&display=swap');
html, body, [class*="css"] { font-family: 'Cairo', sans-serif; }
.stApp { background: #050b18; color: #e8eefc; }
.block-container { max-width: 1500px; padding-top: 1rem; padding-bottom: 2rem; }
[data-testid="stSidebar"] { background: #07101f; border-left: 1px solid #182640; }
.metric { background: #0a1528; border: 1px solid #182944; border-radius: 14px; padding: 16px; text-align: center; }
.metric-title { color: #8b9ab5; font-size: 13px; }
.metric-value { color: #f3f7ff; font-size: 28px; font-weight: 800; margin-top: 3px; }
.status { text-align: center; padding: 9px; border-radius: 10px; margin: 8px 0 18px; font-weight: 700; font-size: 13px; }
.online { color: #35e58b; background: rgba(16,185,129,.08); border: 1px solid rgba(16,185,129,.25); }
.offline { color: #ff6677; background: rgba(239,68,68,.08); border: 1px solid rgba(239,68,68,.25); }
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=30)
def get_health():
    try: 
        resp = requests.get(f"{RAILWAY_URL}/health", timeout=5)
        return resp.json() if resp.status_code == 200 else {"status": "offline"}
    except: 
        return {"status": "offline"}

@st.cache_data(ttl=300)
def get_hf_stats():
    try:
        api = HfApi(token=HF_TOKEN)
        info = api.dataset_info(HF_REPO)
        return {"size": info.size_in_bytes / 1024, "files": len(api.list_repo_files(HF_REPO))}
    except: 
        return {"size": 0, "files": 0}

# --- Sidebar ---
with st.sidebar:
    st.markdown('<div style="text-align:center; padding: 20px 0;"><div style="font-size:35px; font-weight:800; color:#b78cff;">◈</div><div style="font-size:25px; font-weight:800; letter-spacing:4px; margin-top:8px;">MARSAD</div><div style="color:#7e8ca7; font-size:12px;">منصة المراقبة الذكية الحية</div></div>', unsafe_allow_html=True)
    health = get_health()
    is_online = health.get("status") == "operational"
    st.markdown(f'<div class="status {"online" if is_online else "offline"}">● {"النظام يعمل" if is_online else "النظام متوقف"}</div>', unsafe_allow_html=True)
    st.caption(f"آخر تحديث: {datetime.now().strftime('%H:%M:%S')}")
    if st.button("↻ تحديث البيانات", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# --- Main Dashboard ---
st.title("لوحة التحكم المباشرة")
stats = get_hf_stats()

m1, m2, m3, m4 = st.columns(4)
with m1:
    st.markdown(f'<div class="metric"><div class="metric-title">حالة المنسق</div><div class="metric-value">{"🟢 Online" if is_online else "🔴 Offline"}</div></div>', unsafe_allow_html=True)
with m2:
    st.markdown(f'<div class="metric"><div class="metric-title">البوابات الأمنية</div><div class="metric-value">{"✅ مفعلة" if health.get("gates_loaded") else "❌ معطلة"}</div></div>', unsafe_allow_html=True)
with m3:
    st.markdown(f'<div class="metric"><div class="metric-title">حجم بيانات HF</div><div class="metric-value">{stats["size"]:.2f} KB</div></div>', unsafe_allow_html=True)
with m4:
    st.markdown(f'<div class="metric"><div class="metric-title">ملفات HF</div><div class="metric-value">{stats["files"]}</div></div>', unsafe_allow_html=True)

st.divider()
st.subheader("تفاصيل النظام الحية من Railway")
st.json(health)

st.markdown("---")
st.caption("MARSAD • القيم تُقرأ مباشرة من خادم Railway ومستودع Hugging Face (لا بيانات وهمية أو محلية)")
