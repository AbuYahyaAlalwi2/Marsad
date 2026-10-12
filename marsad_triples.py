#!/usr/bin/env python3
"""
marsad_triples.py — مصنع الثلاثيات المتحقَّق منها لـ MARSAD
المصدر: deepmind/code_contests (حلول صحيحة + حلول خاطئة + اختبارات)

القبول يتطلب (Differential Gate):
  1) الحل الصحيح C ينجح في كل الاختبارات المختارة
  2) الحل الخاطئ B يفشل بإجابة خاطئة (WA) في اختبار واحد على الأقل
  3) B و C متشابهان بنيوياً (token similarity >= --min-sim) فيكون الإصلاح تعديلاً صغيراً

العزل (مستوى 2، ليس بديلاً عن Docker): subprocess منفصل + rlimits + بيئة فارغة + مهلة
+ قتل مجموعة العمليات + كنس /proc لأي عملية يتيمة بدليلها المؤقت + فلتر ساكن
+ عزل شبكة عبر `unshare -rn` إن توفّر.
"""
import argparse, collections, concurrent.futures as cf, difflib, gzip, hashlib, json, math
import os, re, resource, signal, subprocess, sys, tempfile, time, tokenize, io

REPO = "deepmind/code_contests"
LANG_PY3 = 3  # AlphaCode: 0 unknown, 1 PYTHON(2), 2 CPP, 3 PYTHON3, 4 JAVA

FORBID_IMPORT = re.compile(
    r"^\s*(?:import|from)\s+(socket|subprocess|ctypes|multiprocessing|shutil|requests|urllib|http|"
    r"ftplib|smtplib|telnetlib|pty|webbrowser|pickle|marshal|glob|pathlib|tempfile|importlib)\b", re.M)
FORBID_CALL = re.compile(
    r"\bos\s*\.\s*(system|popen|exec\w*|spawn\w*|remove|unlink|rmdir|removedirs|rename|fork|kill|killpg|"
    r"chmod|chown|listdir|walk|scandir|environ|getenv)\b|__import__|\bgetattr\s*\(|\bcompile\s*\(|"
    r"\bexec\s*\(|\beval\s*\(|\bopen\s*\(\s*(?!0\s*[,)]|['\"]/dev/stdin)", re.M)


def static_reject(code):
    if len(code) > 20000:
        return "too_long"
    if FORBID_IMPORT.search(code):
        return "forbidden_import"
    if FORBID_CALL.search(code):
        return "forbidden_call"
    return None


def _net_isolation_available():
    try:
        return subprocess.run(["unshare", "-rn", "true"], capture_output=True, timeout=5).returncode == 0
    except Exception:
        return False


NET_PREFIX = ["unshare", "-rn"] if _net_isolation_available() else []


def reap(tmp):
    """اقتل أي عملية (حتى لو هربت من مجموعة العمليات) يكون دليل عملها داخل tmp."""
    me = os.getpid()
    for pid in os.listdir("/proc"):
        if not pid.isdigit() or int(pid) == me:
            continue
        try:
            if os.readlink(f"/proc/{pid}/cwd").startswith(tmp):
                os.kill(int(pid), signal.SIGKILL)
        except Exception:
            pass


def _limits(mem_mb, cpu_s):
    def f():
        resource.setrlimit(resource.RLIMIT_AS, (mem_mb << 20, mem_mb << 20))
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_s, cpu_s))
        resource.setrlimit(resource.RLIMIT_FSIZE, (1 << 20, 1 << 20))
        resource.setrlimit(resource.RLIMIT_NPROC, (32, 32))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    return f


