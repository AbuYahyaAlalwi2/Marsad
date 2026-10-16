#!/usr/bin/env python3
"""
marsad_mut_mine_v1.py — مصنع الطفرات: يحقن أعطالاً حتمية (AST) في مستودع حقيقي مثبَّت على SHA،
ويقبل الطفرة فقط إذا: نجحت الاختبارات الأصلية، وفشل ≥1 اختبار بعد الطفرة. بلا LLM وبلا أسرار.
يُخرج سجلاً لكل طفرة مقتولة (مستوى الدالة) + إحصاءات. الاستعمال:
  python3 marsad_mut_mine_v1.py --spec mut_repos_v3.json --name X --shard 0 --num-shards 1 --pins pins.json
"""
import argparse, ast, difflib, glob, gzip, hashlib, json, os, platform, random, re, shutil, subprocess, sys, time
from marsad_mut_probe_v2 import candidates, apply, run


def first_failure(out):
    for m in re.finditer(r"^(FAILED|ERROR) (\S+)(?: - (.*))?$", out, re.M):
        if m.group(2) != "collecting":
            return m.group(2), ((m.group(1) + ": " + (m.group(3) or ""))[:200])
    m = re.search(r"^(?:FAIL|ERROR): (\S.*)$", out, re.M)
    if m:
        return m.group(1)[:200], "unittest"
    return "", ""


SRC_EXCL = re.compile(r"(^|/)(tests?|testing|conftest)|test_|_test\.py$|setup\.py$|/_version\.py$|/(docs?|benchmarks?|examples?|scripts?|build)/")


def parents_map(tree):
    return {c: p for p in ast.walk(tree) for c in ast.iter_child_nodes(p)}


def mutate_ctx(src, idx):
    tree = ast.parse(src)
    node, kind, sub = candidates(tree)[idx]
    pm, fn = parents_map(tree), node
    while fn is not None and not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
        fn = pm.get(fn)
    if fn is None:
        return None
    before = ast.unparse(fn)
    line = getattr(node, "lineno", 0)
    apply(node, kind, sub)
    ast.fix_missing_locations(tree)
    return ast.unparse(tree), kind, line, before, ast.unparse(fn), fn.name


HEAVY = re.compile(r"\b(torch|pytorch|tensorflow|transformers|jaxlib|jax|nvidia|cuda|onnxruntime|vllm|xformers|bitsandbytes|faiss)\b")


PIPMAP = {"yaml": "pyyaml", "PIL": "pillow", "bs4": "beautifulsoup4", "dateutil": "python-dateutil", "OpenSSL": "pyopenssl", "jwt": "pyjwt",
          "attr": "attrs", "dotenv": "python-dotenv", "git": "gitpython", "serial": "pyserial", "zmq": "pyzmq", "magic": "python-magic"}


