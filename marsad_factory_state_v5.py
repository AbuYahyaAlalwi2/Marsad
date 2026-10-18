#!/usr/bin/env python3
"""
marsad_factory_state_v1.py — قلب المصنع المستقل: طابور مشاريع + حالة + اكتشاف تلقائي (GitHub Search).
  plan   : يملأ الطابور عند الحاجة، يختار دفعة، يثبّت SHA، يكتب cycle_spec.json و pins.json ومصفوفة matrix
  update : يقرأ نتائج الدورة ويحدّث الحالة (mined / rejected / retry / failed) ويصدر تقرير شذوذ
الحالة في state/factory_state.json داخل المستودع (تُلتزم بعد كل دورة، فيبقى المستودع "نشطاً").
"""
import argparse, glob, json, os, re, subprocess, sys, time

LICENSES = ["mit", "apache-2.0", "bsd-3-clause", "bsd-2-clause"]
BANDS = [(1000, 4000), (300, 999), (100, 299), (4001, 20000), (40, 99)]
SKIP = re.compile(r"awesome|tutorial|course|leetcode|interview|cheat|handbook|learn|example|demo|homework|exercise|algorithms|boilerplate|template", re.I)
DENY = re.compile(r"pentest|exploit|vuln[-_]?claw|ssrf|mimikatz|pypykatz|hack|payload|crack|brute|red[-_]?team|malware|keylogger|ctf|metasploit|phish|botnet|ransom|c2[-_]|stealer|bypass", re.I)        # أدوات هجومية: لا يُنتج المصنع منها شيئاً
SHARD = (0, 1)    # (i, n): هذا المصنع يعالج فقط المشاريع التي sha1(name) % n == i  → لا تكرار بين المسارين (Actions / Railway)


def mine(name):
    import hashlib
    return int(hashlib.sha1(name.encode()).hexdigest(), 16) % SHARD[1] == SHARD[0]


REJECT = {"baseline_failed", "install_failed", "license_unknown_rejected", "no_package_found", "heavy_deps_rejected"}


def load(p):
    return json.load(open(p)) if os.path.exists(p) else {"done": {}, "queue": [], "cursor": {"combo": 0, "page": 1}, "cycles": 0}


def save(p, st):
    os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
    json.dump(st, open(p, "w"), ensure_ascii=False, indent=1, sort_keys=True)


def combos():
    return [(l, lo, hi) for (lo, hi) in BANDS for l in LICENSES]


def gh_search(lic, lo, hi, page):
    pushed = time.strftime("%Y-%m-%d", time.gmtime(time.time() - 730 * 86400))
    q = f"language:python license:{lic} stars:{lo}..{hi} archived:false fork:false size:300..40000 pushed:>{pushed}"
    r = subprocess.run(["gh", "api", "-X", "GET", "search/repositories", "-f", f"q={q}", "-f", "sort=stars",
                        "-f", "per_page=100", "-f", f"page={page}"], capture_output=True, text=True)
    if r.returncode != 0:
        return None
    return json.loads(r.stdout).get("items", [])


def refill(st, want, seeds=None):
    known = set(st["done"]) | {q["name"] for q in st["queue"]}
    if seeds is not None:
        for n, u in seeds:
            if n not in known and mine(n):
                st["queue"].append({"name": n, "url": u, "stars": 0}); known.add(n)
        return
    cs, tries = combos(), 0
    while len(st["queue"]) < want and tries < 40:
        c, p = st["cursor"]["combo"] % len(cs), st["cursor"]["page"]
        items = gh_search(*cs[c], p)
        tries += 1
        if items is None:
            break                                   # حدّ معدّل أو خطأ شبكة: نكمل في الدورة التالية
        for it in items:
            name = it["full_name"].replace("/", "__")
            if not mine(name):
                continue
            if name in known or SKIP.search(it["name"] + " " + (it.get("description") or "")) or DENY.search(it["full_name"] + " " + (it.get("description") or "")):
                continue
            st["queue"].append({"name": name, "url": it["html_url"], "stars": it["stargazers_count"]}); known.add(name)
        if len(items) < 100 or p >= 10:
            st["cursor"] = {"combo": c + 1, "page": 1}
        else:
            st["cursor"] = {"combo": c, "page": p + 1}
        time.sleep(2.2)                              # حد البحث: 30 طلباً/دقيقة


def root_ok(url):
    """مرشّح رخيص قبل التعدين: حزمة (pyproject/setup) + مجلد tests/test في الجذر."""
    r = subprocess.run(["gh", "api", "repos/" + url.split("github.com/")[1] + "/contents"], capture_output=True, text=True)
    if r.returncode != 0:
        return True                                  # خطأ شبكة: لا نرفض ظلماً
    try:
        names = {x["name"].lower() for x in json.loads(r.stdout)}
    except Exception:
        return True
    return bool(names & {"pyproject.toml", "setup.py", "setup.cfg"}) and bool(names & {"tests", "test"})


def py_for(url):
    """إصدار بايثون للمشغّل: الأعلى بين 3.12 و requires-python (حتى 3.14)."""
    r = subprocess.run(["gh", "api", "repos/" + url.split("github.com/")[1] + "/contents/pyproject.toml",
                        "-H", "Accept: application/vnd.github.raw"], capture_output=True, text=True)
    m = re.search(r"requires-python\s*=\s*[\"']\s*>=\s*3\.(\d+)", r.stdout) if r.returncode == 0 else None
    return "3.%d" % min(14, max(12, int(m.group(1)))) if m else "3.12"


