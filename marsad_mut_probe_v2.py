#!/usr/bin/env python3
"""
marsad_mut_probe_v1.py — جدوى مصنع الطفرات: يحقن أعطالاً حتمية (AST) في مشروع حقيقي ويقيس كم منها تقتله الاختبارات.
لا LLM ولا أسرار. الطفرة المقتولة (تنجح الاختبارات قبلها وتفشل بعدها) = زوج متحقَّق بحقيقة أرضية.
الاستعمال في Actions:  --spec mut_repos.json --name <repo>     (محلياً: --dir <مجلد> --pkg <حزمة> --test-cmd "...")
"""
import argparse, ast, collections, difflib, glob, json, os, random, re, shlex, subprocess, sys, time

CMP = {ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE, ast.GtE: ast.Gt, ast.Eq: ast.NotEq,
       ast.NotEq: ast.Eq, ast.In: ast.NotIn, ast.NotIn: ast.In, ast.Is: ast.IsNot, ast.IsNot: ast.Is}
BIN = {ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.FloorDiv, ast.FloorDiv: ast.Mult}


def net_prefix():
    try:
        return ["unshare", "-rn"] if subprocess.run(["unshare", "-rn", "true"], capture_output=True, timeout=5).returncode == 0 else []
    except Exception:
        return []


NET = net_prefix()


def candidates(tree):
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            out += [(node, "cmp", i) for i, op in enumerate(node.ops) if type(op) in CMP]
        elif isinstance(node, ast.BinOp) and type(node.op) in BIN:
            out.append((node, "binop", 0))
        elif isinstance(node, ast.BoolOp):
            out.append((node, "boolop", 0))
        elif isinstance(node, ast.If):
            out.append((node, "if_negate", 0))
        elif isinstance(node, ast.Constant) and type(node.value) is int and abs(node.value) < 1000:
            out.append((node, "int_const", 0))
        elif isinstance(node, ast.Constant) and type(node.value) is bool:
            out.append((node, "bool_flip", 0))
        elif isinstance(node, ast.Return) and node.value is not None and not (
                isinstance(node.value, ast.Constant) and node.value.value is None):
            out.append((node, "return_none", 0))
    return out


def apply(node, kind, sub):
    if kind == "cmp":
        node.ops[sub] = CMP[type(node.ops[sub])]()
    elif kind == "binop":
        node.op = BIN[type(node.op)]()
    elif kind == "boolop":
        node.op = ast.Or() if isinstance(node.op, ast.And) else ast.And()
    elif kind == "if_negate":
        node.test = ast.UnaryOp(op=ast.Not(), operand=node.test)
    elif kind == "int_const":
        node.value += 1
    elif kind == "bool_flip":
        node.value = not node.value
    elif kind == "return_none":
        node.value = ast.Constant(value=None)


def mutate(src, idx):
    tree = ast.parse(src)
    cands = candidates(tree)
    node, kind, sub = cands[idx]
    line = getattr(node, "lineno", 0)
    apply(node, kind, sub)
    ast.fix_missing_locations(tree)
    return ast.unparse(tree), kind, line


def run(cmd, cwd, timeout, env):
    t0 = time.perf_counter()
    try:
        p = subprocess.run(NET + cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env)
        return p.returncode, p.stdout + "\n" + p.stderr, time.perf_counter() - t0
    except subprocess.TimeoutExpired:
        return "timeout", "", time.perf_counter() - t0


