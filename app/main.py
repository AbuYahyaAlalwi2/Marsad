"""
مرصد (Marsad) — مركز قيادة وكلاء الذكاء الاصطناعي.
الاسم الجديد بدل Delfin/Dolphin OS — "مرصد" لأنه يراقب وينسّق وكلاء
متعددين، ويطابق مفهوم الشعار (نبضة رادار/سونار).
"""

import streamlit as st
import time

from db import (
    init_db, log_event, create_agent_group, list_agent_groups,
    insert_sample, list_recent_samples, sample_counts_by_status, recent_events,
)
from filters import run_quality_gate, sha256_of
from sandbox import run_code_in_sandbox
from robots_check import check_allowed
from gemini_supervisor import get_plan

st.set_page_config(page_title="مرصد — Marsad", page_icon="app/logo.svg", layout="wide")
init_db()

DEFAULT_GROUPS = {
    "Research": ["Data Scraper", "Code Harvester"],
    "Engineering": ["Code Builder", "Reverse Engineer"],
    "Governance": ["QA & Constitutional Evaluator", "Dedupe & Indexer"],
    "Learning": ["Training Orchestrator"],
    "Reliability": ["Agent Hospital"],
}


def seed_default_groups_if_empty():
    if not list_agent_groups():
        for category, agents in DEFAULT_GROUPS.items():
            for agent_type in agents:
                create_agent_group(name=agent_type, category=category, agent_type=agent_type)


seed_default_groups_if_empty()

st.title("🛰️ مرصد — مركز قيادة وكلاء الذكاء الاصطناعي")
st.caption("Marsad Command Center — سابقاً Delfin OS")

tab_map, tab_mission, tab_quality, tab_events = st.tabs(
    ["🗺️ خريطة الوكلاء", "🎯 Mission Control", "🧪 بوابة الجودة", "📜 سجل الأحداث"]
)

# ------------------------------------------------------------------
# تبويب 1: خريطة الوكلاء كعقد (Node Graph) + Supervisor Chat
# ------------------------------------------------------------------
with tab_map:
    col_chat, col_map = st.columns([1, 1.3])

    with col_chat:
        st.subheader("💬 Supervisor Chat (Gemini)")
        user_command = st.text_area(
            "اكتب أمرك بالعربية أو الإنجليزية",
            placeholder="مثال: أنشئ 5 نسخ من وكيل QA باسم فاحصي المكتبة",
        )
        if st.button("تحليل الأمر → اقترح خطة", type="primary"):
            with st.spinner("Gemini يحلّل الأمر..."):
                plan = get_plan(user_command)
            st.session_state["last_plan"] = plan

        if "last_plan" in st.session_state:
            plan = st.session_state["last_plan"]
            st.markdown("**الخطة المقترحة:**")
            st.json(plan)
            if not plan.get("needs_clarification"):
                if st.button("✅ Approve & Execute (تسجيل فقط — لا تنفيذ آلي مباشر)"):
                    log_event("agent_commands", plan)
                    st.success("تم تسجيل الخطة في سجل الأحداث. التنفيذ الفعلي يحتاج ربط يدوي بالوكيل المختص.")
            else:
                st.warning(plan.get("clarification_question") or "الأمر يحتاج توضيحاً إضافياً.")

    with col_map:
        st.subheader("🗺️ خريطة المجموعات (كل مجموعة = عقدة)")
        groups = list_agent_groups()

        # بناء رسم Graphviz — كل عقدة مجموعة، مرتبطة بعقدة Supervisor المركزية
        dot_lines = [
            "digraph G {",
            'rankdir=TB; bgcolor="transparent";',
            'node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=11, color="#2b6cb0", fillcolor="#ebf8ff"];',
            'Supervisor [shape=doublecircle, fillcolor="#2b6cb0", fontcolor="white", label="Supervisor"];',
        ]
        by_category = {}
        for g in groups:
            by_category.setdefault(g["category"], []).append(g)

        for category, items in by_category.items():
            cat_id = f"cat_{category}"
            count = len(items)
            dot_lines.append(f'{cat_id} [label="{category}\\n({count} وكيل)"];')
            dot_lines.append(f"Supervisor -> {cat_id};")
            for item in items:
                node_id = f"agent_{item['id']}"
                label = f"{item['name']}\\n×{item['clone_count']}"
                color = "#c6f6d5" if item["status"] == "active" else "#fed7d7"
                dot_lines.append(f'{node_id} [label="{label}", fillcolor="{color}"];')
                dot_lines.append(f"{cat_id} -> {node_id};")

        dot_lines.append("}")
        st.graphviz_chart("\n".join(dot_lines))

