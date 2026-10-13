#!/usr/bin/env python3
"""
marsad_cf_mine_v1.py — يتحقق بالتنفيذ من أزواج Codeforces (Python) بنفس بوابة الفرق التفاضلي والـ sandbox
المستعملين في marsad_triples.py (يستورد منه الدوال لا ينسخها).

لكل مسألة: الحل OK يجب أن ينجح في كل الاختبارات الرسمية المختارة (مقارنة رموز حرفية)،
والخاطئ يجب أن يفشل (WA، أو RE مؤكّد بإعادة التشغيل). TLE وMemoryError مستبعدان.
لو فشل حلٌّ حكمه OK عند Codeforces بإجابة مختلفة عندنا => تُتخطّى المسألة كلها (جواب متعدد/دقة عشرية).
"""
import argparse, collections, concurrent.futures as cf, difflib, gzip, hashlib, json, os, sys, tempfile, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import marsad_triples as mt


def is_eval(key):
    return int(hashlib.sha1(key.encode()).hexdigest(), 16) % 100 < 15


def timeout_for(tl):
    try:
        return min(10.0, max(2.0, float(tl) * 1.5 + 1.0))
    except Exception:
        return 4.0


def process_problem(row, opts):
    st, recs = collections.Counter(), []
    pid = row["id"]
    tests = [(t["input"], t["output"]) for t in row["tests"]]
    to = timeout_for(row.get("time_limit"))
    with tempfile.TemporaryDirectory(prefix="mcf_") as tmp:
        P = mt.Problem(tmp, tests)
        good, correct_wa = [], 0
        for s in row["ok"][: opts["max_correct"]]:
            c = s["src"]
            if mt.static_reject(c):
                st["correct_static_reject"] += 1
                continue
            ok, f = P.evaluate(c, to)
            if ok:
                good.append((c, mt.toks(c), s["sid"]))
            else:
                st["correct_fails_tests"] += 1
                if f["type"] == "WA":
                    correct_wa += 1
        if correct_wa:
            st["skip_problem_possible_multi_answer"] += 1
            return recs, st, P.execs
        if not good:
            st["skip_no_verified_correct"] += 1
            return recs, st, P.execs
        cands = []
        for s in row["bad"][: opts["max_incorrect"]]:
            b = s["src"]
            tb = mt.toks(b)
            if not tb:
                st["bad_untokenizable"] += 1
                continue
            ok, fail = P.evaluate(b, to)
            if ok:
                st["bad_passes_selected_tests"] += 1
                continue
            if fail["type"] != "WA":
                if fail["type"] == "TLE":
                    st["bad_tle_skipped"] += 1
                    continue
                if fail["type"] == "RE" and fail["actual"].startswith("MemoryError"):
                    st["bad_re_memory_skipped"] += 1
                    continue
                ok2, _ = P.evaluate(b, to)
                if ok2:
                    st["bad_flaky"] += 1
                    continue
            best, bs, bsid = None, 0.0, None
            for c, tc, sid in good:
                sc = mt.similarity(tb, tc)
                if sc > bs:
                    best, bs, bsid = c, sc, sid
            if best is None or bs < opts["min_sim"]:
                st["bad_no_close_fix"] += 1
                continue
            cands.append((bs, b, best, fail, s, bsid))
        cands.sort(key=lambda x: -x[0])
        seen = set()
        for bs, b, c, fail, s, bsid in cands:
            norm = " ".join(mt.toks(b) or []) + "\0" + " ".join(mt.toks(c) or [])
            h = hashlib.sha256(norm.encode()).hexdigest()
            if h in seen:
                st["dup_pair"] += 1
                continue
            seen.add(h)
            if len(recs) >= opts["max_pairs"]:
                st["capped_per_problem"] += 1
                continue
            k = fail["k"]
            diff = "".join(difflib.unified_diff(
                [l if l.endswith("\n") else l + "\n" for l in b.splitlines(True)],
                [l if l.endswith("\n") else l + "\n" for l in c.splitlines(True)], "buggy.py", "fixed.py", n=2))
            recs.append({
                "id": "cf" + h[:14], "problem": pid, "source": "open-r1/codeforces+codeforces-submissions",
                "license": "cc-by-4.0", "split": "eval" if is_eval(pid) else "train", "lang": "python3",
                "difficulty": row.get("rating"), "title": row.get("title"), "description": row.get("description") or "",
                "buggy_code": b, "fixed_code": c, "diff": diff, "token_similarity": round(bs, 3),
                "failing_test": {"input": tests[k][0][:2000], "expected": tests[k][1][:500],
                                 "actual": fail["actual"], "failure_type": fail["type"]},
                "tests_used": len(tests), "buggy_submission_id": s["sid"], "fixed_submission_id": bsid,
                "buggy_cf_verdict": s.get("verdict"),
                "verified": {"fixed_passes_all": True, "buggy_fails": True},
            })
            st["accepted_pair"] += 1
        return recs, st, P.execs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cand", default="cf_candidates.jsonl.gz")
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--num-shards", type=int, default=1)
    ap.add_argument("--procs", type=int, default=os.cpu_count() or 2)
    ap.add_argument("--limit-problems", type=int, default=0)
    ap.add_argument("--max-correct", type=int, default=12)
    ap.add_argument("--max-incorrect", type=int, default=40)
    ap.add_argument("--max-pairs", type=int, default=4)
    ap.add_argument("--min-sim", type=float, default=0.55)
    ap.add_argument("--out", default="out")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    opts = dict(max_correct=a.max_correct, max_incorrect=a.max_incorrect, max_pairs=a.max_pairs, min_sim=a.min_sim)
    print(f"عزل الشبكة: {'نعم' if mt.NET_PREFIX else 'لا (مستوى أضعف)'} | عمليات: {a.procs}")
    out_path = os.path.join(a.out, f"cftriples_shard{a.shard:03d}of{a.num_shards:03d}.jsonl.gz")
    stats, execs, problems, t0, inflight = collections.Counter(), 0, 0, time.perf_counter(), set()

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

    with gzip.open(out_path, "wb") as gz, cf.ProcessPoolExecutor(a.procs) as pool, gzip.open(a.cand, "rt", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            if int(hashlib.sha1(row["id"].encode()).hexdigest(), 16) % a.num_shards != a.shard:
                continue
            problems += 1
            inflight.add(pool.submit(process_problem, row, opts))
            while len(inflight) >= a.procs * 2:
                drain()
            if a.limit_problems and problems >= a.limit_problems:
                break
        while inflight:
            drain()
    wall = time.perf_counter() - t0
    rep = {"problems_seen": problems, "wall_seconds": round(wall, 1), "executions": execs,
           "accepted_pairs": stats["accepted_pair"], "output_file_bytes": os.path.getsize(out_path),
           "reasons": dict(stats)}
    with open(os.path.join(a.out, f"stats_cf_shard{a.shard:03d}.json"), "w") as g:
        json.dump(rep, g, ensure_ascii=False, indent=2)
    print(json.dumps(rep, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
