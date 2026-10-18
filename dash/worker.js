// Marsad dashboard — Cloudflare Worker (بلا تبعيات). الأسرار: HF_TOKEN, GH_TOKEN, DASH_PASS
const HF = "AbuYahya2/Marsad", GH = "AbuYahyaAlalwi2/Marsad", WF = "factory_cycle_v11.yml";
const hfUrl = (p) => `https://huggingface.co/datasets/${HF}/resolve/main/${p}`;
const J = (o, s = 200) => new Response(JSON.stringify(o), { status: s, headers: { "content-type": "application/json", "cache-control": "no-store" } });

async function safeEq(a, b) {
  const e = new TextEncoder(), [x, y] = await Promise.all([crypto.subtle.digest("SHA-256", e.encode(a)), crypto.subtle.digest("SHA-256", e.encode(b))]);
  const u = new Uint8Array(x), v = new Uint8Array(y); let r = 0; for (let i = 0; i < u.length; i++) r |= u[i] ^ v[i]; return r === 0;
}
async function hfGet(env, p) {
  const r = await fetch(hfUrl(p) + "?t=" + Date.now(), { headers: { Authorization: "Bearer " + env.HF_TOKEN } });
  return r.ok ? await r.text() : null;
}
async function hfPut(env, path, text) {
  const body = JSON.stringify({ key: "header", value: { summary: "dashboard " + path } }) + "\n" +
    JSON.stringify({ key: "file", value: { content: btoa(unescape(encodeURIComponent(text))), path, encoding: "base64" } }) + "\n";
  const r = await fetch(`https://huggingface.co/api/datasets/${HF}/commit/main`, { method: "POST",
    headers: { Authorization: "Bearer " + env.HF_TOKEN, "content-type": "application/x-ndjson" }, body });
  if (!r.ok) throw new Error("HF " + r.status + " " + (await r.text()).slice(0, 200));
}
const jparse = (t) => { try { return JSON.parse(t); } catch { return null; } };

async function status(env) {
  const [st, ctl, rel, seeds] = await Promise.all([hfGet(env, "factory/status.json"), hfGet(env, "factory/control.json"),
    hfGet(env, "release_latest/stats.json"), hfGet(env, "factory/seeds.txt")]);
  let runs = [];
  try {
    const r = await fetch(`https://api.github.com/repos/${GH}/actions/runs?per_page=6`, { headers: { Authorization: "Bearer " + env.GH_TOKEN, "User-Agent": "marsad-dash", Accept: "application/vnd.github+json" } });
    if (r.ok) runs = (await r.json()).workflow_runs.map((x) => ({ name: x.name, status: x.status, conclusion: x.conclusion, at: x.created_at, url: x.html_url }));
  } catch {}
  const s = jparse(st) || {};
  const beat = s.hb || s.last_ts, age = beat ? Math.round(Date.now() / 1000 - beat) : null;
  const alive = age === null || age > 1500 ? false : (s.state === "paused" ? "paused" : true);
  return { now: Date.now(), daemon: s, daemon_age_sec: age, alive,
    control: jparse(ctl) || {}, release: jparse(rel) || {}, seeds: (seeds || "").split("\n").filter((l) => l.includes("=")), runs };
}

