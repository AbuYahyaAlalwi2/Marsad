#!/usr/bin/env python3
"""
marsad_factory_daemon_v5.py — المصنع المستقل: خدمة واحدة دائمة (Railway/أي Docker) بلا تدخل.
الحلقة: خطة (طابور + بذور) -> تعدين معزول لكل مشروع في venv مؤقت -> تحديث الحالة -> حزمة -> رفع HF -> (كل N دورة) إصدار موحّد بحارس.
الحالة والتحكم على HF (دائمة حتى لو أُعيد نشر الحاوية):
  factory/state.json    حالة الطابور (المصدر الوحيد للحقيقة)
  factory/control.json  {"enabled": true, "workers": 2, "batch": 6}  -- مفتاح الإيقاف/التشغيل من أي مكان
  factory/seeds.txt     أسطر name=url (بذور أولوية؛ تُستهلك مرة)
  factory/status.json   نبض الحياة والأرقام المقيسة
البيئة: HF_TOKEN, GH_TOKEN (للقراءة فقط), [TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID], WORKERS, BATCH, BUDGET_MIN, FIX_BUDGET_MIN, FIX_COMMITS, MAX_SITES,
        CONSOLIDATE_EVERY, PORT, HF_REPO. للاختبار المحلي: LOCAL_HF_DIR (يحاكي HF), ONCE=1.
الأمان: عملية التعدين تُشغَّل ببيئة منظَّفة (بلا HF_TOKEN/GH_TOKEN/تيليغرام) داخل venv مؤقت يُحذف بعد كل مشروع.
"""
import glob, json, os, shutil, signal, subprocess, sys, threading, time, traceback, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, HTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.environ.get("WORK_DIR", "/work")
HF_REPO = os.environ.get("HF_REPO", "AbuYahya2/Marsad")
LOCAL_HF = os.environ.get("LOCAL_HF_DIR")
STOP = threading.Event()
LLM = {"url": "", "gw": None}
STATUS = {"started": int(time.time()), "state": "boot", "cycles_done": 0, "last_cycle": None, "consecutive_zero": 0, "release_total": 0}
LAST_ALERT = {}


def env(k, d):
    return type(d)(os.environ.get(k, d))


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def alert(key, msg):
    """تنبيه تيليغرام اختياري، مرة كل ساعة لكل مفتاح."""
    log("ALERT", key, msg)
    tok, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not (tok and chat) or time.time() - LAST_ALERT.get(key, 0) < 3600:
        return
    LAST_ALERT[key] = time.time()
    try:
        data = urllib.parse.urlencode({"chat_id": chat, "text": "Marsad factory: " + msg[:900]}).encode()
        urllib.request.urlopen(urllib.request.Request(f"https://api.telegram.org/bot{tok}/sendMessage", data=data), timeout=15)
    except Exception as e:
        log("telegram failed", e)


class Store:
    """HF dataset (أو مجلد محلي للاختبار). الأخطاء غير 'غير موجود' تُرفع ولا تُبتلع، كي لا نُصفّر الحالة بسبب انقطاع شبكة."""
    def __init__(self):
        if LOCAL_HF:
            os.makedirs(LOCAL_HF, exist_ok=True)
        else:
            from huggingface_hub import HfApi
            self.api = HfApi(token=os.environ["HF_TOKEN"])

    def get(self, path):
        if LOCAL_HF:
            p = os.path.join(LOCAL_HF, path)
            return open(p, encoding="utf-8").read() if os.path.exists(p) else None
        from huggingface_hub import hf_hub_download
        from huggingface_hub.utils import EntryNotFoundError
        try:
            return open(hf_hub_download(HF_REPO, path, repo_type="dataset", token=os.environ["HF_TOKEN"], force_download=True), encoding="utf-8").read()
        except EntryNotFoundError:
            return None

    def put(self, path, text):
        if LOCAL_HF:
            p = os.path.join(LOCAL_HF, path); os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, "w", encoding="utf-8").write(text); return
        self._retry(lambda: self.api.upload_file(path_or_fileobj=text.encode(), path_in_repo=path, repo_id=HF_REPO, repo_type="dataset",
                                                 commit_message="factory " + path))

    def put_folder(self, folder, dest, replace=False):
        if LOCAL_HF:
            d = os.path.join(LOCAL_HF, dest); shutil.rmtree(d, ignore_errors=True); shutil.copytree(folder, d); return
        kw = {"delete_patterns": "*"} if replace else {}
        self._retry(lambda: self.api.upload_folder(folder_path=folder, path_in_repo=dest, repo_id=HF_REPO, repo_type="dataset",
                                                   commit_message="factory " + dest, **kw))

    @staticmethod
    def _retry(fn, n=4):
        for i in range(n):
            try:
                return fn()
            except Exception:
                if i == n - 1:
                    raise
                time.sleep(5 * (i + 1))