# ------------------------------------------------------------------
# تبويب 2: Mission Control
# ------------------------------------------------------------------
with tab_mission:
    st.subheader("🎯 إنشاء مهمة جديدة")
    with st.form("new_group_form"):
        c1, c2, c3 = st.columns(3)
        name = c1.text_input("اسم المجموعة")
        category = c2.selectbox("التصنيف", list(DEFAULT_GROUPS.keys()) + ["Custom"])
        clone_count = c3.number_input("عدد النسخ", min_value=1, max_value=10000, value=1)
        agent_type = st.selectbox(
            "نوع الوكيل",
            ["Data Scraper", "Code Harvester", "Code Builder", "Reverse Engineer",
             "QA & Constitutional Evaluator", "Dedupe & Indexer", "Training Orchestrator",
             "Agent Hospital", "Custom"],
        )
        submitted = st.form_submit_button("إنشاء المجموعة")
        if submitted and name:
            gid = create_agent_group(name, category, agent_type, clone_count)
            log_event("agent_commands", {"action": "create_group", "id": gid, "name": name})
            st.success(f"تم إنشاء المجموعة #{gid}")
            st.rerun()

    st.divider()
    st.subheader("🌐 فحص robots.txt قبل الجمع")
    check_url = st.text_input("رابط المصدر المراد فحصه")
    if st.button("فحص") and check_url:
        result = check_allowed(check_url)
        st.json(result)

# ------------------------------------------------------------------
# تبويب 3: بوابة الجودة — اختبار عينة يدوياً
# ------------------------------------------------------------------
with tab_quality:
    st.subheader("🧪 اختبار عينة عبر بوابة الجودة الكاملة")
    sample_text = st.text_area("محتوى العينة (كود أو نص)", height=200)
    c1, c2 = st.columns(2)
    license_str = c1.text_input("الترخيص (مثال: MIT)")
    source_url = c2.text_input("رابط المصدر")

    if st.button("1) فحص بوابة الجودة (أسرار / PII / ترخيص / تكرار)"):
        existing = [s["content"] for s in list_recent_samples(200)]
        ok, reason = run_quality_gate(sample_text, license_str, existing)
        if ok:
            st.success("اجتازت الفحص الأولي — جاهزة لتشغيل sandbox.")
        else:
            st.error(f"مرفوضة: {reason}")
        st.session_state["gate_ok"] = ok
        st.session_state["gate_reason"] = reason

    if st.session_state.get("gate_ok"):
        if st.button("2) شغّل داخل Sandbox معزول (Docker: network=none, 256m, 0.5cpu, 10s)"):
            with st.spinner("تنفيذ داخل الحاوية المعزولة..."):
                result = run_code_in_sandbox(sample_text)
            st.json(result)
            if result["status"] == "passed":
                inserted = insert_sample(
                    sha256_of(sample_text), sample_text, source_url, license_str,
                    "unknown", {"sandbox_run_id": result["run_id"]}, status="pending_review",
                )
                if inserted:
                    st.success("قُبلت العينة — بحالة pending_review، لن تدخل التدريب قبل موافقة بشرية.")
                else:
                    st.warning("العينة مكررة فعلياً (unique constraint على sha256) — لم تُدرج.")
            else:
                st.error(f"رُفضت من sandbox: {result['reject_reason']}")

    st.divider()
    st.subheader("📊 إحصاءات العينات")
    st.json(sample_counts_by_status())
    st.dataframe(list_recent_samples(20))

# ------------------------------------------------------------------
# تبويب 4: سجل الأحداث
# ------------------------------------------------------------------
with tab_events:
    st.subheader("📜 آخر الأحداث")
    for ev in recent_events(50):
        ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ev["created_at"]))
        st.text(f"[{ts}] {ev['channel']}: {ev['payload_json']}")
