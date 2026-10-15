#!/usr/bin/env python3
"""
marsad_fix_mine_v1.py — المستوى الثالث: أخطاء حقيقية من تاريخ git.
لكل commit يغيّر كوداً (≤ --max-src ملف) ويضيف/يعدّل اختباراً:
  1) على الـcommit نفسه (الإصلاح): اختبارات الملفات المتغيّرة تنجح.
  2) على أبيه + نسخة الاختبارات من الـcommit: ≥1 اختبار يفشل.
  إن تحقق الشرطان فهو زوج حقيقي (خطأ بشري → إصلاحه → اختبار يفرّق بينهما). بلا LLM وبلا أسرار.
الاستعمال: python3 marsad_fix_mine_v1.py --repo DIR --name X --max-commits 400 --out out [--pkg-prefix toolz/]
يفترض أن بيئة التبعيات مثبّتة مسبقاً (pip install للمشروع على HEAD)، ويشغّل كل نسخة بـPYTHONPATH خاص بها.
"""
import argparse, ast, difflib, hashlib, json, os, re, shutil, subprocess, sys, tempfile, time

TEST_RE = re.compile(r"(^|/)(tests?|testing)/|(^|/)test_[^/]*\.py$|_test\.py$|(^|/)conftest\.py$")


def sh(cmd, cwd=None, env=None, timeout=None):
    return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)


def is_test(p):
    return bool(TEST_RE.search(p))


def funcs(src):
    """{qualname: unparse} لكل دالة في الملف."""
    try:
        tree = ast.parse(src)
    except Exception:
        return {}
    out = {}

    def walk(node, pre):
        for ch in ast.iter_child_nodes(node):
            if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)):
                out[pre + ch.name] = ast.unparse(ch)
                walk(ch, pre + ch.name + ".")
            elif isinstance(ch, ast.ClassDef):
                walk(ch, pre + ch.name + ".")
    walk(tree, "")
    return out