def sh(cmd, cwd=None, env_=None, timeout=None):
    """تشغيل في مجموعة عمليات مستقلة؛ عند انتهاء المهلة تُقتل المجموعة كلها."""
    p = subprocess.Popen(cmd, cwd=cwd, env=env_, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True)
    try:
        out, _ = p.communicate(timeout=timeout)
        return p.returncode, out or ""
    except subprocess.TimeoutExpired:
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except Exception:
            pass
        out, _ = p.communicate()
        return 124, (out or "") + "\n[timeout]"


def online(timeout=8):
    import socket
    try:
        for h in (("huggingface.co", 443), ("github.com", 443)):
            socket.create_connection(h, timeout=timeout).close()
        return True
    except Exception:
        return False


def wait_online():
    """ينتظر عودة الإنترنت ثم يكمل (بدون استهلاك): فحص كل 15 ثم حتى 120 ثانية."""
    delay, t0 = 15, time.time()
    while not online() and not STOP.is_set():
        STATUS["state"] = "offline"; STATUS["offline_since"] = STATUS.get("offline_since") or int(t0)
        log("offline; retry in", delay, "s"); STOP.wait(delay); delay = min(delay * 2, 120)
    if STATUS.get("offline_since"):
        log("back online after", int(time.time() - STATUS["offline_since"]), "s"); STATUS["offline_since"] = None; STATUS["state"] = "idle"


OUTBOX = os.path.join(WORK, "outbox")


def flush_outbox(store):
    """يرفع كل دورة منتهية لم تُرفع بعد (حزمة ثم حالة)؛ يبقى الصندوق إلى أن ينجح الرفع، حتى عبر إعادة تشغيل العملية."""
    for p in sorted(glob.glob(os.path.join(OUTBOX, "d*"))):
        cid = os.path.basename(p)
        while not STOP.is_set():
            try:
                wait_online()
                if os.path.isdir(os.path.join(p, "bundle")):
                    store.put_folder(os.path.join(p, "bundle"), "mutations_stream/" + cid)
                store.put("factory/state.json", open(os.path.join(p, "factory_state.json")).read())
                if os.path.exists(os.path.join(p, "seeds_consumed")):
                    store.put("factory/seeds.txt", "")
                shutil.rmtree(p, ignore_errors=True); log("outbox flushed", cid); break
            except Exception as e:
                log("outbox upload failed, will retry:", str(e)[:150]); STOP.wait(60)


def bootstrap_state():
    """أول تشغيل فقط: حالة مستودع GitHub العام الحالية (دورات Actions السابقة) كي لا نعيد تعدين ما أُنجز. بلا رمز."""
    url = "https://raw.githubusercontent.com/AbuYahyaAlalwi2/Marsad/main/state/factory_state.json"
    try:
        txt = urllib.request.urlopen(url, timeout=30).read().decode()
        s = json.loads(txt)
        if not isinstance(s, dict) or "done" not in s or "queue" not in s:
            raise ValueError("not a factory state")
        log("bootstrap: state from GitHub raw,", len(s["done"]), "done"); return txt
    except Exception as e:
        log("bootstrap: empty state (", e, ")")
        return json.dumps({"done": {}, "queue": [], "cursor": {"combo": 0, "page": 1}, "cycles": 0})


def clean_env(venv):
    keep = {k: os.environ[k] for k in ("HOME", "LANG", "LC_ALL", "TMPDIR") if k in os.environ}
    keep.update(PATH=os.path.join(venv, "bin") + os.pathsep + os.environ.get("PATH", ""), VIRTUAL_ENV=venv, PYTHONUNBUFFERED="1",
                PIP_NO_INPUT="1", PIP_DISABLE_PIP_VERSION_CHECK="1", PYTHONDONTWRITEBYTECODE="1")
    return keep


