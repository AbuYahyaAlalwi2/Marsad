/* ============================================================
   MARSAD Dashboard - Real Data Client
   ============================================================ */

const API = "/api";
let donutChart = null;
let activityChart = null;

// ----------------------------------------------------------
// Utilities
// ----------------------------------------------------------
function fmt(n) {
    if (n === null || n === undefined) return "—";
    n = Number(n);
    if (isNaN(n)) return "—";
    if (n >= 1e6) return (n / 1e6).toFixed(1) + "M";
    if (n >= 1e3) return (n / 1e3).toFixed(1) + "K";
    return n.toLocaleString();
}

function setText(id, val) {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
}

function setWidth(id, pct) {
    const el = document.getElementById(id);
    if (el) el.style.width = Math.min(100, Math.max(0, pct)) + "%";
}

function statusClass(s) {
    if (s === "completed") return "task-done";
    if (s === "running") return "task-run";
    return "task-fail";
}

// ----------------------------------------------------------
// Clock
// ----------------------------------------------------------
function tickClock() {
    const now = new Date();
    const time = now.toLocaleTimeString("en-GB", { hour12: false });
    const date = now.toLocaleDateString("en-CA");
    setText("header-clock", `${time} — ${date}`);
}

// ----------------------------------------------------------
// Load Status
// ----------------------------------------------------------
async function loadStatus() {
    try {
        const r = await fetch(`${API}/status`);
        if (!r.ok) throw new Error("status " + r.status);
        const data = await r.json();
        applyStatus(data);
    } catch (e) {
        console.error("[Dashboard] status error:", e);
        const el = document.getElementById("header-status");
        if (el) { el.textContent = "● تعذر الاتصال"; el.style.color = "#ef4444"; }
    }
}

function applyStatus(data) {
    const statusEl = document.getElementById("header-status");
    if (statusEl) {
        if (data.running) {
            statusEl.textContent = "● النظام يعمل";
            statusEl.style.color = "#10b981";
        } else {
            statusEl.textContent = "● النظام متوقف";
            statusEl.style.color = "#ef4444";
        }
    }

    const badge = document.getElementById("status-badge");
    if (badge) {
        badge.textContent = data.running ? "● النظام يعمل" : "● النظام متوقف";
        badge.className = "status-badge " + (data.running ? "status-online" : "status-offline");
    }

    // KPI
    const mrTotal = data.million_runtime?.total_agents || 0;
    const dbTotal = data.agents?.total || 0;
    setText("kpi-agents", fmt(Math.max(mrTotal, dbTotal)));
    setText("kpi-cloud", fmt(data.cloud_stats?.total || 0));
    setText("kpi-sources", fmt(data.sources_count || 0));
    setText("kpi-tasks", fmt(data.tasks?.total || 0));
    setText("kpi-success", (data.tasks?.success_rate || 0).toFixed(1) + "%");
    const _b = data.storage_bytes || 0;
    let _storage;
    if (_b < 1024) _storage = _b.toFixed(0) + " B";
    else if (_b < 1024 * 1024) _storage = (_b / 1024).toFixed(2) + " KB";
    else if (_b < 1024 * 1024 * 1024) _storage = (_b / (1024 * 1024)).toFixed(2) + " MB";
    else _storage = (_b / (1024 * 1024 * 1024)).toFixed(2) + " GB";
    setText("kpi-storage", _storage);

    // Metrics
    const m = data.metrics || {};
    setText("res-cpu-val", (m.cpu || 0).toFixed(0) + "%");
    setText("res-ram-val", (m.ram || 0).toFixed(0) + "%");
    setText("res-disk-val", (m.disk || 0).toFixed(0) + "%");
    setText("res-net-val", (m.net || 0).toFixed(0) + "%");

    setWidth("res-cpu-bar", m.cpu || 0);
    setWidth("res-ram-bar", m.ram || 0);
    setWidth("res-disk-bar", m.disk || 0);
    setWidth("res-net-bar", m.net || 0);

    setWidth("pbar-cpu", m.cpu || 0);
    setWidth("pbar-ram", m.ram || 0);
    setWidth("pbar-disk", m.disk || 0);
    setWidth("pbar-net", m.net || 0);
    setText("pbar-cpu-val", (m.cpu || 0).toFixed(0) + "%");
    setText("pbar-ram-val", (m.ram || 0).toFixed(0) + "%");
    setText("pbar-disk-val", (m.disk || 0).toFixed(0) + "%");
    setText("pbar-net-val", (m.net || 0).toFixed(0) + "%");

    setText("clinic-tracked", fmt(data.clinic?.tracked || 0));
    setText("clinic-quarantined", fmt(data.clinic?.quarantined || 0));
    setText("kb-entries", fmt(data.knowledge?.total_entries || 0));
    setText("queue-backend", data.queue_backend || "—");

    const up = data.uptime_seconds || 0;
    const h = Math.floor(up / 3600);
    const mn = Math.floor((up % 3600) / 60);
    setText("uptime-val", `${h}س ${mn}د`);

    updateDonut(data.agents);
    applyHealthStatus(data);
}

