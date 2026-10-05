"""
Admin Server — واجهة الويب للمالك
=====================================
يشغّل صفحة ويب محلية على http://localhost:7860/admin

المالك يفتح المتصفح → يدخل كلمة المرور → يتحكم بكل شيء
بدون قيود المستخدمين، بدون فلتر output، بدون rate limit

المقارنة بالشركات الكبرى:
  OpenAI داخلياً   → api.openai.com/internal/v1  (موظفون فقط)
  مرصد (AbuYahya)  → localhost:7860/admin         (أنت فقط)

تشغيل:
    python admin_server.py
    ثم افتح: http://localhost:7860/admin
"""

import asyncio
import json
import time
from pathlib import Path
import sys

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT / "admin"))
sys.path.insert(0, str(_ROOT / "agents"))
sys.path.insert(0, str(_ROOT / "core"))
sys.path.insert(0, str(_ROOT / "protection"))

from admin_auth   import get_admin_auth
from output_guard import TierManager, UserTier

try:
    from aiohttp import web
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False


# ─── الصفحات ─────────────────────────────────────────────────────────────────

LOGIN_HTML = """<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>مرصد — Admin</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Segoe UI', Arial, sans-serif;
    background: #0a0a0f;
    color: #e0e0e0;
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
  }
  .card {
    background: #13131a;
    border: 1px solid #2a2a3a;
    border-radius: 12px;
    padding: 40px;
    width: 380px;
    box-shadow: 0 0 40px rgba(100,120,255,0.1);
  }
  .logo {
    text-align: center;
    font-size: 28px;
    font-weight: 700;
    color: #7b9cff;
    margin-bottom: 8px;
    letter-spacing: 2px;
  }
  .subtitle {
    text-align: center;
    color: #666;
    font-size: 13px;
    margin-bottom: 32px;
  }
  label { display: block; font-size: 13px; color: #888; margin-bottom: 6px; }
  input[type="password"] {
    width: 100%;
    background: #1e1e2e;
    border: 1px solid #2a2a3a;
    border-radius: 8px;
    color: #e0e0e0;
    padding: 12px 16px;
    font-size: 15px;
    outline: none;
    transition: border-color 0.2s;
  }
  input[type="password"]:focus { border-color: #7b9cff; }
  button {
    width: 100%;
    background: #7b9cff;
    color: #0a0a0f;
    border: none;
    border-radius: 8px;
    padding: 13px;
    font-size: 15px;
    font-weight: 700;
    cursor: pointer;
    margin-top: 20px;
    transition: background 0.2s;
  }
  button:hover { background: #9bb5ff; }
  .error {
    background: #2a1515;
    border: 1px solid #5a2020;
    border-radius: 6px;
    color: #ff7b7b;
    padding: 10px 14px;
    margin-top: 16px;
    font-size: 13px;
    display: none;
  }
  .indicator {
    display: flex; align-items: center; gap: 8px;
    margin-top: 24px; color: #555; font-size: 12px;
  }
  .dot { width: 8px; height: 8px; border-radius: 50%; background: #2a5a2a; }
</style>
</head>
<body>
<div class="card">
  <div class="logo">⬡ مرصد</div>
  <div class="subtitle">لوحة تحكم المالك — Admin</div>

  <form method="POST" action="/admin/login">
    <label>كلمة مرور Admin</label>
    <input type="password" name="password" placeholder="••••••••" autofocus>
    <button type="submit">دخول</button>
  </form>

  {ERROR_BLOCK}

  <div class="indicator">
    <div class="dot"></div>
    <span>الوصول مقيّد بجهازك المحلي فقط</span>
  </div>
</div>
</body>
</html>"""