def run_repo(cyc, item, cfg):
    name, py = item["name"], item.get("py", "3.12")
    d = os.path.join(cyc, "w", name); os.makedirs(d, exist_ok=True)
    venv = os.path.join(d, "venv")
    t0 = time.time()
    try:
        rc, out = sh(["uv", "venv", "--seed", "--python", py, venv], timeout=600)
        if rc != 0:
            rc, out = sh(["uv", "venv", "--seed", "--python", "3.12", venv], timeout=600)
        if rc != 0:                       # أندرويد/تريمكس: لا تنزيل لبايثون مُدار، نستعمل بايثون النظام
            rc, out = sh(["uv", "venv", "--seed", "--python", sys.executable, venv], timeout=600)
        if rc != 0:
            log(name, "venv failed", out[-200:]); return
        e = clean_env(venv)
        sh([venv + "/bin/python", "-m", "pip", "install", "-q", "pytest", "pytest-timeout", "pytest-mock", "hypothesis", "pytest-asyncio"], cwd=d, env_=e, timeout=600)
        cmd = [venv + "/bin/python", os.path.join(HERE, "marsad_mut_mine_v12.py"), "--spec", os.path.join(cyc, "cycle_spec.json"), "--name", name,
               "--pins", os.path.join(cyc, "pins.json"), "--shard", "0", "--num-shards", "1", "--max-sites", str(cfg["max_sites"]),
               "--budget-min", str(cfg["budget"]), "--out", "out"]
        if cfg["fix_commits"] > 0:
            cmd += ["--fix-commits", str(cfg["fix_commits"]), "--fix-budget-min", str(cfg["fix_budget"])]
        if LLM["url"] and cfg["llm_sites"] > 0:
            cmd += ["--llm-url", LLM["url"], "--llm-sites", str(cfg["llm_sites"]), "--llm-budget-min", str(cfg["llm_budget"])]
        rc, out = sh(cmd, cwd=d, env_=e, timeout=int((cfg["budget"] + cfg["fix_budget"] + cfg.get("llm_budget", 0) + 25) * 60))
        res = os.path.join(cyc, "res"); os.makedirs(res, exist_ok=True)
        for f in glob.glob(os.path.join(d, "out", "*")):
            if os.path.isfile(f):
                shutil.copyfile(f, os.path.join(res, os.path.basename(f)))
        log(f"{name}: rc={rc} {int(time.time() - t0)}s :: {out.strip()[-160:]!r}")
    except Exception:
        log(name, "run_repo exception", traceback.format_exc()[-300:])
    finally:
        shutil.rmtree(d, ignore_errors=True)