def first_failure(out):
    m = re.search(r"^FAILED (\S+)(?: - (.*))?$", out, re.M)
    if m:
        return m.group(1), (m.group(2) or "")[:200]
    m = re.search(r"^(?:FAIL|ERROR): (.+)$", out, re.M)
    return (m.group(1), "") if m else ("", "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec")
    ap.add_argument("--name")
    ap.add_argument("--dir")
    ap.add_argument("--pkg")
    ap.add_argument("--test-cmd")
    ap.add_argument("--mutants", type=int, default=40)
    ap.add_argument("--budget-min", type=float, default=12)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    rep = {"name": a.name or os.path.basename(a.dir or "local"), "t_start": time.time()}
    env = dict(os.environ, SETUPTOOLS_SCM_PRETEND_VERSION="0.0.0", PYTHONHASHSEED="0")
    if a.spec:
        spec = next(s for s in json.load(open(a.spec)) if s["name"] == a.name)
        d = a.name.replace("/", "_")
        subprocess.run(["git", "clone", "--depth", "1", "-q", spec["url"], d], check=True)
        rep["commit"] = subprocess.run(["git", "-C", d, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        lic = ""
        for f in glob.glob(os.path.join(d, "LICEN*")) + glob.glob(os.path.join(d, "COPYING*")):
            lic = open(f, errors="replace").read(600)
            break
        rep["license_guess"] = ("MIT" if re.search(r"\bMIT\b|Permission is hereby granted", lic) else
                                "Apache-2.0" if "Apache License" in lic else
                                "BSD" if re.search(r"Redistribution and use|BSD", lic) else "UNKNOWN")
        inst = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-e", d] + spec.get("extras", []),
                              capture_output=True, text=True, env=env)
        rep["install_ok"] = inst.returncode == 0
        if inst.returncode != 0:
            rep["install_tail"] = (inst.stderr or inst.stdout)[-400:]
        pkg, tests = spec["pkg"], spec["tests"]
        cmd = [sys.executable, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", "-o", "addopts=", "-rf",
               "--no-header", "--timeout=60", tests]
    else:
        d, pkg = a.dir, a.pkg
        cmd = shlex.split(a.test_cmd)
        rep["license_guess"], rep["install_ok"] = "n/a", True
    d = os.path.abspath(d)
    env["PYTHONPATH"] = d + os.pathsep + env.get("PYTHONPATH", "")
    target = os.path.join(d, pkg)
    if os.path.exists(target):
        files = [target] if target.endswith(".py") else sorted(glob.glob(os.path.join(target, "**", "*.py"), recursive=True))
    else:  # اكتشاف تلقائي إذا تغيّر تخطيط المستودع
        rep["pkg_autodiscovered"] = True
        files = [f for f in sorted(glob.glob(os.path.join(d, "**", "*.py"), recursive=True))
                 if not re.search(r"/(docs?|benchmarks?|examples?|scripts?|\.git|\.github|build)/", f)]
    files = [f for f in files if not re.search(r"(^|/)(tests?|testing|conftest)|test_|_test\.py$|setup\.py$|/_version\.py$", f)
             and os.path.getsize(f) < 200_000]
    rep["source_files"] = len(files)
    if not files:
        rep["error"] = "no_source_files_found"
        rep["dir_listing"] = sorted(os.listdir(d))[:30]
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        json.dump(rep, open(f"probe_{rep['name']}.json", "w"), ensure_ascii=False, indent=2)
        return
    # أساس: يجب أن تنجح الاختبارات الأصلية (داخل عزل الشبكة إن توفّر)
    rc, out, base_s = run(cmd, d, 600, env)
    rep["baseline"] = {"ok": rc == 0, "exit": rc, "seconds": round(base_s, 1), "tail": out.strip().splitlines()[-1:][:1]}
    if rc != 0:
        rep["baseline"]["fail_tail"] = out[-500:]
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        json.dump(rep, open(f"probe_{rep['name']}.json", "w"), ensure_ascii=False, indent=2)
        return
    originals, sites = {}, []
    for f in files:
        try:
            src = open(f, encoding="utf-8").read()
            tree = ast.parse(src)
        except Exception:
            continue
        originals[f] = (src, ast.unparse(tree))
        sites += [(f, i) for i in range(len(candidates(tree)))]
    rep["mutation_sites_total"] = len(sites)
    random.Random(a.seed).shuffle(sites)
    cnt, samples, kinds = collections.Counter(), [], collections.Counter()
    mut_timeout = min(300, max(20, base_s * 4))
    t_budget = time.time() + a.budget_min * 60
    t_mut = time.time()
    for f, i in sites[: a.mutants]:
        if time.time() > t_budget:
            cnt["stopped_budget"] += 1
            break
        src, orig_unp = originals[f]
        try:
            msrc, kind, line = mutate(src, i)
        except Exception:
            cnt["mutation_failed"] += 1
            continue
        if msrc == orig_unp:
            cnt["equivalent_text"] += 1
            continue
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
            cnt["killed"] += 1
            kinds[kind] += 1
            if len(samples) < 6:
                tn, msg = first_failure(out)
                diff = "".join(difflib.unified_diff(orig_unp.splitlines(True), msrc.splitlines(True), "orig.py", "mutant.py", n=2))
                samples.append({"file": os.path.relpath(f, d), "line": line, "kind": kind, "failing_test": tn,
                                "message": msg, "diff": diff[:1200]})
        else:
            cnt["broken_exit_%s" % rc] += 1
    wall = time.time() - t_mut
    n = sum(cnt[k] for k in cnt if k in ("killed", "survived", "timeout") or k.startswith("broken"))
    rep.update(counts=dict(cnt), tried=n, wall_seconds=round(wall, 1), killed_by_kind=dict(kinds), samples=samples,
               kill_rate=round(cnt["killed"] / n, 3) if n else None,
               killed_per_cpu_hour=round(cnt["killed"] / (wall / 3600)) if wall and cnt["killed"] else 0,
               mutants_per_minute=round(n / (wall / 60), 1) if wall else None)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    json.dump(rep, open(f"probe_{rep['name']}.json", "w"), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