def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--pins")
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--num-shards", type=int, default=1)
    ap.add_argument("--max-sites", type=int, default=300)
    ap.add_argument("--budget-min", type=float, default=330)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default="out")
    ap.add_argument("--fix-commits", type=int, default=0)
    ap.add_argument("--fix-budget-min", type=float, default=30)
    a = ap.parse_args()
    spec = next(s for s in json.load(open(a.spec)) if s["name"] == a.name)
    os.makedirs(a.out, exist_ok=True)
    env = dict(os.environ, SETUPTOOLS_SCM_PRETEND_VERSION="0.0.0", PYTHONHASHSEED="0", PYTHONDONTWRITEBYTECODE="1")
    d = a.name
    pin = (json.load(open(a.pins)) if a.pins else {}).get(a.name)
    sh(["git", "init", "-q", d]); sh(["git", "-C", d, "remote", "add", "origin", spec["url"]])
    ref = pin or "HEAD"
    if spec.get("full") and pin:       # نسخة كاملة مع الوسوم (attrs وأمثاله)
        if sh(["git", "-C", d, "fetch", "-q", "--tags", "origin"]).returncode != 0:
            sys.exit("fetch failed")
        sh(["git", "-C", d, "checkout", "-q", pin])
    else:
        if sh(["git", "-C", d, "fetch", "--depth", "1", "-q", "origin", ref]).returncode != 0:
            sys.exit("fetch failed")
        sh(["git", "-C", d, "checkout", "-q", "FETCH_HEAD"])
    if spec.get("submodules"):
        sh(["git", "-C", d, "submodule", "update", "--init", "--recursive", "--depth", "1"])
    sha = sh(["git", "-C", d, "rev-parse", "HEAD"]).stdout.strip()
    lic = ""
    for f in glob.glob(os.path.join(d, "LICEN*")) + glob.glob(os.path.join(d, "COPYING*")):
        lic = open(f, errors="replace").read(800); break
    license_id = ("MIT" if re.search(r"\bMIT\b|Permission is hereby granted", lic) else "Apache-2.0" if "Apache License" in lic
                  else "BSD" if re.search(r"Redistribution and use|BSD", lic) else "UNKNOWN")
    stats = {"repo": a.name, "commit": sha, "license": license_id, "shard": a.shard, "num_shards": a.num_shards}
    if license_id == "UNKNOWN":
        stats["error"] = "license_unknown_rejected"; json.dump(stats, open(f"{a.out}/mutstats_{a.name}_{a.shard}.json", "w")); print(stats); return
    auto = "tests" not in spec or "pkg" not in spec
    if auto:
        blob = ""
        try:                                            # pyproject: التبعيات الأساسية فقط (الاختيارية لا تُحتسب)
            import tomllib
            blob += " ".join(tomllib.load(open(os.path.join(d, "pyproject.toml"), "rb")).get("project", {}).get("dependencies", [])).lower()
        except Exception:
            pass
        for fp in [os.path.join(d, n) for n in ("setup.py", "setup.cfg")] + glob.glob(os.path.join(d, "requirements*.txt")) + glob.glob(os.path.join(d, "requirements", "*.txt")):
            try:
                blob += "\n".join(l for l in open(fp, errors="replace").read().lower().splitlines() if not l.lstrip().startswith("#"))
            except Exception:
                pass
        if HEAVY.search(blob):
            stats["error"] = "heavy_deps_rejected"
            json.dump(stats, open(f"{a.out}/mutstats_{a.name}_{a.shard}.json", "w")); print(stats); return
        inst = None
        for grp in ("test", "tests", "testing", "dev", ""):
            inst = sh([sys.executable, "-m", "pip", "install", "-q", "-e", f"./{d}[{grp}]" if grp else f"./{d}"], env=env)
            if inst.returncode == 0:
                break
        try:                                            # PEP 735: [dependency-groups] test/tests/dev
            import tomllib
            pp = os.path.join(d, "pyproject.toml")
            if os.path.exists(pp):
                grp = tomllib.load(open(pp, "rb")).get("dependency-groups", {})
                reqs = []
                for g in ("test", "tests", "testing", "dev"):
                    reqs += [x for x in grp.get(g, []) if isinstance(x, str)]
                tl = tomllib.load(open(pp, "rb")).get("tool", {})
                for k in ("rye", "uv"):
                    reqs += [x for x in (tl.get(k, {}).get("dev-dependencies", []) or []) if isinstance(x, str) and not x.startswith("-e")]
                reqs = [x for x in reqs if not HEAVY.search(x.lower())]
                if reqs:
                    sh([sys.executable, "-m", "pip", "install", "-q"] + reqs, env=env)
        except Exception:
            pass
        for rq in ("requirements-test.txt", "test-requirements.txt", "requirements/test.txt", "requirements/tests.txt", "requirements-dev.txt"):
            if os.path.exists(os.path.join(d, rq)):
                sh([sys.executable, "-m", "pip", "install", "-q", "-r", os.path.join(d, rq)], env=env)
                break
    else:
        inst = sh([sys.executable, "-m", "pip", "install", "-q", "-e", d] + spec.get("extras", []), env=env)
    if inst.returncode != 0:
        stats["error"] = "install_failed"; stats["tail"] = (inst.stderr or inst.stdout)[-300:]
        json.dump(stats, open(f"{a.out}/mutstats_{a.name}_{a.shard}.json", "w")); print(stats); return
    d = os.path.abspath(d)
    env["PYTHONPATH"] = d + os.pathsep + env.get("PYTHONPATH", "")
    env_digest = hashlib.sha256((platform.python_version() + sh([sys.executable, "-m", "pip", "freeze"]).stdout).encode()).hexdigest()[:16]
    if auto:
        spec = dict(spec)
        spec["tests"] = next((c for c in ("tests", "test") if os.path.isdir(os.path.join(d, c))), ".")
        spec["pkg"] = "."
    cmd = [sys.executable, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", "-o", "addopts=", "-rfE", "--no-header",
           "--timeout=60", spec["tests"]] + [x for t in spec.get("deselect", []) for x in ("--deselect", t)]
    cmd += list(spec.get("pytest_args", []))
    if spec.get("unittest"):
        cmd = [sys.executable, "-m", "unittest", "discover", "-s", spec["tests"]]
    target = os.path.join(d, spec["pkg"])
    if os.path.exists(target):
        files = [target] if target.endswith(".py") else glob.glob(os.path.join(target, "**", "*.py"), recursive=True)
    else:
        files = glob.glob(os.path.join(d, "**", "*.py"), recursive=True)
    files = sorted(f for f in files if not SRC_EXCL.search(os.path.relpath(f, d)) and os.path.getsize(f) < 200_000)
    if auto:   # فقط الملفات داخل حزم حقيقية (مجلد فيه __init__.py) أو src/<pkg>
        def in_pkg(f):
            parts = os.path.relpath(f, d).split(os.sep)
            top = parts[1] if parts[0] == "src" and len(parts) > 2 else parts[0]
            base = os.path.join(d, "src", top) if parts[0] == "src" and len(parts) > 2 else os.path.join(d, top)
            return len(parts) > 1 and os.path.exists(os.path.join(base, "__init__.py"))
        files = [f for f in files if in_pkg(f)]
        if not files:
            stats["error"] = "no_package_found"
            json.dump(stats, open(f"{a.out}/mutstats_{a.name}_{a.shard}.json", "w")); print(stats); return
    if auto and not spec.get("unittest"):
        cmd += ["-o", "asyncio_mode=auto"]
        probe = [x for x in cmd if x != "-x"]
        excl, dropped, tried_mods = [], [], set()
        for _ in range(10):
            rc, out, _s = run(probe + excl, d, 900, env)
            if rc == 0 or rc == 5:
                break
            miss = [m.split(".")[0] for m in re.findall(r"No module named '([^']+)'", out)]
            miss = [m for m in dict.fromkeys(miss) if m not in tried_mods and not HEAVY.search(m.lower())
                    and not os.path.exists(os.path.join(d, m)) and not os.path.exists(os.path.join(d, m + ".py"))
                    and not os.path.exists(os.path.join(d, "src", m)) and not m.startswith("_") and m != "tests"]
            if miss and len(tried_mods) < 8:             # تبعية اختبار ناقصة: ثبّتها وأعد المحاولة
                for m in miss:
                    tried_mods.add(m)
                    sh([sys.executable, "-m", "pip", "install", "-q", PIPMAP.get(m, m)], env=env)
                continue
            bad = re.findall(r"^(?:FAILED|ERROR) (\S+)", out, re.M)
            if not bad or len(dropped) + len(bad) > 40:
                break
            for b in bad:
                dropped.append(b)
                excl += ["--ignore=" + b.split("::")[0]] if "::" not in b else ["--deselect", b]
        cmd += excl
        stats["auto_excluded"] = dropped[:40]; stats["auto_installed"] = sorted(tried_mods)
    rc, out, base_s = run(cmd, d, 900, env)
    stats["baseline_ok"] = rc == 0
    if rc != 0:
        stats["error"] = "baseline_failed"; stats["tail"] = out[-400:]
        json.dump(stats, open(f"{a.out}/mutstats_{a.name}_{a.shard}.json", "w")); print(stats); return
    fix_recs = []
    if a.fix_commits > 0:                       # المستوى الثالث: أخطاء حقيقية من تاريخ git (نفس البيئة المثبّتة)
        if not spec.get("full"):
            sh(["git", "-C", d, "fetch", "--depth", str(a.fix_commits + 60), "-q", "origin", ref])
        fdir = os.path.join(os.path.abspath(a.out), "_fix")
        fr = subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "marsad_fix_mine_v2.py"),
                             "--repo", d, "--name", a.name, "--license", license_id, "--max-commits", str(a.fix_commits),
                             "--budget-min", str(a.fix_budget_min), "--out", fdir], capture_output=True, text=True)
        try:
            stats["fix"] = json.load(open(os.path.join(fdir, f"fixstats_{a.name}.json")))
            for ln in open(os.path.join(fdir, f"fixrecs_{a.name}.jsonl")):
                r = json.loads(ln)
                r.update(mutation_type="real_fix", line=None, env_digest=env_digest,
                         evidence_sha256=hashlib.sha256((r["failing_test"]["name"] + r["failing_test"]["message"] + r["diff"]).encode()).hexdigest(),
                         split="eval" if int(hashlib.sha1(a.name.encode()).hexdigest(), 16) % 100 < 15 else "train")
                fix_recs.append(r)
        except Exception as e:
            stats["fix_error"] = (fr.stderr or str(e))[-300:]
        shutil.rmtree(fdir, ignore_errors=True)
    originals, sites = {}, []
    for f in files:
        try:
            src = open(f, encoding="utf-8").read(); tree = ast.parse(src)
        except Exception:
            continue
        originals[f] = (src, ast.unparse(tree))
        sites += [(f, i) for i in range(len(candidates(tree)))]
    stats["sites_total"] = len(sites)
    random.Random(a.seed).shuffle(sites)           # ترتيب حتمي واحد لكل الشظايا
    sites = sites[: a.max_sites][a.shard :: a.num_shards]
    stats["sites_assigned"] = len(sites)
    mut_timeout = min(300, max(20, base_s * 4))
    deadline = time.time() + a.budget_min * 60
    cnt = {"killed": 0, "survived": 0, "timeout": 0, "no_function": 0, "equivalent": 0, "broken": 0, "unprocessed": 0}
    recs, t0, noname = [], time.time(), []
    for n, (f, i) in enumerate(sites):
        if time.time() > deadline:
            cnt["unprocessed"] = len(sites) - n; break
        src, orig_unp = originals[f]
        try:
            m = mutate_ctx(src, i)
        except Exception:
            cnt["broken"] += 1; continue
        if m is None:
            cnt["no_function"] += 1; continue
        msrc, kind, line, before, after, fname = m
        if msrc == orig_unp or before == after:
            cnt["equivalent"] += 1; continue
        try:
            open(f, "w", encoding="utf-8").write(msrc)
            rc, out, secs = run(cmd, d, mut_timeout, env)
        finally:
            open(f, "w", encoding="utf-8").write(src)
        if rc == "timeout":
            cnt["timeout"] += 1
        elif rc == 0:
            cnt["survived"] += 1
        elif rc == 1:
            tn, msg = first_failure(out)
            if not tn:
                cnt["broken_noname"] = cnt.get("broken_noname", 0) + 1
                if len(noname) < 3:
                    noname.append(out[-700:])
                continue
            cnt["killed"] += 1
            diff = "".join(difflib.unified_diff(before.splitlines(True), after.splitlines(True), "fixed", "buggy", n=3))
            rel = os.path.relpath(f, d)
            rid = hashlib.sha1(f"{a.name}|{sha}|{rel}|{i}".encode()).hexdigest()[:16]
            recs.append({
                "id": "mut" + rid, "origin": "procedural", "source": f"github:{a.name}", "repo": a.name,
                "commit_sha": sha, "license": license_id, "file": rel, "function": fname, "line": line,
                "mutation_type": kind, "fixed_code": before, "buggy_code": after, "diff": diff,
                "failing_test": {"name": tn, "message": msg},
                "label_confidence": "test-verified", "env_digest": env_digest,
                "evidence_sha256": hashlib.sha256((tn + msg + diff).encode()).hexdigest(),
                "split": "eval" if int(hashlib.sha1(a.name.encode()).hexdigest(), 16) % 100 < 15 else "train",
                "verified": True})
        else:
            k = "broken_rc%s" % rc
            cnt[k] = cnt.get(k, 0) + 1
    tried = cnt["killed"] + cnt["survived"] + cnt["timeout"]
    stats.update(noname_samples=noname, counts=cnt, tried=tried, kill_rate=round(cnt["killed"] / tried, 3) if tried else None,
                 wall_minutes=round((time.time() - t0) / 60, 1))
    recs = recs + fix_recs
    with gzip.open(f"{a.out}/muttriples_{a.name}_{a.shard}.jsonl.gz", "wt", encoding="utf-8") as fh:
        for r in recs:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    json.dump(stats, open(f"{a.out}/mutstats_{a.name}_{a.shard}.json", "w"), ensure_ascii=False, indent=2)
    print(json.dumps(stats, ensure_ascii=False))


if __name__ == "__main__":
    main()
