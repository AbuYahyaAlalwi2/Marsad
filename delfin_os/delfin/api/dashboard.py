"""لوحة تحكم بسيطة (الطبقة 11): تُعرض بدون بيانات، والبيانات تُجلب بمفتاحك عبر الواجهة."""
HTML = """<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>لوحة دلفن</title>
<style>body{font-family:sans-serif;margin:12px;background:#111;color:#eee}
input,button{padding:8px;margin:4px 0;font-size:16px}input{width:100%;box-sizing:border-box}
pre{background:#1c1c1c;padding:8px;overflow:auto;white-space:pre-wrap;border-radius:6px}
h3{margin:14px 0 4px}.bad{color:#ff6b6b}.ok{color:#6bff95}</style></head><body>
<h2>لوحة دلفن</h2><input id="k" type="password" placeholder="مفتاح API (لا يُحفظ)">
<button onclick="load()">تحديث</button>
<h3>الحالة</h3><pre id="h">—</pre><h3>سلامة سجل التدقيق</h3><pre id="a">—</pre>
<h3>آخر المهام</h3><pre id="t">—</pre><h3>الاستهلاك</h3><pre id="u">—</pre>
<script>
async function g(p){const r=await fetch(p,{headers:{Authorization:'Bearer '+document.getElementById('k').value}});
 const j=await r.json().catch(()=>({error:'رد غير صالح'}));return r.ok?j:{error:j.error||('خطأ '+r.status)};}
function put(id,o){document.getElementById(id).textContent=JSON.stringify(o,null,1);}
async function load(){put('h',await g('/api/health'));put('t',await g('/api/tasks?limit=15'));
 put('u',await g('/api/usage'));put('a',await g('/api/audit/verify'));}
</script></body></html>"""