def run_cycle(store, cfg):
    cid = time.strftime("d%Y%m%d-%H%M%S")
    cyc = os.path.join(WORK, cid)
    shutil.rmtree(cyc, ignore_errors=True); os.makedirs(os.path.join(cyc, "state"))
    st = store.get("factory/state.json")
    if st is None:
        st = bootstrap_state()
    open(os.path.join(cyc, "state", "factory_state.json"), "w").write(st)
    for f in glob.glob(os.path.join(HERE, "mut_repos_v*.json")):
        shutil.copy(f, cyc)
    seeds_txt = store.get("factory/seeds.txt") or ""
    seeds = [l.strip() for l in seeds_txt.splitlines() if "=" in l and not l.startswith("#")]
    e = dict(os.environ, GITHUB_OUTPUT=os.path.join(cyc, "gh_out.txt"))
    cmd = [sys.executable, os.path.join(HERE, "marsad_factory_state_v6.py"), "plan", "--batch", str(cfg["batch"]), "--shard", os.environ.get("SHARD", "1/2")]
    if seeds:
        cmd += ["--seed"] + seeds
    rc, out = sh(cmd, cwd=cyc, env_=e, timeout=1800)
    log("plan:", out.strip()[-200:])
    if rc != 0:
        raise RuntimeError("plan failed: " + out[-300:])
    matrix = {"include": []}
    for ln in open(os.path.join(cyc, "gh_out.txt")).read().splitlines() if os.path.exists(os.path.join(cyc, "gh_out.txt")) else []:
        if ln.startswith("matrix="):
            matrix = json.loads(ln[7:])
    items = matrix["include"]
    if not items:
        shutil.rmtree(cyc, ignore_errors=True)
        return {"cid": cid, "picked": 0, "records": 0}
    with ThreadPoolExecutor(max_workers=cfg["workers"]) as ex:
        list(ex.map(lambda it: run_repo(cyc, it, cfg), items))
    res = os.path.join(cyc, "res"); os.makedirs(res, exist_ok=True)
    if not online():                       # انقطاع أثناء التعدين: نتائجه غير موثوقة، نُسقط الدورة ونعيد التخطيط لاحقاً
        shutil.rmtree(cyc, ignore_errors=True); raise RuntimeError("offline during cycle; discarded (will re-plan)")
    rc, out = sh([sys.executable, os.path.join(HERE, "marsad_factory_state_v6.py"), "update", "--results", "res"], cwd=cyc, timeout=600)
    log("update:", out.strip()[-300:])
    report = json.load(open(os.path.join(cyc, "cycle_report.json"))) if os.path.exists(os.path.join(cyc, "cycle_report.json")) else {}
    rc, out = sh([sys.executable, os.path.join(HERE, "build_mut_bundle_v8.py"), "--in-dir", "res", "--out-dir", "bundle", "--cap-per-repo", "800",
                  "--specs", "cycle_spec.json"], cwd=cyc, timeout=900)
    bs = {}
    try:
        bs = json.load(open(os.path.join(cyc, "bundle", "stats.json")))
    except Exception:
        log("bundle failed", out[-300:])
    records = bs.get("train", 0) + bs.get("eval", 0)
    ob = os.path.join(OUTBOX, cid); os.makedirs(ob, exist_ok=True)               # الصندوق الصادر: يصمد أمام انقطاع الشبكة وإعادة التشغيل
    if records > 0:
        shutil.copytree(os.path.join(cyc, "bundle"), os.path.join(ob, "bundle"))
    shutil.copyfile(os.path.join(cyc, "state", "factory_state.json"), os.path.join(ob, "factory_state.json"))
    if seeds:
        open(os.path.join(ob, "seeds_consumed"), "w").write("1")
    shutil.rmtree(cyc, ignore_errors=True)
    flush_outbox(store)
    return {"cid": cid, "picked": len(items), "records": records, "real": bs.get("real_fix_pairs", 0), "report": report}


def consolidate(store):
    """إصدار موحّد بحارس: لا يستبدل release_latest إلا إن لم يصغر ولم يفقد eval."""
    if LOCAL_HF:
        sdir = os.path.join(LOCAL_HF, "mutations_stream"); extra = ["--stream-dir", sdir]
    else:
        extra = ["--hf-repo", HF_REPO]
    out = os.path.join(WORK, "release"); shutil.rmtree(out, ignore_errors=True)
    rc, o = sh([sys.executable, os.path.join(HERE, "consolidate_release_v4.py"), "--out", out] + extra, timeout=3000)
    if rc != 0:
        alert("consolidate", "consolidate failed: " + o[-300:]); return
    s = json.load(open(os.path.join(out, "stats.json")))
    total = s["train"] + s["eval"]
    if s["eval"] == 0 or total < STATUS.get("release_total", 0) * 0.98:
        alert("guard", f"release guard blocked upload (total={total}, eval={s['eval']}, prev={STATUS.get('release_total')})"); return
    store.put_folder(out, "release_latest", replace=True)
    STATUS["release_total"] = total
    log("release_latest uploaded", total)
    shutil.rmtree(out, ignore_errors=True)


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        b = json.dumps(STATUS, ensure_ascii=False).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(b)

    def log_message(self, *a):
        pass