// ----------------------------------------------------------
// Tasks (real)
// ----------------------------------------------------------
async function loadTasks() {
    try {
        const r = await fetch(`${API}/tasks/recent?limit=6`);
        const data = await r.json();
        const container = document.getElementById("tasks-list");
        if (!container) return;
        if (!data.tasks || data.tasks.length === 0) {
            container.innerHTML = '<div style="text-align:center;color:#64748b;padding:20px;font-size:12px">لا توجد مهام مسجلة بعد</div>';
            return;
        }
        container.innerHTML = data.tasks.map(t => `
            <div class="task-line">
                <span class="task-time">${t.time}</span>
                <span class="task-desc">${t.title}</span>
                <span class="${statusClass(t.status)}">● ${t.status_ar}</span>
            </div>
        `).join("");
    } catch (e) {
        console.error("[Dashboard] tasks error:", e);
    }
}

// ----------------------------------------------------------
// Sources (real)
// ----------------------------------------------------------
async function loadSources() {
    try {
        const r = await fetch(`${API}/sources`);
        const data = await r.json();
        const tbody = document.getElementById("sources-tbody");
        if (!tbody) return;
        if (!data.sources || data.sources.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:#64748b;padding:20px">لا توجد مصادر مسجلة — سيتم تسجيلها عند بدء الجمع</td></tr>';
            return;
        }
        tbody.innerHTML = data.sources.slice(0, 8).map(s => `
            <tr>
                <td>${s.name}</td>
                <td><span class="status-dot">● ${s.status === 'active' ? 'نشط' : s.status}</span></td>
                <td>${s.last}</td>
                <td>${fmt(s.items)}</td>
            </tr>
        `).join("");
    } catch (e) {
        console.error("[Dashboard] sources error:", e);
    }
}

// ----------------------------------------------------------
// Task stats + metrics (real)
// ----------------------------------------------------------
async function loadTaskStats() {
    try {
        const r = await fetch(`${API}/tasks/stats`);
        const data = await r.json();
        setText("stat-total", fmt(data.total || 0));
        setText("stat-completed", fmt(data.completed || 0));
        setText("stat-failed", fmt(data.failed || 0));
        setText("stat-rate", (data.success_rate || 0).toFixed(1) + "%");
    } catch (e) { console.error(e); }
}


