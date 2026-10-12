#!/usr/bin/env python3
"""
probe_cf_join_v2.py — فحص قراءة فقط (لا تنفيذ أي كود) لمصدري Codeforces على HF.
يجيب بالقياس: صيغة المفاتيح، نسبة التطابق، اكتمال الاختبارات، صيغة المدقّق، وعدد المسائل الصالحة للأزواج.
"""
import collections, json, os, sys
import pyarrow.parquet as pq
from huggingface_hub import HfApi, hf_hub_download

CF, SUB = "open-r1/codeforces", "open-r1/codeforces-submissions"
PY = {"Python 3", "PyPy 3", "PyPy 3-64"}
api = HfApi()


def parquet_files(repo, prefix):
    fs = [f for f in api.list_repo_files(repo, repo_type="dataset") if f.endswith(".parquet")]
    tops = collections.Counter(f.split("/")[0] for f in fs)
    out = sorted(f for f in fs if f.startswith(prefix))
    print(f"[{repo}] parquet={len(fs)} حسب المجلد={dict(tops)} | بادئة {prefix!r}: {len(out)}", flush=True)
    assert 0 < len(out) <= 12, "فلتر غير متوقع: أوقف قبل تحميل أي شيء"
    return out


def read(repo, path, cols):
    p = hf_hub_download(repo, path, repo_type="dataset", local_dir="dl")
    try:
        pf = pq.ParquetFile(p)
        have = set(pf.schema_arrow.names)
        cols = [c for c in cols if c in have]
        for b in pf.iter_batches(columns=cols, batch_size=2000):
            yield from b.to_pylist()
    finally:
        try:
            os.remove(p)  # وفّر القرص: احذف الملف بعد قراءته
        except OSError:
            pass


rep = {}
# ---- codeforces (verifiable/train) ----
cf = {}
checker_sample = None
mode = collections.Counter()
for path in parquet_files(CF, "verifiable/train-"):
    for r in read(CF, path, ["id", "contest_id", "index", "official_tests_complete",
                             "executable", "input_mode", "generated_checker", "testset_size", "rating"]):
        gc = r.get("generated_checker")
        cf[r["id"]] = {"complete": bool(r.get("official_tests_complete")), "exe": bool(r.get("executable")),
                       "checker": bool(gc), "mode": r.get("input_mode"), "rating": r.get("rating")}
        mode[r.get("input_mode")] += 1
        if gc and checker_sample is None:
            checker_sample = gc[:700]
rep["cf_rows"] = len(cf)
rep["cf_id_examples"] = list(cf)[:5]
rep["cf_complete"] = sum(v["complete"] for v in cf.values())
rep["cf_executable"] = sum(v["exe"] for v in cf.values())
rep["cf_with_checker"] = sum(v["checker"] for v in cf.values())
rep["cf_complete_and_exe"] = sum(v["complete"] and v["exe"] for v in cf.values())
rep["cf_input_mode"] = dict(mode)

# ---- submissions ----
subs = {}
for cfg in ("selected_accepted", "selected_incorrect"):
    ps = parquet_files(SUB, cfg + "/train-")
    langs, verd, pids, n = collections.Counter(), collections.Counter(), collections.defaultdict(set), 0
    for path in ps:
        for r in read(SUB, path, ["problem_id", "programmingLanguage", "verdict", "submission_id"]):
            n += 1
            langs[r["programmingLanguage"]] += 1
            verd[r["verdict"]] += 1
            if r["programmingLanguage"] in PY:
                pids[r["problem_id"]].add(r["submission_id"])
    subs[cfg] = pids
    rep[cfg] = {"rows": n, "top_languages": dict(langs.most_common(8)), "verdicts": dict(verd.most_common(6)),
                "unique_problems_python": len(pids), "python_subs": sum(len(v) for v in pids.values())}

acc, inc = subs["selected_accepted"], subs["selected_incorrect"]
both = set(acc) & set(inc)
valid = {p for p in both if p in cf and cf[p]["complete"] and cf[p]["exe"]}
rep["join"] = {
    "python_problems_with_accepted_and_incorrect": len(both),
    "of_which_id_found_in_cf": sum(p in cf for p in both),
    "of_which_complete_tests_and_executable": len(valid),
    "of_which_need_checker": sum(cf[p]["checker"] for p in valid),
    "python_pairs_upper_bound": sum(len(acc[p]) * len(inc[p]) for p in valid),
    "problem_id_examples": list(both)[:5],
}
rep["checker_sample_head"] = checker_sample
print(json.dumps(rep, ensure_ascii=False, indent=2))
open("probe_report.json", "w", encoding="utf-8").write(json.dumps(rep, ensure_ascii=False, indent=2))
