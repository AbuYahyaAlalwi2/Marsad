import os
import json
import requests
from datetime import datetime
import streamlit as st

st.set_page_config(page_title="MARSAD Live", page_icon="◈", layout="wide")

# ─── الاتصال بـ Railway ──────────────────────────────────────────────────────
RAILWAY_URL = os.environ.get("RAILWAY_URL", "https://marsad-sandbox-production.up.railway.app")
HF_REPO = "AbuYahyaAlalwi2/marsad-security-dataset-v1"
HF_TOKEN = os.environ.get("HF_TOKEN")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;700&display=swap');
html, body, [class*="css"] { font-family: 'Cairo', sans-serif; }
.stApp { background: #050b18; color: #e8eefc; }
.metric-card { background: #0a1528; border: 1px solid #182944; border-radius: 12px; padding: 15px; }
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=30)
def get_system_health():
    try:
        resp = requests.get(f"{RAILWAY_URL}/health", timeout=5)
        return resp.json() if resp.status_code == 200 else {}
    except:
        return {"status": "offline"}

@st.cache_data(ttl=300)
def get_dataset_stats():
    try:
        from huggingface_hub import HfApi
        api = HfApi(token=HF_TOKEN)
        info = api.dataset_info(HF_REPO)
        return {
            "size": info.size_in_bytes,
            "last_modified": info.lastModified,
            "files": len(api.list_repo_files(HF_REPO))
        }
    except:
        return {"size": 0, "files": 0}

st.title("◈ MARSAD Live Monitor")
st.caption(f"نظام المراقبة المباشر | آخر تحديث: {datetime.now().strftime('%H:%M:%S')}")

health = get_system_health()
stats = get_dataset_stats()

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.metric("حالة المنسق", "🟢 Online" if health.get("status") == "operational" else "🔴 Offline")
    st.markdown('</div>', unsafe_allow_html=True)

with col2:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.metric("البوابات النشطة", "✅ مفعلة" if health.get("gates_loaded") else "❌ معطلة")
    st.markdown('</div>', unsafe_allow_html=True)

with col3:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.metric("حجم البيانات", f"{stats['size'] / 1024:.2f} KB")
    st.markdown('</div>', unsafe_allow_html=True)

with col4:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.metric("ملفات HF", stats['files'])
    st.markdown('</div>', unsafe_allow_html=True)

st.divider()
st.subheader("تفاصيل النظام")
st.json(health)

st.caption("MARSAD • بيانات حية من Railway و Hugging Face")
