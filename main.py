"""
CYBERGUARD OS — النظام الذكي للمبرمجين
"""
import streamlit as st
import time
import os
import threading
import logging

# إعداد تسجيل الأحداث
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# تهيئة قاعدة البيانات أولاً (قبل أي استدعاء آخر)
# ============================================================================

# استيراد _ensure_db أولاً لضمان تهيئة قاعدة البيانات
from db import (
    _ensure_db,
    init_db,
    get_recent_events,
    get_memory_size_gb,
    get_database_stats,
    insert_conversation,
    get_conversation_history,
    list_providers,
)

# ضمان تهيئة قاعدة البيانات قبل أي شيء آخر
_ensure_db()

# الآن استيراد باقي الوحدات (بعد ضمان تهيئة قاعدة البيانات)
from core.brain import brain
from core.memory import memory
from chat.interface import chat
from agents.hierarchy import hierarchy
from agents.parasite import parasite_swarm
from merge.omni_merger import merger
from collect.multi_platform import collector
from collect.datasets import dataset_collector
from providers.llm_providers import llm_providers
from providers.code_providers import code_providers
from plugins.loader import plugin_loader
from keep_alive import start_keep_alive, stop_keep_alive
from config import KEEP_ALIVE_INTERVAL, DATASET_PLATFORMS, API_PROVIDERS, SOURCE_PLATFORMS

# استيراد systems الجديدة
try:
    from key_manager import key_manager, key_collector_proxy
    logger.info("Key Manager loaded successfully")
except Exception as e:
    logger.warning(f"Failed to load Key Manager: {e}")
    key_manager = None

try:
    from vpn_config import vpn_manager
    logger.info("VPN Manager loaded successfully")
except Exception as e:
    logger.warning(f"Failed to load VPN Manager: {e}")
    vpn_manager = None


# ============================================================================
# تهيئة النظام (بعد ضمان تهيئة قاعدة البيانات)
# ============================================================================

# استخدام lock لتجنب race condition
_init_lock = threading.Lock()
_initialized = False

def safe_init():
    """تهيئة آمنة للنظام"""
    global _initialized
    
    if _initialized:
        return
    
    with _init_lock:
        if _initialized:
            return
        
        try:
            # تأكد من تهيئة قاعدة البيانات
            _ensure_db()
            
            # تهيئة قاعدة البيانات
            init_db()
            
            # تهيئة الذاكرة
            memory.start_monitoring()
            
            # تهيئة التسلسل الهرمي
            hierarchy.initialize()
            
            # تحميل الإضافات
            plugin_loader.load_all()
            
            # تهيئة VPN إذا كان متوفر
            if os.environ.get("CG_ENABLE_VPN", "false").lower() == "true" and vpn_manager:
                try:
                    vpn_manager.connect_vpn()
                    logger.info("VPN connected successfully")
                except Exception as e:
                    logger.warning(f"VPN connection failed: {e}")
            
            _initialized = True
            logger.info("CYBERGUARD OS initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing CYBERGUARD OS: {e}")
            raise

# تهيئة آمنه
safe_init()

# تهيئة keep alive
if os.environ.get("CG_ENABLE_KEEP_ALIVE", "true").lower() == "true":
    start_keep_alive()


# ============================================================================
# إعداد Streamlit
# ============================================================================

