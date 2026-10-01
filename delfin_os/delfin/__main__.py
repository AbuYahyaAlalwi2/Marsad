"""أوامر التشغيل: init | newkey | manifest | verify | serve"""
import argparse
import os
import sys

from .app import build_app
from .security.layer import SCOPES


def _env_or_file(name):
    v = os.environ.get(name)
    f = os.environ.get(name + "_FILE")
    if not v and f and os.path.exists(f):
        v = open(f).read().strip()
    return v or ""


def _build(home):
    llm = auditor = sandbox = notifier = None
    url = os.environ.get("DELFIN_LLM_URL")
    if url:
        from .agents.llm import LLMClient
        llm = LLMClient(url, _env_or_file("DELFIN_LLM_KEY"), os.environ.get("DELFIN_LLM_MODEL", "v2"))
        aurl = os.environ.get("DELFIN_AUDITOR_URL")
        if aurl:
            auditor = LLMClient(aurl, _env_or_file("DELFIN_AUDITOR_KEY"), os.environ.get("DELFIN_AUDITOR_MODEL", "v2"))
    surl = os.environ.get("DELFIN_SANDBOX_URL")
    if surl:
        from .sandbox.executor import RemoteSandbox
        sandbox = RemoteSandbox(surl, _env_or_file("DELFIN_SANDBOX_TOKEN"))
    tg, chat = _env_or_file("TELEGRAM_BOT_TOKEN"), _env_or_file("TELEGRAM_CHAT_ID")
    if tg and chat:
        from .safety.layers import TelegramNotifier
        notifier = TelegramNotifier(tg, chat)
    ctx = ""
    cp = os.environ.get("DELFIN_COMPANY_FILE")
    if cp and os.path.exists(cp):
        ctx = open(cp, encoding="utf-8").read()[:6000]
    app = build_app(home, llm=llm, auditor_llm=auditor, sandbox=sandbox, notifier=notifier, company_context=ctx)
    return app


def main(argv=None):
    ap = argparse.ArgumentParser(prog="delfin")
    ap.add_argument("cmd", choices=["init", "newkey", "listkeys", "revoke", "manifest", "verify", "serve"])
    ap.add_argument("--home", default=os.environ.get("DELFIN_HOME", os.path.expanduser("~/.delfin")))
    ap.add_argument("--name", default="admin")
    ap.add_argument("--id", default="")
    ap.add_argument("--scopes", default="admin")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--model-file")
    ap.add_argument("--model-sha")
    a = ap.parse_args(argv)
    app = _build(a.home)
    if a.cmd in ("init", "newkey"):
        scopes = set(a.scopes.split(","))
        if not scopes <= SCOPES:
            sys.exit("نطاقات غير صالحة: " + ",".join(sorted(scopes - SCOPES)))
        kid, raw = app.security.keys.issue(a.name, scopes)
        if a.cmd == "init":
            app.integrity.build_manifest(["delfin/security", "delfin/sandbox", "delfin/safety", "delfin/core"])
        app.security.audit.append("owner-cli", "key_issued", f"{kid} {a.name} {','.join(sorted(scopes))}")
        print(f"المفتاح (يُعرض مرة واحدة فقط، احفظه الآن):\n{raw}\nالمعرّف: {kid}")
    elif a.cmd == "listkeys":
        rows = app.security.keys.list()
        for r in rows:
            print(f"{r['id']}  {'ملغى ' if r['revoked'] else 'فعّال'}  {r['name']}  [{','.join(r['scopes'])}]")
        if not rows:
            print("لا توجد مفاتيح")
    elif a.cmd == "revoke":
        if not a.id:
            sys.exit("حدّد المعرّف: --id <المعرّف> (اعرضها بـ listkeys)")
        if not app.security.keys.revoke(a.id):
            sys.exit("معرّف غير موجود")
        app.security.audit.append("owner-cli", "key_revoked", a.id)
        print("أُلغي المفتاح", a.id)
    elif a.cmd == "manifest":
        n = len(app.integrity.build_manifest(["delfin/security", "delfin/sandbox", "delfin/safety", "delfin/core"]))
        print(f"تم توقيع بصمات {n} ملفاً")
    elif a.cmd == "verify":
        probs = app.integrity.verify()
        ok, n = app.security.audit.verify()
        if a.model_file and a.model_sha:
            app.integrity.verify_model(a.model_file, a.model_sha)
            probs = app.integrity.problems
        print("سجل التدقيق:", "سليم" if ok else "مُعبَث به", f"({n} سطراً)")
        print("القيود:", "مُعبَث بها" if app.safety.store.tampered else "سليمة")
        print("السلامة:", "سليمة" if not probs else probs)
        sys.exit(0 if ok and not probs and not app.safety.store.tampered else 1)
    elif a.cmd == "serve":
        probs = app.integrity.verify()
        if probs:
            app.safety.enter_maintenance("؛ ".join(probs)[:300])
            print("تحذير: وضع الصيانة (قراءة فقط):", probs)
        if a.host not in ("127.0.0.1", "localhost"):
            print("تحذير: الربط على غير المحلي. ضع وكيلاً عكسياً بـ TLS ولا تكشف المنفذ مباشرة.")
        srv, _ = __import__("delfin.api.server", fromlist=["serve"]).serve(app, a.host, a.port)
        print(f"يعمل على http://{a.host}:{a.port}/dashboard")
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