def run_tests(wt, files, env, timeout=240):
    cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-o", "addopts=", "-rfE", "--no-header", "-x"] + files
    try:
        r = sh(cmd, cwd=wt, env=env, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 99, "timeout"
    return r.returncode, r.stdout + r.stderr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--license", default="UNKNOWN")
    ap.add_argument("--max-commits", type=int, default=400)
    ap.add_argument("--max-src", type=int, default=3)
    ap.add_argument("--max-lines", type=int, default=120)
    ap.add_argument("--budget-min", type=float, default=60)
    ap.add_argument("--out", default="out")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    repo = os.path.abspath(a.repo)
    deadline = time.time() + a.budget_min * 60
    revs = sh(["git", "-C", repo, "log", "--no-merges", "--format=%H", f"-n{a.max_commits}"]).stdout.split()
    stats = {"repo": a.name, "commits_scanned": 0, "candidates": 0, "accepted_commits": 0, "pairs": 0,
             "rej": {"fixed_fails": 0, "parent_passes": 0, "timeout": 0, "no_func_change": 0}}
    recs = []
    tmp = tempfile.mkdtemp(prefix="fixmine_")
    env0 = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONHASHSEED="0")
    for c in revs:
        if time.time() > deadline:
            break
        stats["commits_scanned"] += 1
        parents = sh(["git", "-C", repo, "rev-list", "--parents", "-n1", c]).stdout.split()[1:]
        if len(parents) != 1:
            continue
        p = parents[0]
        files = sh(["git", "-C", repo, "diff", "--name-status", p, c]).stdout.splitlines()
        src, tst = [], []
        for ln in files:
            st, _, path = ln.partition("\t")
            if st not in ("M", "A") or not path.endswith(".py"):
                if st != "M" and st != "A":
                    src = None; break
                continue
            (tst if is_test(path) else src).append((st, path))
        if not src or not tst or len(src) > a.max_src or any(s != "M" for s, _ in src):
            continue
        nl = sum(1 for l in sh(["git", "-C", repo, "diff", "-U0", p, c, "--"] + [x for _, x in src]).stdout.splitlines()
                 if l[:1] in "+-" and l[:3] not in ("+++", "---"))
        if nl > a.max_lines:
            continue
        stats["candidates"] += 1
        wf, wp = os.path.join(tmp, "fix"), os.path.join(tmp, "par")
        for w, rev in ((wf, c), (wp, p)):
            shutil.rmtree(w, ignore_errors=True)
            sh(["git", "-C", repo, "worktree", "add", "-q", "--detach", w, rev])
        if not (os.path.isdir(wf) and os.path.isdir(wp)):    # الأب خارج التاريخ الضحل
            stats["rej"]["no_parent_in_clone"] = stats["rej"].get("no_parent_in_clone", 0) + 1
            for w in (wf, wp):
                sh(["git", "-C", repo, "worktree", "remove", "--force", w])
            continue
        for _, tp in tst:                                   # نسخة اختبارات الإصلاح فوق الأب
            dst = os.path.join(wp, tp)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(os.path.join(wf, tp), dst)
        tfiles = [x for _, x in tst if os.path.basename(x).startswith("test_") or x.endswith("_test.py") or "/test" in x]
        tfiles = [x for x in tfiles if os.path.exists(os.path.join(wf, x))] or [x for _, x in tst if os.path.exists(os.path.join(wf, x))]
        ef = dict(env0, PYTHONPATH=wf); ep = dict(env0, PYTHONPATH=wp)
        rcf, outf = run_tests(wf, tfiles, ef)
        if rcf != 0:
            stats["rej"]["timeout" if rcf == 99 else "fixed_fails"] += 1
        else:
            rcp, outp = run_tests(wp, tfiles, ep)
            if rcp == 0:
                stats["rej"]["parent_passes"] += 1
            elif rcp == 99:
                stats["rej"]["timeout"] += 1
            else:
                m = re.search(r"^(?:FAILED|ERROR) (\S+)(?: - (.*))?$", outp, re.M)
                ft = {"name": m.group(1), "message": (m.group(2) or "")[:300]} if m else {"name": "?", "message": outp[-300:]}
                msg = sh(["git", "-C", repo, "log", "-1", "--format=%s", c]).stdout.strip()
                n_before = len(recs)
                for _, sp in src:
                    bsrc, fsrc = sh(["git", "-C", repo, "show", f"{p}:{sp}"]).stdout, sh(["git", "-C", repo, "show", f"{c}:{sp}"]).stdout
                    fb, ff = funcs(bsrc), funcs(fsrc)
                    for q in sorted(set(fb) & set(ff)):
                        if fb[q] != ff[q] and len(fb[q]) < 6000 and len(ff[q]) < 6000:
                            diff = "".join(difflib.unified_diff(fb[q].splitlines(True), ff[q].splitlines(True), "buggy", "fixed"))
                            recs.append({"id": "fix" + hashlib.sha1(f"{a.name}|{c}|{sp}|{q}".encode()).hexdigest()[:16],
                                         "origin": "real_commit", "source": f"github:{a.name}", "repo": a.name,
                                         "commit_sha": c, "parent_sha": p, "license": a.license, "file": sp, "function": q,
                                         "commit_message": msg[:200], "buggy_code": fb[q], "fixed_code": ff[q], "diff": diff,
                                         "failing_test": ft, "tests_changed": [x for _, x in tst][:6],
                                         "label_confidence": "test-verified-real-fix", "verified": True})
                if len(recs) > n_before:
                    stats["accepted_commits"] += 1
                else:
                    stats["rej"]["no_func_change"] += 1
        for w in (wf, wp):
            sh(["git", "-C", repo, "worktree", "remove", "--force", w])
    stats["pairs"] = len(recs)
    with open(os.path.join(a.out, f"fixrecs_{a.name}.jsonl"), "w") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    json.dump(stats, open(os.path.join(a.out, f"fixstats_{a.name}.json"), "w"), ensure_ascii=False, indent=1)
    shutil.rmtree(tmp, ignore_errors=True)
    print(json.dumps(stats, ensure_ascii=False))


if __name__ == "__main__":
    main()