st.set_page_config(
    page_title="CYBERGUARD OS",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# عنوان النظام
st.title("🛡️ CYBERGUARD OS — النظام الذكي للمبرمجين")
st.markdown("---")

# Sidebar
with st.sidebar:
    st.header("🌱 لوحة التحكم")
    
    # إحصائيات سريعة
    st.subheader("📊 إحصائيات النظام")
    db_stats = get_database_stats()
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("قاعدة البيانات", f"{db_stats.get('db_size_mb', 0):.2f} MB")
        st.metric("الذاكرة", f"{get_memory_size_gb():.2f} GB")
    with col2:
        st.metric("المحادثات", db_stats.get("conversations_count", 0))
        st.metric("البيانات", db_stats.get("datasets_count", 0))
    
    # أوامر سريعة
    st.subheader("⚡ أوامر سريعة")
    command = st.text_input("أدخل أمر:", key="sidebar_command")
    if st.button("تنفيذ", key="sidebar_execute") and command:
        try:
            result = chat.handle(command)
            st.json(result)
            # حفظ في قاعدة البيانات
            if result.get("status") == "success":
                insert_conversation(
                    session_id="sidebar",
                    user_input=command,
                    response=str(result),
                    provider="chat",
                    model="default"
                )
        except Exception as e:
            st.error(f"خطأ: {e}")

# Tabs الرئيسية
tabs = st.tabs([
    "💬 الدردشة", "🤖 الوكلاء", "🧠 الدمج", "📥 الجمع",
    "📊 البيانات", "🔌 API", "💾 الذاكرة", "📋 السجلات",
    "🔒 إدارة المفاتيح", "🌐 VPN"
])

# --- Tab 1: الدردشة ---
with tabs[0]:
    st.header("💬 الدردشة الذكية")
    
    # عرض تاريخ المحادثات
    st.subheader("📜 تاريخ المحادثات")
    conversations = get_conversation_history("main", limit=10)
    for conv in conversations:
        with st.expander(f"{conv['created_at']} - {conv['user_input'][:50]}..."):
            st.text(f"Input: {conv['user_input']}")
            st.text(f"Response: {conv['response'][:200]}...")
    
    # واجهة الدردشة
    st.subheader("💬 واجهة الدردشة")
    user_input = st.text_input("أدخل رسالتك:", key="chat_input")
    if st.button("إرسال", key="chat_send") and user_input:
        with st.spinner("جاري المعالجة..."):
            try:
                result = chat.handle(user_input)
                
                # عرض النتيجة
                if result.get("status") == "success":
                    st.success("✅ تم المعالجة بنجاح")
                    st.code(result.get("response", ""), language="python")
                else:
                    st.error(f"❌ خطأ: {result.get('error', 'خطأ غير معروف')}")
                
                # حفظ في قاعدة البيانات
                insert_conversation(
                    session_id="main",
                    user_input=user_input,
                    response=str(result),
                    provider="chat",
                    model="default"
                )
            except Exception as e:
                st.error(f"❌ خطأ: {e}")

# --- Tab 2: الوكلاء ---
with tabs[1]:
    st.header("🤖 إدارة الوكلاء")
    
    # إحصائيات الوكلاء
    st.subheader("📊 إحصائيات الوكلاء")
    
    from db import count_agents_by_level
    levels = [1, 2, 3, 4]
    cols = st.columns(4)
    
    for i, level in enumerate(levels):
        with cols[i]:
            count = count_agents_by_level(level)
            st.metric(f"المستوى {level}", count)
    
    # إدارة الوكلاء
    st.subheader("🎯 إدارة الوكلاء")
    
    if st.button("🔄 توسيع التسلسل الهرمي"):
        with st.spinner("جاري توسيع التسلسل الهرمي..."):
            try:
                result = hierarchy.expand(hierarchy.root_id, target_agents=10000)
                st.success("✅ تم توسيع التسلسل الهرمي")
                st.json(result)
            except Exception as e:
                st.error(f"❌ خطأ: {e}")
    
    # عرض إحصائيات الوكلاء
    try:
        agent_stats = hierarchy.get_stats()
        st.json(agent_stats)
    except Exception as e:
        st.warning(f"لم يتم الحصول على إحصائيات الوكلاء: {e}")

# --- Tab 3: الدمج ---
with tabs[2]:
    st.header("🧠 دمج النماذج")
    
    st.subheader("📋 خطة الدمج")
    try:
        merge_plan = merger.get_merge_plan()
        st.json(merge_plan)
    except Exception as e:
        st.warning(f"لم يتم الحصول على خطة الدمج: {e}")
    
    if st.button("🚀 بدء الدمج"):
        with st.spinner("جاري دمج النماذج..."):
            try:
                result = merger.merge_all()
                if result.get("status") == "success":
                    st.success("✅ تم دمج النماذج بنجاح")
                else:
                    st.error(f"❌ خطأ: {result.get('error', 'خطأ غير معروف')}")
                st.json(result)
            except Exception as e:
                st.error(f"❌ خطأ: {e}")

# --- Tab 4: الجمع ---
with tabs[3]:
    st.header("📥 جمع البيانات")
    
    st.subheader("🔍 جمع من المنصات")
    
    # اختيار المنصة
    platform_options = list(DATASET_PLATFORMS.keys())
    selected_platform = st.selectbox("اختر المنصة:", platform_options)
    
    # إعدادات البحث
    col1, col2 = st.columns(2)
    with col1:
        query = st.text_input("استعلام البحث:", "security vulnerability")
    with col2:
        limit = st.slider("عدد النتائج:", 1, 100, 10)

    if st.button("🔎 بدأ الجمع"):
        with st.spinner(f"جاري جمع البيانات من {selected_platform}..."):
            try:
                results = collector.collect_all(query, limit)
                st.json(results)
            except Exception as e:
                st.error(f"❌ خطأ: {e}")
    
    st.markdown("---")
    
    # تنزيل datasets
    st.subheader("📦 تنزيل datasets")
    if st.button("📥 تنزيل datasets المعلقة"):
        with st.spinner("جاري تنزيل datasets..."):
            try:
                result = dataset_collector.download_pending()
                st.json(result)
            except Exception as e:
                st.error(f"❌ خطأ: {e}")
    
    # إحصائيات datasets
    try:
        ds_stats = dataset_collector.get_dataset_stats()
        st.json(ds_stats)
    except Exception as e:
        st.warning(f"لم يتم الحصول على إحصائيات datasets: {e}")

# --- Tab 5: البيانات ---
with tabs[4]:
    st.header("📊 إدارة البيانات")
    
    st.subheader("🔍 بحث في البيانات")
    search_query = st.text_input("أدخل كلمة البحث:", key="data_search")
    if st.button("🔎 بحث"):
        st.info("سيتم إضافة ميزة البحث قريباً")
    
    st.markdown("---")
    
    # عرض datasets
    st.subheader("📦 datasets المتاحة")
    try:
        from db import get_pending_datasets
        datasets = get_pending_datasets(50)
        
        for ds in datasets:
            with st.expander(f"{ds['name']} - {ds['platform']}"):
                st.write(f"**الوصف:** {ds.get('description', 'لا يوجد وصف')}")
                st.write(f"**الرابط:** {ds.get('url', 'لا يوجد رابط')}")
                st.write(f"**الحجم:** {ds.get('size_mb', 0):.2f} MB")
    except Exception as e:
        st.warning(f"لم يتم عرض datasets: {e}")

# --- Tab 6: API ---
with tabs[5]:
    st.header("🔌 واجهة API")
    
    st.subheader("📋 موفرو API")
    try:
        all_providers = list_providers()
        st.write(f"عدد موفري API: {len(all_providers)}")
        
        # فلترة حسب الفئة
        category_filter = st.selectbox(
            "فلترة حسب الفئة:",
            ["جميع", "llm", "code", "embedding"]
        )
        
        if category_filter != "جميع":
            filtered_providers = [p for p in all_providers if p['category'] == category_filter]
        else:
            filtered_providers = all_providers
        
        st.write(f"عدد النتائج: {len(filtered_providers)}")
        
        for provider in filtered_providers:
            with st.expander(f"{provider['name']} ({provider['provider_key']})"):
                st.json(provider)
    except Exception as e:
        st.warning(f"لم يتم عرض موفري API: {e}")
        all_providers = []
    
    st.markdown("---")
    
    # اختبار توليد نصوص
    st.subheader("✍️ اختبار توليد نصوص")
    llm_prompt = st.text_area("النص:", key="api_llm_prompt")
    llm_provider = st.selectbox(
        "مزود LLM:",
        [p['provider_key'] for p in all_providers if p['category'] == 'llm']
    )
    
    if st.button("🚀 توليد"):
        with st.spinner("جاري التوليد..."):
            try:
                result = llm_providers.generate(llm_prompt)
                if result.get("status") == "success":
                    st.success("✅ تم التوليد بنجاح")
                    st.text_area("النتيجة:", result.get("text", ""), height=200)
                    
                    insert_conversation(
                        session_id="api_test",
                        user_input=llm_prompt,
                        response=result.get("text", ""),
                        provider=result.get("provider", "unknown"),
                        model=result.get("model", "unknown")
                    )
                else:
                    st.error(f"❌ خطأ: {result.get('reason', 'خطأ غير معروف')}")
            except Exception as e:
                st.error(f"❌ خطأ: {e}")
    
    st.markdown("---")
    
    # اختبار توليد كود
    st.subheader("💻 اختبار توليد كود")
    code_prompt = st.text_area("الوصف:", key="api_code_prompt")
    code_language = st.selectbox("اللغة:", ["python", "javascript", "bash", "java", "c++"])
    
    if st.button("🚀 توليد الكود"):
        with st.spinner("جاري توليد الكود..."):
            try:
                result = code_providers.generate_code(code_prompt, language=code_language)
                if result.get("status") == "success":
                    st.success("✅ تم توليد الكود بنجاح")
                    st.code(result.get("code", ""), language=code_language)
                    
                    insert_conversation(
                        session_id="api_code_test",
                        user_input=code_prompt,
                        response=result.get("code", ""),
                        provider=result.get("provider", "unknown"),
                        model=result.get("model", "unknown")
                    )
                else:
                    st.error(f"❌ خطأ: {result.get('reason', 'خطأ غير معروف')}")
            except Exception as e:
                st.error(f"❌ خطأ: {e}")

# --- Tab 7: الذاكرة ---
with tabs[6]:
    st.header("💾 إدارة الذاكرة")
    
    # إحصائيات الذاكرة
    current_gb = get_memory_size_gb()
    st.metric("حجم الذاكرة", f"{current_gb:.2f} GB")
    
    # شريط التقدم
    progress = min(1.0, current_gb / 10.0)
    st.progress(progress)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("مستخدم", f"{current_gb:.2f} GB")
    with col2:
        st.metric("متبقي", f"{10.0 - current_gb:.2f} GB")
    with col3:
        st.metric("النسبة", f"{progress * 100:.1f}%")
    
    st.markdown("---")
    
    # عمليات الذاكرة
    st.subheader("⚙️ عمليات الذاكرة")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 معالجة الذاكرة"):
            try:
                memory._auto_process()
                st.success("✅ تم بدء معالجة الذاكرة")
            except Exception as e:
                st.error(f"❌ خطأ: {e}")
    
    with col2:
        if st.button("🗑️ مسح الذاكرة المدربة"):
            try:
                from db import clear_trained_memory
                clear_trained_memory()
                st.success("✅ تم مسح الذاكرة المدربة")
            except Exception as e:
                st.error(f"❌ خطأ: {e}")
    
    st.markdown("---")
    
    st.subheader("📊 إحصائيات الذاكرة")
    try:
        from db import get_untrained_memory
        untrained = get_untrained_memory()
        st.write(f"**عدد السجلات غير المدربة:** {len(untrained)}")
    except Exception as e:
        st.warning(f"لم يتم عرض إحصائيات الذاكرة: {e}")

# --- Tab 8: السجلات ---
with tabs[7]:
    st.header("📋 السجلات")
    
    # فلترة السجلات
    col1, col2 = st.columns(2)
    with col1:
        limit = st.slider("عدد السجلات:", 10, 200, 50, key="events_limit")
    with col2:
        channel_filter = st.selectbox(
            "فلترة حسب القناة:",
            ["جميع"] + list(set(e['channel'] for e in get_recent_events(100)))
        )

    events = get_recent_events(limit)
    
    if channel_filter != "جميع":
        events = [e for e in events if e['channel'] == channel_filter]
    
    st.write(f"**عدد السجلات المعروضة:** {len(events)}")
    
    # عرض السجلات
    for event in events:
        with st.expander(f"📝 {event['channel']} - {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(event['created_at']))}"):
            try:
                import json
                payload = json.loads(event['payload'])
                st.json(payload)
            except Exception:
                st.text(event['payload'])

# --- Tab 9: إدارة المفاتيح ---
with tabs[8]:
    st.header("🔒 إدارة المفاتيح")
    
    if key_manager:
        st.subheader("📋 قائمة المفاتيح")
        
        try:
            keys = key_manager.list_keys()
            if keys:
                st.json(keys)
            else:
                st.info("لا توجد مفاتيح مخزنة")
        except Exception as e:
            st.error(f"❌ خطأ في عرض المفاتيح: {e}")
        
        st.markdown("---")
        
        st.subheader("➕ إضافة مفتاح جديد")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            new_key_name = st.text_input("اسم المفتاح:", key="new_key_name")
        with col2:
            new_key_value = st.text_input("قيمة المفتاح:", key="new_key_value", type="password")
        with col3:
            new_key_type = st.selectbox("نوع المفتاح:", ["api_key", "token", "password"], key="new_key_type")
        
        if st.button("💾 حفظ المفتاح"):
            if new_key_name and new_key_value:
                try:
                    success = key_manager.set_key(
                        new_key_name,
                        new_key_value,
                        new_key_type
                    )
                    if success:
                        st.success("✅ تم حفظ المفتاح بنجاح")
                    else:
                        st.error("❌ فشل حفظ المفتاح")
                except Exception as e:
                    st.error(f"❌ خطأ: {e}")
            else:
                st.warning("يرجى إدخال اسم وقيمة المفتاح")
        
        st.markdown("---")
        
        st.subheader("🗑️ حذف مفتاح")
        delete_key_name = st.text_input("اسم المفتاح للحذف:", key="delete_key_name")
        if st.button("🗑️ حذف"):
            if delete_key_name:
                try:
                    success = key_manager.delete_key(delete_key_name)
                    if success:
                        st.success("✅ تم حذف المفتاح بنجاح")
                    else:
                        st.error("❌ فشل حذف المفتاح")
                except Exception as e:
                    st.error(f"❌ خطأ: {e}")
            else:
                st.warning("يرجى إدخال اسم المفتاح")
        
        st.markdown("---")
        
        st.subheader("🔍 اختبار مفتاح")
        test_key_name = st.selectbox("اختر المفتاح:", list(keys.keys()) if keys else [], key="test_key_name")
        if st.button("🧪 اختبار"):
            if test_key_name:
                try:
                    key_value = key_manager.get_key(test_key_name)
                    if key_value:
                        is_valid = key_manager.validate_key(test_key_name, key_value)
                        if is_valid:
                            st.success("✅ المفتاح صالح")
                        else:
                            st.error("❌ المفتاح غير صالح")
                    else:
                        st.warning("لم يتم العثور على المفتاح")
                except Exception as e:
                    st.error(f"❌ خطأ: {e}")
    else:
        st.warning("نظام إدارة المفاتيح غير متوفر")

# --- Tab 10: VPN ---
with tabs[9]:
    st.header("🌐 إدارة VPN")
    
    if vpn_manager:
        st.subheader("📊 حالة VPN")
        
        try:
            status = vpn_manager.get_status()
            st.json(status)
        except Exception as e:
            st.error(f"❌ خطأ في الحصول على حالة VPN: {e}")
        
        st.markdown("---")
        
        st.subheader("🔗 اتصال VPN")
        
        # اختيار تكوين VPN
        vpn_configs = list(vpn_manager.vpn_configs.keys())
        if vpn_configs:
            selected_vpn = st.selectbox("اختر تكوين VPN:", vpn_configs)
            
            if st.button("🔗 الاتصال"):
                with st.spinner("جاري الاتصال..."):
                    try:
                        success = vpn_manager.connect_vpn(selected_vpn)
                        if success:
                            st.success("✅ تم الاتصال ب VPN بنجاح")
                        else:
                            st.error("❌ فشل الاتصال ب VPN")
                    except Exception as e:
                        st.error(f"❌ خطأ: {e}")
            
            if st.button("🔓 الفصل"):
                try:
                    success = vpn_manager.disconnect_vpn()
                    if success:
                        st.success("✅ تم الفصل من VPN بنجاح")
                    else:
                        st.error("❌ فشل الفصل من VPN")
                except Exception as e:
                    st.error(f"❌ خطأ: {e}")
        else:
            st.info("لا توجد تكوينات VPN متاحة")
        
        st.markdown("---")
        
        st.subheader("🌍 التبديل بين الدول")
        
        from vpn_config import CountryCode
        country_options = [c.value for c in CountryCode]
        selected_country = st.selectbox("اختر الدولة:", country_options)
        
        if st.button("🔄 التبديل"):
            try:
                country_code = CountryCode[selected_country.upper()]
                success = vpn_manager.switch_country(country_code)
                if success:
                    st.success(f"✅ تم التبديل إلى {selected_country}")
                else:
                    st.error(f"❌ فشل التبديل إلى {selected_country}")
            except Exception as e:
                st.error(f"❌ خطأ: {e}")
        
        st.markdown("---")
        
        st.subheader("🔄 إدارة پروكسي")
        
        # عرض قائمة پروكسي
        proxies = vpn_manager.proxy_list
        if proxies:
            st.write(f"عدد پروكسيات: {len(proxies)}")
            
            # اختيار پروكسي
            proxy_options = [f"{p.host}:{p.port} ({p.country or 'N/A'})" for p in proxies]
            selected_proxy = st.selectbox("اختر پروكسي:", proxy_options)
            
            if st.button("🔧 تعيين پروكسي"):
                try:
                    proxy_index = proxy_options.index(selected_proxy)
                    success = vpn_manager.set_proxy(proxy_index=proxy_index)
                    if success:
                        st.success("✅ تم تعيين پروكسي بنجاح")
                    else:
                        st.error("❌ فشل تعيين پروكسي")
                except Exception as e:
                    st.error(f"❌ خطأ: {e}")
            
            if st.button("🔄 تدوير پروكسي"):
                try:
                    success = vpn_manager.rotate_proxy()
                    if success:
                        st.success("✅ تم تدوير پروكسي بنجاح")
                    else:
                        st.error("❌ فشل تدوير پروكسي")
                except Exception as e:
                    st.error(f"❌ خطأ: {e}")
            
            if st.button("🗑️ مسح پروكسي"):
                vpn_manager.clear_proxy()
                st.success("✅ تم مسح پروكسي")
        else:
            st.info("لا توجد پروكسيات متاحة")
        
        st.markdown("---")
        
        st.subheader("🌐 معلومات الشبكة")
        
        if st.button("🔍 الحصول على IP عام"):
            try:
                ip = vpn_manager.get_public_ip()
                if ip:
                    st.code(f"IP العام: {ip}")
                else:
                    st.warning("لم يتم الحصول على IP")
            except Exception as e:
                st.error(f"❌ خطأ: {e}")
        
        if st.button("📍 الحصول على موقع جغرافي"):
            try:
                location = vpn_manager.get_geo_location()
                if location:
                    st.json(location)
                else:
                    st.warning("لم يتم الحصول على الموقع")
            except Exception as e:
                st.error(f"❌ خطأ: {e}")
    else:
        st.warning("نظام VPN غير متوفر")

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #888; padding: 2rem 0;'>
    <p><strong>CYBERGUARD OS</strong> - النظام الذكي للمبرمجين</p>
    <p>جميع الحقوق محفوظة | 2024</p>
</div>
""", unsafe_allow_html=True)