export default {
  async fetch(req, env) {
    const u = new URL(req.url);
    if (u.pathname === "/") return new Response(PAGE, { headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-store" } });
    if (!u.pathname.startsWith("/api/")) return new Response("not found", { status: 404 });
    const pass = req.headers.get("x-pass") || "";
    if (!env.DASH_PASS || !(await safeEq(pass, env.DASH_PASS))) return J({ error: "unauthorized" }, 401);
    try {
      if (u.pathname === "/api/status") return J(await status(env));
      if (req.method !== "POST") return J({ error: "method" }, 405);
      const b = await req.json();
      if (u.pathname === "/api/control") {                                  // قائمة بيضاء للحقول
        const cur = jparse(await hfGet(env, "factory/control.json")) || {}, out = { ...cur };
        if (typeof b.enabled === "boolean") out.enabled = b.enabled;
        for (const [k, lo, hi] of [["workers", 1, 4], ["batch", 1, 10], ["llm_sites", 0, 200]])
          if (b[k] !== undefined) { const n = Math.floor(Number(b[k])); if (!(n >= lo && n <= hi)) return J({ error: k + " out of range" }, 400); out[k] = n; }
        await hfPut(env, "factory/control.json", JSON.stringify(out)); return J({ ok: true, control: out });
      }
      if (u.pathname === "/api/seeds") {
        const line = String(b.line || "").trim();
        if (!/^[A-Za-z0-9_.-]+=https:\/\/github\.com\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+(\.git)?$/.test(line)) return J({ error: "format: name=https://github.com/owner/repo" }, 400);
        const cur = (await hfGet(env, "factory/seeds.txt")) || "";
        await hfPut(env, "factory/seeds.txt", (cur.trim() ? cur.trim() + "\n" : "") + line + "\n"); return J({ ok: true });
      }
      if (u.pathname === "/api/dispatch") {
        const r = await fetch(`https://api.github.com/repos/${GH}/actions/workflows/${WF}/dispatches`, { method: "POST",
          headers: { Authorization: "Bearer " + env.GH_TOKEN, "User-Agent": "marsad-dash", Accept: "application/vnd.github+json" }, body: JSON.stringify({ ref: "main" }) });
        return J({ ok: r.status === 204, status: r.status }, r.status === 204 ? 200 : 502);
      }
      return J({ error: "unknown" }, 404);
    } catch (e) { return J({ error: String(e.message || e).slice(0, 300) }, 502); }
  },
};

const PAGE = `<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>مرصد — لوحة التحكم</title><style>
:root{--bg:#f6f7f9;--c:#fff;--t:#14171c;--m:#667085;--l:#e4e7ec;--ok:#12805c;--bad:#c0362c;--warn:#b7791f;--a:#2457d6}
@media(prefers-color-scheme:dark){:root{--bg:#0e1116;--c:#171b22;--t:#e8ebf0;--m:#98a2b3;--l:#2a303a;--ok:#3ddc97;--bad:#ff7b72;--warn:#e3b341;--a:#7aa2ff}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--t);font:15px/1.6 system-ui,-apple-system,"Segoe UI",Tahoma,sans-serif;padding:16px}
.w{max-width:760px;margin:auto}h1{font-size:20px;margin:0 0 4px}h2{font-size:14px;color:var(--m);margin:20px 0 8px;font-weight:600}
.card{background:var(--c);border:1px solid var(--l);border-radius:12px;padding:14px;margin-bottom:10px}
.g{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px}.k{font-size:12px;color:var(--m)}.v{font-size:22px;font-weight:700;direction:ltr;text-align:right}
.dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-left:6px}.ok{background:var(--ok)}.bad{background:var(--bad)}.warn{background:var(--warn)}
button,input{font:inherit;border-radius:8px;border:1px solid var(--l);padding:9px 12px;background:var(--c);color:var(--t)}button{cursor:pointer;background:var(--a);color:#fff;border:0}button.s{background:var(--c);color:var(--t);border:1px solid var(--l)}
.r{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:6px 0}input{flex:1;min-width:120px}table{width:100%;border-collapse:collapse;font-size:13px}td{padding:5px 0;border-bottom:1px solid var(--l)}
.mu{color:var(--m);font-size:13px}.ft li{margin:4px 0}.tag{font-size:11px;padding:1px 7px;border-radius:99px;border:1px solid var(--l);color:var(--m);margin-inline-start:6px}
</style></head><body><div class="w"><h1>مرصد · لوحة التحكم</h1><div class="mu" id="sub">—</div>
<div id="login" class="card" style="display:none"><div class="r"><input id="pw" type="password" placeholder="كلمة المرور"><button onclick="go()">دخول</button></div></div>
<div id="app" style="display:none">
<h2>المصنع</h2><div class="card"><div id="state"></div><div class="g" style="margin-top:10px">
<div><div class="k">دورات</div><div class="v" id="cy">-</div></div><div><div class="k">مشاريع منتهية</div><div class="v" id="dn">-</div></div>
<div><div class="k">صندوق صادر</div><div class="v" id="ob">-</div></div><div><div class="k">آخر نبضة</div><div class="v" id="ag">-</div></div></div></div>
<h2>الإنتاج (release_latest)</h2><div class="card"><div class="g">
<div><div class="k">تدريب</div><div class="v" id="tr">-</div></div><div><div class="k">تقييم</div><div class="v" id="ev">-</div></div>
<div><div class="k">مشاريع</div><div class="v" id="rp">-</div></div><div><div class="k">إصلاحات حقيقية</div><div class="v" id="rf">-</div></div></div></div>
<h2>مزوّدو LLM</h2><div class="card mu" id="llm">-</div>
<h2>تحكم</h2><div class="card"><div class="r"><button id="tg" onclick="toggle()">—</button><button class="s" onclick="disp()">تشغيل دورة Actions الآن</button></div>
<div class="r"><span class="mu">workers</span><input id="w" type="number" min="1" max="4"><span class="mu">batch</span><input id="b" type="number" min="1" max="10">
<span class="mu">llm_sites</span><input id="l" type="number" min="0" max="200"><button onclick="save()">حفظ</button></div>
<div class="r"><input id="sd" placeholder="name=https://github.com/owner/repo" dir="ltr"><button onclick="seed()">إضافة بذرة</button></div><div class="mu" id="sdl"></div><div class="mu" id="msg"></div></div>
<h2>دورات GitHub Actions</h2><div class="card"><table id="runs"></table></div>
<h2>المميزات المخطط لها</h2><div class="card"><ul class="ft mu" style="margin:0;padding-inline-start:18px">
<li>وكلاء مصادر (codeforces، مجموعات HF) <span class="tag">قيد البناء</span></li><li>وكلاء مشاريع كاملة + المشرف (متجر/بنك/جامعة) <span class="tag">مخطط</span></li>
<li>تحقق E2B للشيفرة الخطرة <span class="tag">مخطط</span></li><li>ساندبوكس Docker خاص بنا <span class="tag">مخطط</span></li>
<li>فحص ملكية الشركة/الجهاز <span class="tag">مخطط</span></li><li>الشروط والأحكام والمراجعة القانونية <span class="tag">مخطط</span></li></ul></div>
</div></div><script>
let P=localStorage.getItem("mp")||"",S=null;const $=i=>document.getElementById(i);
async function api(p,b){const r=await fetch("/api/"+p,{method:b?"POST":"GET",headers:{"x-pass":P,"content-type":"application/json"},body:b?JSON.stringify(b):undefined});
 if(r.status==401){localStorage.removeItem("mp");$("login").style.display="";$("app").style.display="none";throw new Error("unauthorized")}return r.json()}
function go(){P=$("pw").value;localStorage.setItem("mp",P);load()}
const n=x=>x==null?"-":Number(x).toLocaleString("en");
async function load(){try{S=await api("status")}catch(e){$("login").style.display="";return}
 $("login").style.display="none";$("app").style.display="";const d=S.daemon,c=S.control,r=S.release;
 const cls=S.alive===true?"ok":S.alive==="paused"?"warn":"bad";
 $("state").innerHTML='<span class="dot '+cls+'"></span>'+({true:"حيّ",false:"لا نبض حديث"}[S.alive]||"متوقّف بأمر")+' · الحالة: <b>'+(d.state||"?")+'</b> · المضيف: '+(d.host||"?");
 $("cy").textContent=n(d.cycles_done);$("dn").textContent=n(d.last_cycle&&d.last_cycle.report&&d.last_cycle.report.done_total);
 $("ob").textContent=n(d.outbox||0);$("ag").textContent=S.daemon_age_sec==null?"-":Math.round(S.daemon_age_sec/60)+"د";
 $("tr").textContent=n(r.train);$("ev").textContent=n(r.eval);$("rp").textContent=n(r.repos);$("rf").textContent=n(r.real_fix_pairs);
 const L=d.llm;$("llm").textContent=L?("ناجح "+L.ok+" · فاشل "+L.fail+" · 429: "+L.rate_limited+" · "+JSON.stringify(L.by)):(d.llm_enabled===false?"معطّل (لا مفاتيح)":"لا بيانات");
 const en=c.enabled!==false;$("tg").textContent=en?"إيقاف المصنع مؤقتاً":"استئناف المصنع";$("w").value=c.workers||"";$("b").value=c.batch||"";$("l").value=c.llm_sites??"";
 $("sdl").textContent=S.seeds.length?("بذور بالانتظار: "+S.seeds.join(" , ")):"";
 $("runs").innerHTML=S.runs.map(x=>'<tr><td>'+x.name+'</td><td>'+(x.conclusion||x.status)+'</td><td class="mu">'+x.at.slice(5,16).replace("T"," ")+'</td></tr>').join("")||"<tr><td>—</td></tr>";
 $("sub").textContent="آخر تحديث "+new Date().toLocaleTimeString("ar")}
async function post(p,b){$("msg").textContent="…";try{const r=await api(p,b);$("msg").textContent=r.error?("خطأ: "+r.error):"تم ✓";load()}catch(e){$("msg").textContent=String(e)}}
function toggle(){post("control",{enabled:!(S.control.enabled!==false)})}
function save(){const b={};for(const[k,i]of[["workers","w"],["batch","b"],["llm_sites","l"]])if($(i).value!=="")b[k]=Number($(i).value);post("control",b)}
function seed(){post("seeds",{line:$("sd").value}).then(()=>$("sd").value="")}
function disp(){post("dispatch",{})}
if(P)load();else $("login").style.display="";setInterval(()=>P&&load(),60000);
</script></body></html>`;
