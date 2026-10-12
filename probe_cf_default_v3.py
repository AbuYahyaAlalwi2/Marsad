#!/usr/bin/env python3
"""
probe_cf_default_v3.py — قراءة فقط. هل يكفي إعداد default (12.6M تقديم) لتكوين أزواج Python
على مسائل Codeforces كاملة الاختبارات؟ يعدّ فقط، ولا يحمّل كود المصدر ولا ينفّذ شيئاً.
"""
import collections, json, os
import pyarrow.parquet as pq
from huggingface_hub import HfApi, hf_hub_download

CF, SUB = "open-r1/codeforces", "open-r1/codeforces-submissions"
PY = {"Python 3", "PyPy 3", "PyPy 3-64"}
api = HfApi()


def parquet_files(repo, prefix, lo, hi):
    fs = [f for f in api.list_repo_files(repo, repo_type="dataset") if f.endswith(".parquet")]
    tops = collections.Counter(f.split("/")[0] for f in fs)
    out = sorted(f for f in fs if f.startswith(prefix))
    print(f"[{repo}] parquet={len(fs)} حسب المجلد={dict(tops)} | بادئة {prefix!r}: {len(out)}", flush=True)
    if not (lo <= len(out) <= hi):
        print("  عيّنة مسارات:", fs[:10])
        raise SystemExit("فلتر غير متوقع: أوقف قبل تحميل أي شيء")
    return out


def read(repo, path, cols):
    p = hf_hub_download(repo, path, repo_type="dataset", local_dir="dl")
    try:
        pf = pq.ParquetFile(p)
        cols = [c for c in cols if c in set(pf.schema_arrow.names)]
        for b in pf.iter_batches(columns=cols, batch_size=20000):
            yield from b.to_pylist()
    finally:
        try:
            os.remove(p)
        except OSError:
            pass


rep = {}
cf, chk_with, chk_without, testlib = {}, None, None, 0
for path in parquet_files(CF, "verifiable/train-", 1, 12):
    for r in read(CF, path, ["id", "official_tests_complete", "generated_checker", "rating"]):
        gc = r.get("generated_checker") or ""
        cf[r["id"]] = {"complete": bool(r.get("official_tests_complete")), "checker": bool(gc), "rating": r.get("rating")}
        if gc:
            if "testlib" in gc:
                testlib += 1
            if chk_with is None:
                chk_with = gc[:900]
complete = {k for k, v in cf.items() if v["complete"]}
rep["cf_complete"] = len(complete)
rep["cf_complete_with_checker"] = sum(cf[k]["checker"] for k in complete)
rep["cf_checker_mentions_testlib_all"] = testlib
rep["checker_head"] = chk_with

ok, bad = collections.defaultdict(int), collections.defaultdict(lambda: collections.Counter())
langs, verd, n = collections.Counter(), collections.Counter(), 0
for path in parquet_files(SUB, "data/train-", 20, 60):
    for r in read(SUB, path, ["problem_id", "programmingLanguage", "verdict"]):
        n += 1
        pid = r["problem_id"]
        if pid not in complete or r["programmingLanguage"] not in PY:
            continue
        v = r["verdict"]
        langs[r["programmingLanguage"]] += 1
        verd[v] += 1
        if v == "OK":
            ok[pid] += 1
        elif v in ("WRONG_ANSWER", "RUNTIME_ERROR"):
            bad[pid][v] += 1
rep["submissions_rows_scanned"] = n
rep["python_langs_on_complete_problems"] = dict(langs)
rep["verdicts_python_on_complete"] = dict(verd)
both = [p for p in complete if ok.get(p) and bad.get(p)]
rep["complete_problems_with_python_ok"] = sum(1 for p in complete if ok.get(p))
rep["complete_problems_with_python_wa_or_re"] = sum(1 for p in complete if bad.get(p))
rep["complete_problems_with_both"] = len(both)
rep["python_ok_total_on_both"] = sum(ok[p] for p in both)
rep["python_wa_re_total_on_both"] = sum(sum(bad[p].values()) for p in both)
rep["pairs_if_cap3_per_problem_upper"] = sum(min(3, ok[p] * sum(bad[p].values())) for p in both)
rep["both_examples"] = both[:5]
print(json.dumps(rep, ensure_ascii=False, indent=2))
open("probe_report_v3.json", "w", encoding="utf-8").write(json.dumps(rep, ensure_ascii=False, indent=2))