DASHBOARD_HTML = """<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>مرصد — Admin Dashboard</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', Arial, sans-serif; background: #0a0a0f; color: #e0e0e0; }
  .topbar {
    background: #13131a;
    border-bottom: 1px solid #2a2a3a;
    padding: 14px 24px;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .logo { font-size: 20px; font-weight: 700; color: #7b9cff; letter-spacing: 2px; }
  .badge {
    background: #1a2a1a;
    border: 1px solid #2a5a2a;
    color: #5aff5a;
    font-size: 11px;
    padding: 4px 10px;
    border-radius: 20px;
  }
  .logout {
    color: #666; font-size: 13px; text-decoration: none; padding: 6px 12px;
    border: 1px solid #2a2a3a; border-radius: 6px; transition: all 0.2s;
  }
  .logout:hover { color: #ff7b7b; border-color: #5a2020; }

  .main { display: flex; min-height: calc(100vh - 53px); }
  .sidebar {
    width: 220px;
    background: #13131a;
    border-left: 1px solid #2a2a3a;
    padding: 20px 0;
  }
  .nav-item {
    padding: 12px 20px;
    cursor: pointer;
    color: #888;
    font-size: 14px;
    transition: all 0.15s;
    border-right: 3px solid transparent;
    display: block;
    text-decoration: none;
  }
  .nav-item:hover, .nav-item.active {
    color: #e0e0e0;
    background: #1e1e2e;
    border-right-color: #7b9cff;
  }
  .content { flex: 1; padding: 28px 32px; }

  h2 { font-size: 20px; margin-bottom: 20px; color: #c0c8ff; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 16px; margin-bottom: 28px; }
  .stat-card {
    background: #13131a;
    border: 1px solid #2a2a3a;
    border-radius: 10px;
    padding: 20px;
  }
  .stat-card .label { font-size: 12px; color: #666; margin-bottom: 8px; }
  .stat-card .value { font-size: 28px; font-weight: 700; color: #7b9cff; }

  .panel {
    background: #13131a;
    border: 1px solid #2a2a3a;
    border-radius: 10px;
    padding: 20px;
    margin-bottom: 20px;
  }
  .panel h3 { font-size: 15px; color: #c0c8ff; margin-bottom: 16px; }

  textarea {
    width: 100%;
    background: #1e1e2e;
    border: 1px solid #2a2a3a;
    border-radius: 8px;
    color: #e0e0e0;
    padding: 12px;
    font-family: monospace;
    font-size: 13px;
    resize: vertical;
    min-height: 120px;
    outline: none;
  }
  textarea:focus { border-color: #7b9cff; }

  .btn {
    background: #7b9cff;
    color: #0a0a0f;
    border: none;
    border-radius: 7px;
    padding: 10px 20px;
    font-size: 13px;
    font-weight: 700;
    cursor: pointer;
    margin-top: 12px;
    transition: background 0.2s;
  }
  .btn:hover { background: #9bb5ff; }
  .btn-danger { background: #cc4444; color: white; }
  .btn-danger:hover { background: #ee5555; }

  .response-box {
    background: #0a0a0f;
    border: 1px solid #2a2a3a;
    border-radius: 8px;
    padding: 14px;
    margin-top: 14px;
    font-family: monospace;
    font-size: 13px;
    white-space: pre-wrap;
    min-height: 60px;
    color: #aaffaa;
    display: none;
  }

  table { width: 100%; border-collapse: collapse; }
  th { text-align: right; padding: 10px; font-size: 12px; color: #666; border-bottom: 1px solid #2a2a3a; }
  td { padding: 10px; font-size: 13px; border-bottom: 1px solid #1a1a2a; }

  input[type="text"] {
    background: #1e1e2e;
    border: 1px solid #2a2a3a;
    border-radius: 6px;
    color: #e0e0e0;
    padding: 8px 12px;
    font-size: 13px;
    outline: none;
    margin-left: 8px;
  }
  input[type="text"]:focus { border-color: #7b9cff; }

  .tag { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px; }
  .tag-sub  { background: #1a2a1a; color: #5aff5a; border: 1px solid #2a5a2a; }
  .tag-free { background: #2a2a1a; color: #ffdd5a; border: 1px solid #5a5a2a; }
</style>
</head>
<body>
<div class="topbar">
  <div class="logo">⬡ مرصد</div>
  <span class="badge">✓ Admin — AbuYahya</span>
  <a href="/admin/logout" class="logout">خروج</a>
</div>

<div class="main">
  <div class="sidebar">
    <a class="nav-item active" href="#" onclick="showTab('dashboard')">📊 لوحة التحكم</a>
    <a class="nav-item" href="#" onclick="showTab('scan')">🔍 فحص مباشر</a>
    <a class="nav-item" href="#" onclick="showTab('users')">👥 المستخدمون</a>
    <a class="nav-item" href="#" onclick="showTab('training')">🧠 التدريب</a>
    <a class="nav-item" href="#" onclick="showTab('logs')">📋 السجلات</a>
  </div>

  <div class="content">

    <!-- Dashboard -->
    <div id="tab-dashboard">
      <h2>لوحة التحكم</h2>
      <div class="grid">
        <div class="stat-card"><div class="label">إجمالي الفحوصات</div><div class="value" id="stat-scans">—</div></div>
        <div class="stat-card"><div class="label">الثغرات المكتشفة</div><div class="value" id="stat-vulns">—</div></div>
        <div class="stat-card"><div class="label">المستخدمون</div><div class="value" id="stat-users">—</div></div>
        <div class="stat-card"><div class="label">المشتركون</div><div class="value" id="stat-subs">—</div></div>
      </div>
      <div class="panel">
        <h3>حالة النظام</h3>
        <div id="system-status" style="color:#666;font-size:13px;">جاري التحميل...</div>
      </div>
    </div>

    <!-- Scan -->
    <div id="tab-scan" style="display:none">
      <h2>فحص مباشر — بلا قيود</h2>
      <div class="panel">
        <h3>أرسل كوداً للفحص</h3>
        <textarea id="scan-input" placeholder="الصق الكود هنا..."></textarea>
        <br>
        <button class="btn" onclick="runScan()">▶ فحص</button>
        <div class="response-box" id="scan-result"></div>
      </div>
    </div>

    <!-- Users -->
    <div id="tab-users" style="display:none">
      <h2>إدارة المستخدمين</h2>
      <div class="panel">
        <h3>ترقية / تخفيض مستوى</h3>
        <input type="text" id="uid-input" placeholder="معرف المستخدم">
        <button class="btn" onclick="upgradeUser()">⬆ ترقية لمشترك</button>
        <button class="btn btn-danger" style="margin-right:8px" onclick="downgradeUser()">⬇ تخفيض لمجاني</button>
        <div class="response-box" id="user-result"></div>
      </div>
      <div class="panel">
        <h3>المستخدمون الحاليون</h3>
        <table id="users-table">
          <tr><th>المعرف</th><th>المستوى</th></tr>
        </table>
      </div>
    </div>

    <!-- Training -->
    <div id="tab-training" style="display:none">
      <h2>التدريب والتقييم</h2>
      <div class="panel">
        <h3>تصدير بيانات التدريب</h3>
        <p style="color:#666;font-size:13px;margin-bottom:12px">تصدير السجلات المتحقق منها بصيغة JSONL للتدريب</p>
        <button class="btn" onclick="exportTraining()">📦 تصدير JSONL</button>
        <div class="response-box" id="training-result"></div>
      </div>
    </div>

    <!-- Logs -->
    <div id="tab-logs" style="display:none">
      <h2>السجلات</h2>
      <div class="panel">
        <h3>آخر الأخطاء المسجّلة</h3>
        <div id="logs-content" style="color:#666;font-size:13px;">جاري التحميل...</div>
      </div>
    </div>

  </div>
</div>

<script>
const TOKEN = "{SESSION_TOKEN}";

function showTab(name) {
  document.querySelectorAll('[id^="tab-"]').forEach(t => t.style.display = 'none');
  document.getElementById('tab-' + name).style.display = 'block';
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  event.target.classList.add('active');
  if (name === 'dashboard') loadStats();
  if (name === 'users') loadUsers();
  if (name === 'logs') loadLogs();
}

async function api(path, data = null) {
  const opts = {
    headers: {'X-Admin-Token': TOKEN, 'Content-Type': 'application/json'}
  };
  if (data) { opts.method = 'POST'; opts.body = JSON.stringify(data); }
  const r = await fetch('/admin/api' + path, opts);
  return r.json();
}

async function loadStats() {
  const d = await api('/stats');
  document.getElementById('stat-scans').textContent = d.total_scans ?? '—';
  document.getElementById('stat-vulns').textContent = d.total_vulns ?? '—';
  document.getElementById('stat-users').textContent = d.total_users ?? '—';
  document.getElementById('stat-subs').textContent  = d.subscribers ?? '—';
  document.getElementById('system-status').textContent =
    'النموذج: ' + (d.model ?? '—') + ' | الحالة: ' + (d.status ?? 'غير معروف');
}

async function runScan() {
  const code = document.getElementById('scan-input').value;
  const box  = document.getElementById('scan-result');
  box.style.display = 'block';
  box.textContent = 'جاري الفحص...';
  const d = await api('/scan', {code, user_id: 'admin'});
  box.textContent = d.report || JSON.stringify(d, null, 2);
}

async function upgradeUser() {
  const uid = document.getElementById('uid-input').value;
  const d   = await api('/user/upgrade', {user_id: uid});
  const box = document.getElementById('user-result');
  box.style.display = 'block';
  box.textContent = d.message;
  loadUsers();
}

async function downgradeUser() {
  const uid = document.getElementById('uid-input').value;
  const d   = await api('/user/downgrade', {user_id: uid});
  const box = document.getElementById('user-result');
  box.style.display = 'block';
  box.textContent = d.message;
  loadUsers();
}

async function loadUsers() {
  const d    = await api('/users');
  const tbl  = document.getElementById('users-table');
  let rows   = '<tr><th>المعرف</th><th>المستوى</th></tr>';
  for (const [uid, tier] of Object.entries(d.users || {})) {
    const cls = tier === 'subscriber' ? 'tag-sub' : 'tag-free';
    rows += `<tr><td>${uid}</td><td><span class="tag ${cls}">${tier}</span></td></tr>`;
  }
  tbl.innerHTML = rows;
}

async function exportTraining() {
  const d   = await api('/export');
  const box = document.getElementById('training-result');
  box.style.display = 'block';
  box.textContent = d.message;
}

async function loadLogs() {
  const d = await api('/logs');
  document.getElementById('logs-content').innerHTML =
    (d.errors || []).map(e =>
      `<div style="margin-bottom:12px;padding:10px;background:#1a1a2a;border-radius:6px">
        <div style="color:#ff9955">${e.error_type}</div>
        <div style="color:#888;font-size:12px;margin-top:4px">${e.lesson}</div>
      </div>`
    ).join('') || 'لا أخطاء مسجّلة';
}

// تحميل تلقائي
loadStats();
</script>
</body>
</html>"""


