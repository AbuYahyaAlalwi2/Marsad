#!/usr/bin/env python3
"""
build_mut_bundle_v1.py — يجمّع سجلات مصنع الطفرات في حزمة نشر نظيفة (لا ينفّذ أي كود من البيانات).
يفعل: قراءة muttriples_*.jsonl.gz -> رفض المعطوب/الناقص/ذي نمط السر/ترخيص غير مسموح
-> توحيد اسم المشروع (attrs2 -> attrs) -> إزالة التكرار (id و زوج الكود)
-> سقف لكل مشروع (حتمي) -> تقسيم حسب المشروع كله (sha1(repo)%100<15 => eval)
-> train.jsonl.gz, eval.jsonl.gz, stats.json, NOTICE.md, MUTATIONS_CARD.md, REVIEW_SAMPLE.md
"""
import argparse, collections, glob, gzip, hashlib, json, os, random, re

PAT = re.compile(r"(hf_[A-Za-z0-9]{30,}|ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|"
                 r"sk-or-[A-Za-z0-9-]{20,}|sk-[A-Za-z0-9]{32,}|gsk_[A-Za-z0-9]{30,}|AKIA[0-9A-Z]{16}|"
                 r"[0-9]{8,10}:AA[A-Za-z0-9_-]{30,})")
REQ = ("id", "repo", "commit_sha", "license", "file", "function", "mutation_type", "fixed_code", "buggy_code", "failing_test")
ALLOWED = {"MIT", "Apache-2.0", "BSD"}
ALIAS = {"attrs2": "attrs", "pyparsing2": "pyparsing", "rich2": "rich"}


def h(s):
    return hashlib.sha1(s.encode("utf-8", "replace")).hexdigest()


def split_for(repo):
    return "eval" if int(hashlib.sha1(repo.encode()).hexdigest(), 16) % 100 < 15 else "train"


