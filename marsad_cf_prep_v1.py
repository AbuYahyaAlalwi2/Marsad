#!/usr/bin/env python3
"""
marsad_cf_prep_v1.py — تحضير مرشّحات Codeforces (قراءة فقط؛ لا يشغّل أي كود من البيانات).

المخرج: cf_candidates.jsonl.gz — سطر لكل مسألة، فيه:
  اختبارات رسمية مختارة (تتضمن الاختبارات التي سقطت عندها التقديمات الخاطئة) + تقديمات Python
  صحيحة (OK) وخاطئة (WRONG_ANSWER/RUNTIME_ERROR) بعينة حتمية مقيّدة لكل مسألة.
المسائل المقبولة: اختباراتها الرسمية كاملة + بلا مدقّق خاص (generated_checker) + إدخال/إخراج قياسي.
لماذا بلا مدقّق: مقارنة الرموز الحرفية صحيحة فقط حين يكون الجواب وحيداً. (مدقّقات Python موجودة لـ403 مسألة وتأجّل.)
"""
import argparse, collections, glob, gzip, hashlib, json, os, sys

CF, SUB = "open-r1/codeforces", "open-r1/codeforces-submissions"
PY = ["Python 3", "PyPy 3", "PyPy 3-64"]
BAD = ("WRONG_ANSWER", "RUNTIME_ERROR")
OK_CAP, BAD_CAP = 30, 80


def hkey(s):
    return hashlib.sha1(str(s).encode("utf-8", "replace")).hexdigest()


def files(repo, prefix, local, lo, hi):
    if local:
        sub = "cf" if repo == CF else "sub"
        out = sorted(glob.glob(os.path.join(local, sub, prefix + "*.parquet")))
        return out
    from huggingface_hub import HfApi
    allf = [f for f in HfApi().list_repo_files(repo, repo_type="dataset") if f.endswith(".parquet")]
    out = sorted(f for f in allf if f.startswith(prefix))
    print(f"[{repo}] بادئة {prefix!r}: {len(out)} ملف", flush=True)
    if not (lo <= len(out) <= hi):
        raise SystemExit(f"فلتر غير متوقع ({len(out)} ملف) عيّنة: {allf[:8]}")
    return out


def batches(repo, path, cols, bs, local, keep):
    import pyarrow.parquet as pq
    if local:
        p, dele = path, False
    else:
        from huggingface_hub import hf_hub_download
        p, dele = hf_hub_download(repo, path, repo_type="dataset", local_dir="dl"), not keep
    try:
        pf = pq.ParquetFile(p)
        have = set(pf.schema_arrow.names)
        for b in pf.iter_batches(columns=[c for c in cols if c in have], batch_size=bs):
            yield b
    finally:
        if dele:
            try:
                os.remove(p)
            except OSError:
                pass


