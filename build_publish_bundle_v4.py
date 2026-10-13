#!/usr/bin/env python3
"""
build_publish_bundle_v4.py — يجمّع مخرجات شرائح المصنع في حزمة نشر نظيفة (بلا تنفيذ أي كود من البيانات).

يفعل: قراءة كل triples_*.jsonl.gz -> رفض الأسطر المعطوبة أو الناقصة -> إسقاط أي سطر فيه نمط سر
-> إزالة التكرار بحسب id -> إزالة سجلات train التي يطابق كودها (الخاطئ أو الصحيح) كود سجل في eval
-> كتابة train.jsonl.gz و eval.jsonl.gz و stats.json و TRIPLES_CARD.md.
"""
import argparse, collections, difflib, glob, gzip, hashlib, json, os, re

PAT = re.compile(r"(hf_[A-Za-z0-9]{30,}|ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|"
                 r"sk-or-[A-Za-z0-9-]{20,}|sk-[A-Za-z0-9]{32,}|gsk_[A-Za-z0-9]{30,}|AKIA[0-9A-Z]{16}|"
                 r"[0-9]{8,10}:AA[A-Za-z0-9_-]{30,})")
REQ = ("id", "problem", "buggy_code", "fixed_code", "split", "failing_test", "license", "source")


CC_KEY = re.compile(r"^(\d+)_([A-Za-z]\d?)\b")


def prob_key(r):
    """مفتاح المسألة المشترك بين المصدرين: contest/index (مثل 852/A)."""
    p = str(r.get("problem") or "")
    if "/" in p and p.split("/")[0].isdigit():
        return p
    m = CC_KEY.match(p)
    return f"{m.group(1)}/{m.group(2).upper()}" if m else p


def split_for(key):
    """تقسيم واحد لكل مسألة عبر كل المصادر: لا تسرّب ولا حذف سجلات."""
    return "eval" if int(hashlib.sha1(key.encode()).hexdigest(), 16) % 100 < 15 else "train"


def h(s):
    return hashlib.sha1(s.encode("utf-8", "replace")).hexdigest()


def norm_diff(buggy, fixed):
    """فرق موحّد مع تطبيع نهاية السطر الأخير (كي لا تلتصق سطور الفرق ببعضها)."""
    fix = lambda t: [l if l.endswith("\n") else l + "\n" for l in t.splitlines(True)]
    return "".join(difflib.unified_diff(fix(buggy), fix(fixed), "buggy.py", "fixed.py", n=2))


def n_changed(diff):
    return sum(1 for l in diff.splitlines() if l[:1] in "+-" and not l.startswith(("+++", "---")))


def tier(n):
    return "small_patch" if n <= 10 else "medium_patch" if n <= 40 else "rewrite"