def run_py(code_path, in_path, out_path, timeout=3.0, mem_mb=512):
    """returns (status, seconds); status in OK|RE|TLE"""
    t0 = time.perf_counter()
    cwd = os.path.dirname(code_path)
    status = None
    with open(in_path, "rb") as fin, open(out_path, "wb") as fout, open(out_path + ".err", "wb") as ferr:
        p = subprocess.Popen(
            NET_PREFIX + [sys.executable, "-I", code_path],
            stdin=fin, stdout=fout, stderr=ferr, cwd=cwd,
            env={"PATH": "/usr/bin:/bin", "PYTHONHASHSEED": "0", "PYTHONIOENCODING": "utf-8"},
            preexec_fn=_limits(mem_mb, int(timeout) + 1), start_new_session=True)
        try:
            p.wait(timeout=timeout)
            status = "OK" if p.returncode == 0 else "RE"
        except subprocess.TimeoutExpired:
            status = "TLE"
        finally:
            try:
                os.killpg(p.pid, signal.SIGKILL)
            except Exception:
                pass
            reap(cwd)
            try:
                p.wait(timeout=5)
            except Exception:
                pass
    return status, time.perf_counter() - t0


def pick_tests(row, max_tests=15, max_bytes=100_000):
    def pairs(key):
        t = row.get(key) or {}
        return [(i, o) for i, o in zip(t.get("input") or [], t.get("output") or [])
                if len(i) <= max_bytes and len(o) <= max_bytes]
    base = (pairs("public_tests") + pairs("private_tests"))[:6]
    gen = pairs("generated_tests")
    need = max_tests - len(base)
    if gen and need > 0:
        gen = gen[::max(1, len(gen) // need)][:need]
    else:
        gen = []
    return base + gen


class Problem:
    def __init__(self, tmp, tests):
        self.tmp, self.execs, self.n = tmp, 0, 0
        self.ins, self.exp = [], []
        for k, (i, o) in enumerate(tests):
            p = os.path.join(tmp, f"in_{k}.txt")
            with open(p, "w", encoding="utf-8", newline="") as f:
                f.write(i)
            self.ins.append(p)
            self.exp.append(o.split())

    def evaluate(self, code, timeout=3.0):
        self.n += 1
        cp = os.path.join(self.tmp, f"sol_{self.n}.py")
        with open(cp, "w", encoding="utf-8") as f:
            f.write(code)
        op = os.path.join(self.tmp, f"out_{self.n}.txt")
        for k, ip in enumerate(self.ins):
            st, _ = run_py(cp, ip, op, timeout)
            self.execs += 1
            if st != "OK":
                err = ""
                if st == "RE":  # آخر سطر من الخطأ (مثل IndexError: ...) يُحفظ كسبب الفشل
                    try:
                        with open(op + ".err", "rb") as f:
                            lines = [l for l in f.read(4000).decode("utf-8", "replace").splitlines() if l.strip()]
                        err = lines[-1][:200] if lines else ""
                    except Exception:
                        pass
                return False, {"k": k, "type": st, "actual": err}
            with open(op, "r", encoding="utf-8", errors="replace") as f:
                actual = f.read(1_000_001)
            if actual.split() != self.exp[k]:
                return False, {"k": k, "type": "WA", "actual": actual[:500]}
        return True, None


def toks(code):
    try:
        skip = (tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT, tokenize.ENDMARKER)
        return [t.string for t in tokenize.generate_tokens(io.StringIO(code).readline) if t.type not in skip]
    except Exception:
        return None


def similarity(a, b):
    if not a or not b:
        return 0.0
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    if sm.real_quick_ratio() < 0.4 or sm.quick_ratio() < 0.4:
        return 0.0
    return sm.ratio()


def py3_solutions(block, cap):
    block = block or {}
    out = [s for l, s in zip(block.get("language") or [], block.get("solution") or [])
           if l == LANG_PY3 and isinstance(s, str)]
    seen, uniq = set(), []
    for s in out:
        h = hashlib.sha1(s.encode()).hexdigest()
        if h not in seen:
            seen.add(h)
            uniq.append(s)
    return uniq[:cap]


def is_eval(name):
    return int(hashlib.sha1(name.encode()).hexdigest(), 16) % 100 < 15  # الحجز حسب المسألة لا حسب العيّنة


def process_problem(row, opts):
    st, recs = collections.Counter(), []
    name = row.get("name") or "unknown"
    tests = pick_tests(row, opts["max_tests"])
    if len(tests) < 3:
        st["skip_few_tests"] += 1
        return recs, st, 0
    good_src = py3_solutions(row.get("solutions"), opts["max_correct"])
    bad_src = py3_solutions(row.get("incorrect_solutions"), opts["max_incorrect"])
    if not good_src or not bad_src:
        st["skip_no_py3_pair_candidates"] += 1
        return recs, st, 0
    with tempfile.TemporaryDirectory(prefix="mt_") as tmp:
        P = Problem(tmp, tests)
        good, correct_wa = [], 0
        for c in good_src:
            if static_reject(c):
                st["correct_static_reject"] += 1
                continue
            ok, cf = P.evaluate(c)
            if ok:
                good.append((c, toks(c)))
            else:
                st["correct_fails_tests"] += 1
                if cf["type"] == "WA":
                    correct_wa += 1
        if correct_wa:  # حل صحيح رسمياً يعطي جواباً مختلفاً => المسألة تقبل أكثر من جواب، فحكم WA غير موثوق
            st["skip_problem_possible_multi_answer"] += 1
            return recs, st, P.execs
        if not good:
            st["skip_no_verified_correct"] += 1
            return recs, st, P.execs
        cands = []
        for b in bad_src:
            r = static_reject(b)
            if r:
                st["bad_" + r] += 1
                continue
            tb = toks(b)
            if not tb:
                st["bad_untokenizable"] += 1
                continue
            ok, fail = P.evaluate(b)
            if ok:
                st["bad_passes_selected_tests"] += 1
                continue
            if fail["type"] != "WA":
                if fail["type"] == "TLE" and not opts["allow_tle"]:
                    st["bad_tle_skipped"] += 1  # يعتمد على سرعة الجهاز
                    continue
                if fail["type"] == "RE" and fail["actual"].startswith("MemoryError"):
                    st["bad_re_memory_skipped"] += 1  # يعتمد على حد الذاكرة عندنا
                    continue
                ok2, _ = P.evaluate(b)
                if ok2:
                    st["bad_flaky"] += 1
                    continue
            best, bs = None, 0.0
            for c, tc in good:
                s = similarity(tb, tc)
                if s > bs:
                    best, bs = c, s
            if best is None or bs < opts["min_sim"]:
                st["bad_no_close_fix"] += 1
                continue
            cands.append((bs, b, best, fail))
        cands.sort(key=lambda x: -x[0])
        seen_pairs = set()
        for bs, b, c, fail in cands:
            norm = " ".join(toks(b) or []) + "\0" + " ".join(toks(c) or [])
            h = hashlib.sha256(norm.encode()).hexdigest()
            if h in seen_pairs:
                st["dup_pair"] += 1
                continue
            seen_pairs.add(h)
            if len(recs) >= opts["max_pairs"]:
                st["capped_per_problem"] += 1
                continue
            k = fail["k"]
            diff = "".join(difflib.unified_diff(b.splitlines(True), c.splitlines(True), "buggy.py", "fixed.py", n=2))
            recs.append({
                "id": h[:16], "problem": name, "source": "deepmind/code_contests", "license": "cc-by-4.0",
                "split": "eval" if is_eval(name) else "train", "lang": "python3",
                "difficulty": row.get("difficulty"), "description": (row.get("description") or "")[:4000],
                "buggy_code": b, "fixed_code": c, "diff": diff, "token_similarity": round(bs, 3),
                "failing_test": {"input": tests[k][0][:2000], "expected": tests[k][1][:500],
                                 "actual": fail["actual"], "failure_type": fail["type"]},
                "tests_used": len(tests),
                "verified": {"fixed_passes_all": True, "buggy_fails": True},
            })
            st["accepted_pair"] += 1
        return recs, st, P.execs


def iter_rows(args):
    if args.fixture:
        from fixture_rows import ROWS
        yield from ROWS
        return
    from huggingface_hub import HfApi, hf_hub_download
    import pyarrow.parquet as pq
    tok = os.environ.get(f"HF_TOKEN_{(args.shard % 5) + 1}") or os.environ.get("HF_TOKEN")
    api = HfApi(token=tok)
    allf = api.list_repo_files(REPO, repo_type="dataset")
    files = sorted(f for f in allf if f.endswith(".parquet") and os.path.basename(f).startswith(f"{args.split}-"))
    if not files:
        print("❌ لا parquet للـ split. الملفات:", allf[:30], file=sys.stderr)
        sys.exit(2)
    mods = math.ceil(args.num_shards / len(files))
    units = [(f, m) for f in files for m in range(mods)]
    cols = ["name", "description", "public_tests", "private_tests", "generated_tests",
            "solutions", "incorrect_solutions", "difficulty"]
    for f, m in units[args.shard::args.num_shards]:
        pf = pq.ParquetFile(hf_hub_download(REPO, f, repo_type="dataset", token=tok))
        idx = 0
        for batch in pf.iter_batches(batch_size=4, columns=cols):
            for row in batch.to_pylist():
                if idx % mods == m:
                    yield row
                idx += 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="train")
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--num-shards", type=int, default=1)
    ap.add_argument("--procs", type=int, default=os.cpu_count() or 2)
    ap.add_argument("--limit-problems", type=int, default=0)
    ap.add_argument("--max-tests", type=int, default=30)
    ap.add_argument("--max-correct", type=int, default=12)
    ap.add_argument("--max-incorrect", type=int, default=40)
    ap.add_argument("--max-pairs", type=int, default=3)
    ap.add_argument("--min-sim", type=float, default=0.55)
    ap.add_argument("--out", default="out")
    ap.add_argument("--fixture", action="store_true")
    ap.add_argument("--allow-tle", action="store_true")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    opts = dict(max_tests=args.max_tests, max_correct=args.max_correct, max_incorrect=args.max_incorrect,
                max_pairs=args.max_pairs, min_sim=args.min_sim, allow_tle=args.allow_tle)
    print(f"عزل الشبكة عبر unshare: {'نعم' if NET_PREFIX else 'لا (مستوى أضعف)'} | عمليات: {args.procs}")
    out_path = os.path.join(args.out, f"triples_{args.split}_shard{args.shard:03d}of{args.num_shards:03d}.jsonl.gz")
    stats, execs, problems, t0 = collections.Counter(), 0, 0, time.perf_counter()
    inflight = set()

    def drain():
        nonlocal execs
        done, _ = cf.wait(inflight, return_when=cf.FIRST_COMPLETED)
        for fu in done:
            inflight.discard(fu)
            recs, st, ex = fu.result()
            stats.update(st)
            execs += ex
            for r in recs:
                gz.write((json.dumps(r, ensure_ascii=False) + "\n").encode())

    with gzip.open(out_path, "wb") as gz, cf.ProcessPoolExecutor(args.procs) as pool:
        for row in iter_rows(args):
            problems += 1
            inflight.add(pool.submit(process_problem, row, opts))
            while len(inflight) >= args.procs * 2:
                drain()
            if args.limit_problems and problems >= args.limit_problems:
                break
        while inflight:
            drain()
    wall = time.perf_counter() - t0
    report = {"problems_seen": problems, "wall_seconds": round(wall, 1), "executions": execs,
              "execs_per_second": round(execs / wall, 1) if wall else None,
              "accepted_pairs": stats["accepted_pair"],
              "output_file_bytes": os.path.getsize(out_path), "reasons": dict(stats)}
    with open(os.path.join(args.out, f"stats_{args.split}_shard{args.shard:03d}.json"), "w") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