def pin(url):
    r = subprocess.run(["git", "ls-remote", url, "HEAD"], capture_output=True, text=True)
    return r.stdout.split()[0] if r.stdout.split() else None


def cmd_plan(a):
    global SHARD
    if a.shard:
        i, n = a.shard.split("/"); SHARD = (int(i), int(n))
    st = load(a.state)
    st["queue"] = [q for q in st["queue"] if mine(q["name"])]
    for sp in glob.glob("mut_repos_v*.json"):                    # المشاريع اليدوية السابقة تُعدّ منجزة
        for r in json.load(open(sp)):
            n = re.sub(r"2$", "", r["name"]) if r["name"] in ("attrs2", "pyparsing2", "rich2") else r["name"]
            st["done"].setdefault(n, {"status": "manual", "ts": int(time.time())})
    seeds = [tuple(x.split("=", 1)) for x in a.seed] if a.seed else None
    seeds_given = seeds is not None
    refill(st, a.batch * 3, seeds)
    picked, rest = [], []
    for q in st["queue"]:
        if len(picked) < a.batch and q["name"] not in st["done"]:
            if not seeds_given and not root_ok(q["url"]):
                st["done"][q["name"]] = {"status": "rejected", "error": "prefilter_no_pkg_or_tests", "ts": int(time.time())}; continue
            sha = pin(q["url"])
            if sha:
                q["sha"] = sha; q["py"] = py_for(q["url"]); picked.append(q); continue
            st["done"][q["name"]] = {"status": "rejected", "error": "no_head", "ts": int(time.time())}; continue
        if q["name"] not in st["done"]:
            rest.append(q)
    st["queue"] = rest
    st["inflight"] = {q["name"]: {"url": q["url"], "sha": q["sha"], "attempts": q.get("attempts", 0) + 1} for q in picked}
    st["cycles"] = st.get("cycles", 0) + 1
    save(a.state, st)
    json.dump([{"name": q["name"], "url": q["url"], "shards": 1} for q in picked], open("cycle_spec.json", "w"))
    json.dump({q["name"]: q["sha"] for q in picked}, open("pins.json", "w"))
    matrix = {"include": [{"name": q["name"], "shard": 0, "n": 1, "py": q.get("py", "3.12")} for q in picked]}
    if os.environ.get("GITHUB_OUTPUT"):
        open(os.environ["GITHUB_OUTPUT"], "a").write(f"matrix={json.dumps(matrix)}\ncount={len(picked)}\n")
    print(f"cycle {st['cycles']}: picked {len(picked)}, queue left {len(st['queue'])}, done {len(st['done'])}")


def cmd_update(a):
    st = load(a.state)
    res, report = {}, {"mined": 0, "rejected": 0, "retry": 0, "failed": 0, "pairs": 0}
    for f in glob.glob(os.path.join(a.results, "**", "mutstats_*.json"), recursive=True):
        s = json.load(open(f)); res[s["repo"]] = s
    for name, inf in st.get("inflight", {}).items():
        s = res.get(name)
        if s is None:                                                  # لا نتيجة: غالباً توقّف الجهاز → إعادة محاولة واحدة
            if inf["attempts"] >= 2:
                st["done"][name] = {"status": "failed", "error": "no_result", "ts": int(time.time())}; report["failed"] += 1
            else:
                st["queue"].insert(0, {"name": name, "url": inf["url"], "stars": 0, "attempts": inf["attempts"]}); report["retry"] += 1
        elif s.get("error") in REJECT or s.get("error"):
            st["done"][name] = {"status": "rejected", "error": s.get("error"), "sha": s.get("commit"), "ts": int(time.time())}; report["rejected"] += 1
        else:
            k = (s.get("counts") or {}).get("killed", 0)
            st["done"][name] = {"status": "mined", "sha": s.get("commit"), "killed": k, "kill_rate": s.get("kill_rate"), "ts": int(time.time())}
            report["mined"] += 1; report["pairs"] += k
    st["inflight"] = {}
    save(a.state, st)
    report["queue_left"], report["done_total"] = len(st["queue"]), len(st["done"])
    anomaly = []
    if report["pairs"] == 0:
        anomaly.append("الدورة لم تنتج أي زوج")
    tot = report["mined"] + report["rejected"] + report["failed"]
    if tot >= 5 and report["rejected"] / tot > 0.9:
        anomaly.append("أكثر من 90% من المشاريع رُفضت (تحقق من تغيّر البيئة)")
    report["anomaly"] = anomaly
    json.dump(report, open("cycle_report.json", "w"), ensure_ascii=False, indent=1)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="c", required=True)
    p = sub.add_parser("plan"); p.add_argument("--state", default="state/factory_state.json"); p.add_argument("--batch", type=int, default=20); p.add_argument("--seed", nargs="*"); p.add_argument("--shard", default="")
    u = sub.add_parser("update"); u.add_argument("--state", default="state/factory_state.json"); u.add_argument("--results", default="res")
    a = ap.parse_args()
    cmd_plan(a) if a.c == "plan" else cmd_update(a)