# ─── الـ Server ───────────────────────────────────────────────────────────────

def create_app():
    if not HAS_AIOHTTP:
        raise ImportError("pip install aiohttp")

    from security_pipeline import SecurityPipeline
    from knowledge_store   import get_store

    app      = web.Application()
    auth_mgr = get_admin_auth()
    tiers    = TierManager()
    store    = get_store()

    # ── المسارات ──────────────────────────────────────────────────────────────

    async def handle_login_page(request):
        error = request.rel_url.query.get("error", "")
        err_block = (
            f'<div class="error" style="display:block">✗ {error}</div>'
            if error else ""
        )
        return web.Response(
            text=LOGIN_HTML.replace("{ERROR_BLOCK}", err_block),
            content_type="text/html"
        )

    async def handle_login_post(request):
        data     = await request.post()
        password = data.get("password", "")
        session  = auth_mgr.login(password)

        if not session.valid:
            raise web.HTTPFound("/admin?error=كلمة+المرور+خاطئة")

        # احفظ الـ token في cookie
        resp = web.HTTPFound("/admin/dashboard")
        resp.set_cookie("admin_token", session.token, httponly=True, max_age=28800)
        return resp

    async def handle_dashboard(request):
        token = request.cookies.get("admin_token", "")
        if not auth_mgr.verify_session(token):
            raise web.HTTPFound("/admin")
        html = DASHBOARD_HTML.replace("{SESSION_TOKEN}", token)
        return web.Response(text=html, content_type="text/html")

    async def handle_logout(request):
        resp = web.HTTPFound("/admin")
        resp.del_cookie("admin_token")
        return resp

    def _check_token(request) -> bool:
        token = request.headers.get("X-Admin-Token", "")
        return auth_mgr.verify_session(token)

    async def api_stats(request):
        if not _check_token(request):
            return web.json_response({"error": "غير مصرح"}, status=401)
        stats = store.get_stats() if hasattr(store, 'get_stats') else {}
        return web.json_response({
            "total_scans": stats.get("total", 0),
            "total_vulns": stats.get("verified", 0),
            "total_users": len(tiers._tiers),
            "subscribers": sum(1 for v in tiers._tiers.values() if v == "subscriber"),
            "model":       "Qwen3-Coder-480B",
            "status":      "جاهز",
        })

    async def api_scan(request):
        if not _check_token(request):
            return web.json_response({"error": "غير مصرح"}, status=401)
        data     = await request.json()
        code     = data.get("code", "")
        pipeline = SecurityPipeline()
        result   = await pipeline.analyze(code)
        return web.json_response({"report": result.report})

    async def api_upgrade(request):
        if not _check_token(request):
            return web.json_response({"error": "غير مصرح"}, status=401)
        data = await request.json()
        uid  = data.get("user_id", "")
        tiers.upgrade(uid)
        return web.json_response({"message": f"✓ {uid} → مشترك"})

    async def api_downgrade(request):
        if not _check_token(request):
            return web.json_response({"error": "غير مصرح"}, status=401)
        data = await request.json()
        uid  = data.get("user_id", "")
        tiers.downgrade(uid)
        return web.json_response({"message": f"✓ {uid} → مجاني"})

    async def api_users(request):
        if not _check_token(request):
            return web.json_response({"error": "غير مصرح"}, status=401)
        return web.json_response({"users": tiers._tiers})

    async def api_export(request):
        if not _check_token(request):
            return web.json_response({"error": "غير مصرح"}, status=401)
        path = store.export_training_jsonl()
        return web.json_response({"message": f"✓ تم التصدير: {path}"})

    async def api_logs(request):
        if not _check_token(request):
            return web.json_response({"error": "غير مصرح"}, status=401)
        errors = store.get_errors_for_context(limit=20)
        return web.json_response({"errors": errors})

    # ── تسجيل المسارات ────────────────────────────────────────────────────────

    app.router.add_get  ("/admin",              handle_login_page)
    app.router.add_post ("/admin/login",        handle_login_post)
    app.router.add_get  ("/admin/dashboard",    handle_dashboard)
    app.router.add_get  ("/admin/logout",       handle_logout)

    app.router.add_get  ("/admin/api/stats",    api_stats)
    app.router.add_post ("/admin/api/scan",     api_scan)
    app.router.add_post ("/admin/api/user/upgrade",   api_upgrade)
    app.router.add_post ("/admin/api/user/downgrade", api_downgrade)
    app.router.add_get  ("/admin/api/users",    api_users)
    app.router.add_post ("/admin/api/export",   api_export)
    app.router.add_get  ("/admin/api/logs",     api_logs)

    return app


# ─── التشغيل ─────────────────────────────────────────────────────────────────

def run_admin_server(host: str = "127.0.0.1", port: int = 7860):
    """
    يشغّل السيرفر على localhost فقط (آمن — لا يُكشف للإنترنت)
    """
    auth_mgr = get_admin_auth()

    # إعداد كلمة المرور إذا لم تُعَدّ بعد
    if not auth_mgr.is_setup():
        import getpass
        print("\n⚠ أول تشغيل — اختر كلمة مرور Admin:")
        pw = getpass.getpass("كلمة المرور (لن تُعرض): ")
        auth_mgr.setup(pw)

    app = create_app()

    print(f"\n✓ Admin Server يعمل على: http://{host}:{port}/admin")
    print("  افتح الرابط في متصفحك\n")

    web.run_app(app, host=host, port=port, print=lambda x: None)


if __name__ == "__main__":
    run_admin_server()