def write_gz(path, rows):
    with gzip.open(path, "wt", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def card(st, n_train, n_eval):
    ft = st.get("failure_types", {})
    return f"""---
license: cc-by-4.0
pretty_name: Marsad verified bug-fix triples (Python 3)
source_datasets:
  - deepmind/code_contests
  - open-r1/codeforces
  - open-r1/codeforces-submissions
---
# Marsad verified bug-fix triples

Each record pairs a **buggy** Python 3 solution with a **correct** solution to the same problem, plus the
**failing test** that separates them. A pair is accepted only if the correct solution passes every selected
test and the buggy one fails at least one (wrong answer or a deterministic runtime error).

- train: {n_train} | eval: {n_eval} | sources: {json.dumps(st.get('sources', {}), ensure_ascii=False)} | problems: {st.get('problems')}
  (one shared split per problem key across sources: sha1(contest/index) % 100 < 15 -> eval; train records whose code also appears in eval were removed)
- failure types: {json.dumps(ft, ensure_ascii=False)}
- patch tiers (changed lines in diff): {json.dumps(st.get("patch_tiers", {}), ensure_ascii=False)};
  `small_patch` <= 10, `medium_patch` <= 40, `rewrite` > 40. Filter on `patch_tier` for minimal fixes.

## Method
Execution in a resource-limited subprocess sandbox (no network, rlimits, empty environment). Problems where an
officially correct solution disagrees with the expected output are skipped as possibly multi-answer.

## Limitations (read before use)
- These are **logic bugs from programming contests, not security vulnerabilities**.
- The "fixed" code is another author's accepted solution; it is token-similar (>= 0.55) but **not a minimal patch**.
- Python 3 only. Output comparison is token-exact. Sandbox is process-level isolation, not a container.

## Attribution
Derived from deepmind/code_contests, open-r1/codeforces and open-r1/codeforces-submissions (all CC BY 4.0). Modified: filtered, paired, executed and verified.
The split is recomputed from the problem key so the same problem is on the same side in every source; identical code pairs are de-duplicated across sources.
Codeforces records carry `tests_complete` (false = official tests were partial; the fixed code is still an accepted submission and the buggy code fails a known official test).
Source pin: see sources_manifest.json in the project repository.
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    files = sorted(glob.glob(os.path.join(a.in_dir, "**", "*triples_*.jsonl.gz"), recursive=True))
    st, seen, buckets, ftypes = collections.Counter(), set(), {"train": [], "eval": []}, collections.Counter()
    seen_pairs, src_count = set(), collections.Counter()
    for fp in files:
        with gzip.open(fp, "rt", encoding="utf-8") as f:
            for line in f:
                st["read"] += 1
                try:
                    r = json.loads(line)
                except Exception:
                    st["bad_json"] += 1
                    continue
                if not all(k in r for k in REQ):
                    st["missing_fields"] += 1
                    continue
                if r["split"] not in buckets:
                    st["bad_split"] += 1
                    continue
                if PAT.search(line):
                    st["dropped_secret_pattern"] += 1
                    continue
                if r["id"] in seen:
                    st["dup_id"] += 1
                    continue
                seen.add(r["id"])
                code_pair = h(r["buggy_code"]) + h(r["fixed_code"])
                if code_pair in seen_pairs:
                    st["dup_code_pair_cross_source"] += 1
                    continue
                seen_pairs.add(code_pair)
                r["problem_key"] = prob_key(r)
                new_split = split_for(r["problem_key"])
                if new_split != r["split"]:
                    st["resplit_changed"] += 1
                r["split"] = new_split
                src_count[r["source"]] += 1
                buckets[r["split"]].append(r)
    ev = buckets["eval"]
    ev_codes = {h(r["buggy_code"]) for r in ev} | {h(r["fixed_code"]) for r in ev}
    kept = []
    for r in buckets["train"]:
        if h(r["buggy_code"]) in ev_codes or h(r["fixed_code"]) in ev_codes:
            st["train_removed_overlap_with_eval"] += 1
        else:
            kept.append(r)
    buckets["train"] = kept
    tiers = collections.Counter()
    for sp in buckets:
        buckets[sp].sort(key=lambda r: r["id"])
        for r in buckets[sp]:
            ftypes[(r.get("failing_test") or {}).get("failure_type", "?")] += 1
            r["diff"] = norm_diff(r["buggy_code"], r["fixed_code"])
            r["changed_lines"] = n_changed(r["diff"])
            r["patch_tier"] = tier(r["changed_lines"])
            tiers[r["patch_tier"]] += 1
    write_gz(os.path.join(a.out_dir, "train.jsonl.gz"), buckets["train"])
    write_gz(os.path.join(a.out_dir, "eval.jsonl.gz"), buckets["eval"])
    stats = dict(st)
    stats.update(files_read=len(files), train=len(buckets["train"]), eval=len(buckets["eval"]),
                 failure_types=dict(ftypes), patch_tiers=dict(tiers), sources=dict(src_count),
                 problems=len({r["problem_key"] for sp in buckets for r in buckets[sp]}))
    with open(os.path.join(a.out_dir, "stats.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    with open(os.path.join(a.out_dir, "TRIPLES_CARD.md"), "w", encoding="utf-8") as f:
        f.write(card(stats, stats["train"], stats["eval"]))
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