// ----------------------------------------------------------
// Health Status (real)
// ----------------------------------------------------------
function applyHealthStatus(data) {
    const ring = document.getElementById("health-ring");
    const text = document.getElementById("health-text");
    const sub  = document.getElementById("health-sub");
    if (!ring || !text || !sub) return;

    const rate = data.tasks?.success_rate || 0;
    const failed = data.tasks?.failed || 0;
    const running = data.running || false;

    let color, label, note, symbol;
    if (!running) {
        color = "#ef4444"; label = "متوقف"; note = "النظام لا يعمل حالياً"; symbol = "✕";
    } else if (rate >= 95 && failed === 0) {
        color = "#10b981"; label = "ممتاز"; note = "لا يوجد مشاكل"; symbol = "✓";
    } else if (rate >= 80) {
        color = "#22d3ee"; label = "جيد"; note = `${failed} مهمة فاشلة`; symbol = "✓";
    } else if (rate >= 50) {
        color = "#f59e0b"; label = "مقبول"; note = `${failed} مهمة فاشلة`; symbol = "!";
    } else {
        color = "#ef4444"; label = "يحتاج مراجعة"; note = `${failed} مهمة فاشلة`; symbol = "!";
    }

    ring.textContent = symbol;
    ring.style.color = color;
    ring.style.borderColor = color;
    ring.style.boxShadow = `0 0 25px ${color}33`;
    text.textContent = label;
    text.style.color = color;
    sub.textContent = note;
}

// ----------------------------------------------------------
// Today's metrics (real)
// ----------------------------------------------------------
async function loadTodayMetrics() {
    try {
        const r = await fetch(`${API}/metrics/today`);
        const data = await r.json();
        setText("today-success", fmt(data.tasks_success || 0));
        setText("today-failed", fmt(data.tasks_failed || 0));
        setText("today-agents", fmt(data.agents_spawned || 0));
        const total = (data.tasks_success || 0) + (data.tasks_failed || 0);
        const rate = total > 0 ? ((data.tasks_success / total) * 100).toFixed(1) + "%" : "—";
        setText("today-rate", rate);
    } catch (e) {
        console.error("[Dashboard] today metrics error:", e);
    }
}


// ----------------------------------------------------------
// Auto-Scaler status
// ----------------------------------------------------------
async function loadScaler() {
    try {
        const r = await fetch(`${API}/scaler/status`);
        const data = await r.json();
        setText("scaler-stage", data.stage ?? "—");
        setText("scaler-current", fmt(data.current || 0));
        setText("scaler-next", fmt(data.next_target || 0));
        setText("scaler-max", fmt(data.max_agents || 0));
    } catch (e) { console.error(e); }
}


// ----------------------------------------------------------
// Email Pool
// ----------------------------------------------------------
async function loadEmailPool() {
    try {
        const r = await fetch(`${API}/email_pool/stats`);
        const data = await r.json();
        setText("epool-available", fmt(data.available || 0));
        setText("epool-total", fmt(data.total || 0));
        setText("epool-target", fmt(data.target || 0));
    } catch (e) { console.error(e); }
    try {
        const r = await fetch(`${API}/email_pool/demand`);
        const data = await r.json();
        setText("epool-demand", fmt(data.total_demand || 0));
    } catch (e) { console.error(e); }
}


// ----------------------------------------------------------
// Distributed Workers
// ----------------------------------------------------------
async function loadDistributed() {
    try {
        const r = await fetch(`${API}/distributed/status`);
        const data = await r.json();
        setText("dw-online", fmt(data.online_workers || 0));
        setText("dw-capacity", fmt(data.total_capacity || 0));
        setText("dw-active", fmt(data.active_agents || 0));
    } catch (e) { console.error(e); }
    try {
        const r = await fetch(`${API}/master/plan`);
        const data = await r.json();
        setText("dw-target", fmt(data.target_agents || 1000000));
    } catch (e) { console.error(e); }
}


// ----------------------------------------------------------
// Million Runtime (1M agents)
// ----------------------------------------------------------
async function loadMillion() {
    try {
        const r = await fetch(`${API}/million/status`);
        const data = await r.json();
        setText("mr-total", fmt(data.total_agents || 0));
        setText("mr-working", fmt(data.states_sampled?.working || 0));
        setText("mr-learning", fmt(data.states_sampled?.learning || 0));
        setText("mr-memory", (data.memory_mb || 0).toFixed(2) + " MB");
        setText("mr-ticks", fmt(data.ticks || 0));
    } catch (e) { console.error(e); }
}