def write_gz(path, rows):
    with gzip.open(path, "wt", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--specs", nargs="*", default=sorted(glob.glob("mut_repos_v*.json")))
    ap.add_argument("--cap-per-repo", type=int, default=800)
    ap.add_argument("--sample", type=int, default=25)
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    urls = {}
    for sp in a.specs:
        for r in json.load(open(sp)):
            urls[ALIAS.get(r["name"], r["name"])] = r["url"]
    files = sorted(glob.glob(os.path.join(a.in_dir, "**", "muttriples_*.jsonl.gz"), recursive=True))
    st, seen_id, seen_pair = collections.Counter(), set(), set()
    by_repo = collections.defaultdict(list)
    for fp in files:
        with gzip.open(fp, "rt", encoding="utf-8") as f:
            for line in f:
                st["read"] += 1
                try:
                    r = json.loads(line)
                except Exception:
                    st["bad_json"] += 1; continue
                if not all(k in r for k in REQ):
                    st["missing_fields"] += 1; continue
                if r["license"] not in ALLOWED:
                    st["license_not_allowed"] += 1; continue
                if PAT.search(line):
                    st["dropped_secret_pattern"] += 1; continue
                if r["buggy_code"] == r["fixed_code"]:
                    st["identical_code"] += 1; continue
                r["repo"] = ALIAS.get(r["repo"], r["repo"])
                pair = h(r["repo"] + "\0" + r["file"] + "\0" + r["buggy_code"] + "\0" + r["fixed_code"])
                if r["id"] in seen_id or pair in seen_pair:
                    st["duplicate"] += 1; continue
                seen_id.add(r["id"]); seen_pair.add(pair)
                r["repo_url"] = urls.get(r["repo"], "")
                by_repo[r["repo"]].append(r)
    kept, before, after = [], {}, {}
    for repo, rows in sorted(by_repo.items()):
        rows.sort(key=lambda r: h(r["id"]))          # ترتيب حتمي
        before[repo] = len(rows)
        rows = rows[: a.cap_per_repo]
        after[repo] = len(rows)
        sp = split_for(repo)
        for r in rows:
            r["split"] = sp
            r["origin"] = "procedural"
            kept.append(r)
    st["dropped_by_cap"] = sum(before.values()) - sum(after.values())
    buckets = {"train": [], "eval": []}
    for r in kept:
        buckets[r["split"]].append(r)
    for k in buckets:
        buckets[k].sort(key=lambda r: r["id"])
    write_gz(os.path.join(a.out_dir, "train.jsonl.gz"), buckets["train"])
    write_gz(os.path.join(a.out_dir, "eval.jsonl.gz"), buckets["eval"])
    kinds = collections.Counter(r["mutation_type"] for r in kept)
    stats = dict(st)
    stats.update(files_read=len(files), train=len(buckets["train"]), eval=len(buckets["eval"]), repos=len(after),
                 per_repo_before_cap=before, per_repo_after_cap=after, by_mutation_type=dict(kinds),
                 eval_repos=sorted({r["repo"] for r in buckets["eval"]}), cap_per_repo=a.cap_per_repo)
    json.dump(stats, open(os.path.join(a.out_dir, "stats.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    # NOTICE: إسناد كل مشروع مصدر (مطلوب بتراخيص MIT/Apache/BSD)
    notice = ["# NOTICE — upstream projects used to derive these records", ""]
    for repo in sorted(after):
        any_r = next(r for r in kept if r["repo"] == repo)
        notice.append(f"- {repo} — {any_r['repo_url']} — license: {any_r['license']} — commit: {any_r['commit_sha']}")
    open(os.path.join(a.out_dir, "NOTICE.md"), "w", encoding="utf-8").write("\n".join(notice) + "\n")
    card = f"""---
license: other
license_name: per-record-upstream-permissive
pretty_name: Marsad verified mutation bug-fix pairs (Python)
---
# Marsad verified mutation pairs

Each record: a function from a real open-source Python project (`fixed_code`), a deterministic AST mutation of it
(`buggy_code`), and the upstream test that **passes before and fails after** the mutation (`failing_test`).
Accepted only if the project's original test suite passed first. No LLM involved; `origin = procedural`.

- train: {stats['train']} | eval: {stats['eval']} | projects: {stats['repos']} | cap per project: {a.cap_per_repo}
- split is by whole project (sha1(project) % 100 < 15 -> eval), so no project appears on both sides.
- mutation types: {json.dumps(dict(kinds), ensure_ascii=False)}

## Licenses
Code comes from projects under MIT, Apache-2.0 or BSD licenses. Every record carries `license`, `repo_url`,
`commit_sha`. See NOTICE.md for the full attribution list. The mutations are synthetic edits, not human-written fixes.

## Limitations
- Synthetic, simple bugs (operator swap, off-by-one, negated condition, dropped return). Not a substitute for real-world fixes.
- A mutation counts as detected if any upstream test failed; the failing test may not be the most relevant one.
- Function-level snippets (formatting normalized through ast.unparse; comments removed).
"""
    open(os.path.join(a.out_dir, "MUTATIONS_CARD.md"), "w", encoding="utf-8").write(card)
    rnd = random.Random(1)
    pool = list(kept); rnd.shuffle(pool)
    lines = ["# Review sample (random, seed=1)", "", "For each: is the diff a plausible bug, and does the failing test explain it?", ""]
    for r in pool[: a.sample]:
        lines += [f"## {r['repo']} · {r['file']} · {r['function']} · {r['mutation_type']}",
                  f"failing: `{r['failing_test']['name']}` — {r['failing_test'].get('message','')[:160]}", "```diff", r.get("diff", "")[:900], "```", ""]
    open(os.path.join(a.out_dir, "REVIEW_SAMPLE.md"), "w", encoding="utf-8").write("\n".join(lines))
    print(json.dumps({k: v for k, v in stats.items() if not k.startswith("per_repo")}, ensure_ascii=False, indent=1))
    print("per repo before->after:", {k: f"{before[k]}->{after[k]}" for k in after})


if __name__ == "__main__":
    main()