def select_tests(tests, fail_counter, max_tests=48, max_bytes=100_000):
    """أول 6 اختبارات + مواضع السقوط الفعلية للتقديمات الخاطئة + تعبئة بخطوة منتظمة."""
    elig = [i for i, t in enumerate(tests) if len(t.get("input") or "") <= max_bytes and len(t.get("output") or "") <= max_bytes]
    if len(elig) < 3:
        return []
    es = set(elig)
    chosen = set(elig[:6])
    for idx, _ in fail_counter.most_common(24):
        if idx in es:
            chosen.add(idx)
    rest = [i for i in elig if i not in chosen]
    need = max_tests - len(chosen)
    if need > 0 and rest:
        step = max(1, len(rest) // need)
        chosen.update(rest[::step][:need])
    return [{"idx": i, "input": tests[i]["input"], "output": tests[i]["output"]} for i in sorted(chosen)]


class Reservoir:
    """عيّنة حتمية: نحتفظ بأصغر cap مفتاح sha1 (لا عشوائية ولا تحيّز ترتيب الملفات)."""
    def __init__(self, cap):
        self.cap, self.items, self.seen = cap, [], set()

    def add(self, rec):
        h = hkey(rec["src"])
        if h in self.seen:
            return
        self.seen.add(h)
        self.items.append((hkey(rec["sid"]), rec))
        if len(self.items) > self.cap * 3:
            self.items.sort(key=lambda x: x[0])
            self.items = self.items[: self.cap]

    def final(self):
        self.items.sort(key=lambda x: x[0])
        return [r for _, r in self.items[: self.cap]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="cf_candidates.jsonl.gz")
    ap.add_argument("--local-dir", default="")
    ap.add_argument("--limit-problems", type=int, default=0)
    a = ap.parse_args()
    import pyarrow as pa
    import pyarrow.compute as pc
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import marsad_triples as mt

    st = collections.Counter()
    # ---- مرحلة 1: أي المسائل مؤهلة؟ ----
    targets = {}
    for path in files(CF, "verifiable/train-", a.local_dir, 1, 12):
        for b in batches(CF, path, ["id", "official_tests_complete", "generated_checker", "input_mode", "rating",
                                    "time_limit", "title"], 64, a.local_dir, True):
            for r in b.to_pylist():
                st["cf_rows"] += 1
                if not r.get("official_tests_complete"):
                    st["cf_not_complete"] += 1
                elif r.get("generated_checker"):
                    st["cf_has_checker_deferred"] += 1
                elif r.get("input_mode") != "stdio":
                    st["cf_not_stdio"] += 1
                else:
                    targets[r["id"]] = {"title": r.get("title"), "rating": r.get("rating"), "time_limit": r.get("time_limit")}
    st["eligible_problems"] = len(targets)
    print("مسائل مؤهلة:", len(targets), flush=True)

    # ---- مرحلة 2: مسح التقديمات (default) ----
    ok = collections.defaultdict(lambda: Reservoir(OK_CAP))
    bad = collections.defaultdict(lambda: Reservoir(BAD_CAP))
    ids_arr = pa.array(sorted(targets))
    cols = ["problem_id", "programmingLanguage", "verdict", "testset", "passedTestCount", "submission_id", "source"]
    use_arrow = True
    for path in files(SUB, "data/train-", a.local_dir, 20, 60):
        for b in batches(SUB, path, cols, 20000, a.local_dir, False):
            st["sub_rows"] += b.num_rows
            rows = None
            if use_arrow:
                try:
                    m = pc.and_(pc.is_in(b.column("problem_id"), value_set=ids_arr),
                                pc.is_in(b.column("programmingLanguage"), value_set=pa.array(PY)))
                    rows = b.filter(m).to_pylist()
                except Exception as e:  # احتياط: لو اختلف واجهة pyarrow نرجع لمسار بايثون الخالص
                    print("تنبيه: مسار arrow فشل، أستعمل البايثون:", type(e).__name__, flush=True)
                    use_arrow = False
            if rows is None:
                rows = [r for r in b.to_pylist() if r["problem_id"] in targets and r["programmingLanguage"] in PY]
            for r in rows:
                v, src = r["verdict"], r.get("source") or ""
                if v != "OK" and v not in BAD:
                    continue
                if r.get("testset") not in (None, "TESTS"):
                    continue
                if mt.static_reject(src):
                    st["sub_static_reject"] += 1
                    continue
                rec = {"sid": str(r["submission_id"]), "src": src}
                if v == "OK":
                    ok[r["problem_id"]].add(rec)
                else:
                    pc_ = r.get("passedTestCount")
                    rec.update(verdict=v, passed=int(pc_) if pc_ is not None else None)
                    bad[r["problem_id"]].add(rec)
    finalists = {}
    for pid in targets:
        if pid in ok and pid in bad:
            o, bd = ok[pid].final(), bad[pid].final()
            if o and bd:
                finalists[pid] = (o, bd)
    st["problems_with_ok_and_bad"] = len(finalists)
    print("مسائل فيها OK وخاطئ:", len(finalists), flush=True)
    if a.limit_problems:
        finalists = dict(list(finalists.items())[: a.limit_problems])

    # ---- مرحلة 3: الاختبارات الرسمية للمسائل النهائية فقط ----
    n = 0
    with gzip.open(a.out, "wt", encoding="utf-8") as gz:
        for path in files(CF, "verifiable/train-", a.local_dir, 1, 12):
            for b in batches(CF, path, ["id", "description", "official_tests", "time_limit", "rating", "title"],
                             4, a.local_dir, True):
                for r in b.to_pylist():
                    pid = r["id"]
                    if pid not in finalists:
                        continue
                    o, bd = finalists[pid]
                    fc = collections.Counter(x["passed"] for x in bd if x.get("passed") is not None)
                    tests = select_tests(r.get("official_tests") or [], fc)
                    if len(tests) < 3:
                        st["skip_few_tests"] += 1
                        continue
                    gz.write(json.dumps({
                        "id": pid, "title": r.get("title"), "rating": r.get("rating"),
                        "time_limit": r.get("time_limit"), "description": (r.get("description") or "")[:4000],
                        "tests": tests, "ok": o, "bad": bd}, ensure_ascii=False) + "\n")
                    n += 1
                    st["written_problems"] += 1
    st["cand_file_bytes"] = os.path.getsize(a.out)
    print(json.dumps(dict(st), ensure_ascii=False, indent=2))
    with open("prep_stats.json", "w", encoding="utf-8") as f:
        json.dump(dict(st), f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