def main():
    os.makedirs(WORK, exist_ok=True)
    for d in glob.glob(os.path.join(WORK, "d*")):         # الدورات غير المكتملة فقط؛ الصندوق الصادر يبقى
        shutil.rmtree(d, ignore_errors=True)
    os.makedirs(OUTBOX, exist_ok=True)
    signal.signal(signal.SIGTERM, lambda *a: STOP.set())
    if env("PORT", 0):
        threading.Thread(target=lambda: HTTPServer(("0.0.0.0", env("PORT", 0)), H).serve_forever(), daemon=True).start()
    store = Store()
    try:                                   # بوابة المزوّدين تعيش هنا فقط (المفاتيح لا تصل إلى المنقّب)
        from marsad_gateway import Gateway
        from marsad_llm_inject import serve
        gw = Gateway()
        if gw.available():
            _srv, port = serve(gw)
            LLM.update(url=f"http://127.0.0.1:{port}", gw=gw); STATUS["llm"] = gw.stats
            log("llm gateway up:", [p for p, _k in gw.keys].count("groq"), "groq keys,", len(gw.keys), "total")
        else:
            log("llm gateway: no keys, LLM injection disabled")
    except Exception:
        log("llm gateway failed", traceback.format_exc()[-300:])
    prev = store.get("factory/status.json")
    if prev:
        try:
            STATUS["release_total"] = json.loads(prev).get("release_total", 0)
            STATUS["cycles_done"] = json.loads(prev).get("cycles_done", 0)
        except Exception:
            pass
    def heartbeat():                       # نبضة كل 5 دقائق حتى أثناء الإيقاف/الانتظار/التعدين الطويل (للوحة التحكم)
        while not STOP.wait(300):
            try:
                STATUS["hb"] = int(time.time()); store.put("factory/status.json", json.dumps(STATUS, ensure_ascii=False))
            except Exception:
                pass
    threading.Thread(target=heartbeat, daemon=True).start()
    since_release = 0
    while not STOP.is_set():
        try:
            wait_online(); flush_outbox(store)
            ctl = json.loads(store.get("factory/control.json") or "{}")
            if not ctl.get("enabled", True):
                STATUS["state"] = "paused"; log("paused by control.json"); STOP.wait(300); continue
            if shutil.disk_usage(WORK).free < 2 * 1024 ** 3:
                alert("disk", "low disk space, skipping cycle"); STOP.wait(600); continue
            cfg = {"workers": int(ctl.get("workers", env("WORKERS", 2))), "batch": int(ctl.get("batch", env("BATCH", 6))),
                   "max_sites": env("MAX_SITES", 1500), "budget": env("BUDGET_MIN", 40.0), "fix_budget": env("FIX_BUDGET_MIN", 20.0),
                   "fix_commits": env("FIX_COMMITS", 800), "llm_sites": int(ctl.get("llm_sites", env("LLM_SITES", 40))),
                   "llm_budget": env("LLM_BUDGET_MIN", 10.0)}
            if not os.environ.get("GH_TOKEN"):
                STATUS["state"] = "needs_GH_TOKEN"
                alert("ghtoken", "GH_TOKEN is not set on the factory service (Railway > Variables); waiting")
                STOP.wait(600); continue
            STATUS["state"] = "running"
            r = run_cycle(store, cfg)
            STATUS.update(last_cycle=r, state="idle", host=os.environ.get("HOST_NAME", "railway"), llm_enabled=bool(LLM["url"]),
                          outbox=len(glob.glob(os.path.join(OUTBOX, "d*"))), cycles_done=STATUS["cycles_done"] + 1, last_ts=int(time.time()))
            since_release += 1
            if r["records"] == 0:
                STATUS["consecutive_zero"] += 1
                if STATUS["consecutive_zero"] >= 3:
                    alert("zero", f"{STATUS['consecutive_zero']} consecutive cycles with 0 records; sleeping 1h")
                    store.put("factory/status.json", json.dumps(STATUS)); STOP.wait(3600)
            else:
                STATUS["consecutive_zero"] = 0
            if since_release >= env("CONSOLIDATE_EVERY", 4) and r["records"] > 0:
                consolidate(store); since_release = 0
            store.put("factory/status.json", json.dumps(STATUS, ensure_ascii=False))
        except Exception:
            tb = traceback.format_exc()
            alert("cycle", "cycle exception: " + tb[-400:]); STATUS["state"] = "error"
            STOP.wait(300)
        if env("ONCE", 0):
            break
        STOP.wait(env("PAUSE_SEC", 30))


if __name__ == "__main__":
    main()