// ----------------------------------------------------------
// Auto-Deployer
// ----------------------------------------------------------
async function loadDeployer() {
    try {
        const r = await fetch(`${API}/deployer/status`);
        const data = await r.json();
        setText("dp-mode", data.dry_run ? "تجربة (Dry Run)" : "نشط");
        setText("dp-workers", fmt(data.total_workers || 0));
        setText("dp-capacity", fmt(data.total_capacity_agents || 0));
        const maxW = Object.values(data.providers_max || {}).reduce((a, b) => a + b, 0);
        setText("dp-max", fmt(maxW * 10000));
    } catch (e) { console.error(e); }
}

// ----------------------------------------------------------
// Charts
// ----------------------------------------------------------
function initDonut() {
    const ctx = document.getElementById("donutChart");
    if (!ctx) return;
    donutChart = new Chart(ctx, {
        type: "doughnut",
        data: {
            labels: ["المستوى 1", "المستوى 2", "المستوى 3", "المستوى 4", "المستوى 5"],
            datasets: [{
                data: [0, 0, 0, 0, 0],
                backgroundColor: ["#6366f1", "#3b82f6", "#10b981", "#f59e0b", "#ef4444"],
                borderWidth: 0,
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false, cutout: "70%",
            plugins: { legend: { display: false } },
        },
    });
}

function updateDonut(agents) {
    if (!donutChart || !agents) return;
    donutChart.data.datasets[0].data = [
        agents.level_1 || 0,
        agents.level_2 || 0,
        agents.level_3 || 0,
        agents.level_4 || 0,
        agents.level_5 || 0,
    ];
    donutChart.update("none");
    setText("donut-total", fmt(agents.total || 0));
}

function initActivityChart() {
    const ctx = document.getElementById("activityChart");
    if (!ctx) return;
    const labels = [], data = [];
    for (let i = 29; i >= 0; i--) {
        labels.push(i + "s");
        data.push(40 + Math.random() * 50);
    }
    activityChart = new Chart(ctx, {
        type: "line",
        data: {
            labels,
            datasets: [{
                data,
                borderColor: "#a78bfa",
                backgroundColor: "rgba(139,92,246,0.15)",
                borderWidth: 2, fill: true, tension: 0.4, pointRadius: 0,
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { grid: { display: false }, ticks: { color: "#475569", font: { size: 9 } } },
                y: { grid: { color: "#1a2332" }, ticks: { color: "#475569", font: { size: 9 } }, min: 0, max: 110 },
            },
        },
    });
}

function tickActivity() {
    if (!activityChart) return;
    const d = activityChart.data.datasets[0].data;
    d.shift();
    d.push(40 + Math.random() * 50);
    activityChart.update("none");
}

// ----------------------------------------------------------
// Init
// ----------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
    tickClock();
    setInterval(tickClock, 1000);

    initDonut();
    initActivityChart();

    loadStatus();
    loadTasks();
    loadSources();
    loadTaskStats();
    loadTodayMetrics();
    loadScaler();
    loadEmailPool();
    loadDistributed();
    loadMillion();
    loadDeployer();

    setInterval(loadStatus, 5000);
    setInterval(loadTasks, 10000);
    setInterval(loadSources, 15000);
    setInterval(loadTaskStats, 10000);
    setInterval(loadTodayMetrics, 15000);
    setInterval(loadScaler, 30000);
    setInterval(loadEmailPool, 20000);
    setInterval(loadDistributed, 30000);
    setInterval(loadMillion, 5000);
    setInterval(loadDeployer, 30000);
    setInterval(tickActivity, 2000);

    document.querySelectorAll(".nav-item").forEach(el => {
        el.addEventListener("click", () => {
            document.querySelectorAll(".nav-item").forEach(n => n.classList.remove("active"));
            el.classList.add("active");
        });
    });
});
