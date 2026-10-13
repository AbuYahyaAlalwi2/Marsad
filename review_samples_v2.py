#!/usr/bin/env python3
"""
review_samples_v2.py — مراجعة جودة بشرية قبل أي نشر. stdlib فقط (يعمل على Termux).
الاستعمال:  python3 review_samples_v2.py <مجلد فيه ملفات triples_*.jsonl.gz> [عدد العيّنات=5] [seed=1]
يطبع: توزيع نوع الفشل، التشابه، حجم الفرق، الصعوبة، ثم عيّنات عشوائية مختصرة.
"""
import collections, glob, gzip, json, os, random, sys


def changed_lines(diff):
    return sum(1 for l in diff.splitlines() if l[:1] in "+-" and not l.startswith(("+++", "---")))


def bucket(x, edges):
    for e in edges:
        if x <= e:
            return f"<={e}"
    return f">{edges[-1]}"


def main():
    d = sys.argv[1] if len(sys.argv) > 1 else "."
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    files = sorted(glob.glob(os.path.join(d, "**", "*triples_*.jsonl.gz"), recursive=True))
    rows = []
    for fp in files:
        with gzip.open(fp, "rt", encoding="utf-8") as f:
            for l in f:
                try:
                    r = json.loads(l)
                    r["failing_test"]["failure_type"], r["diff"], r["token_similarity"]
                    rows.append(r)
                except Exception:
                    continue  # سطر معطوب أو ناقص: تجاهله
    if not rows:
        print("لا سجلات في", d)
        return
    print(f"ملفات: {len(files)} | سجلات: {len(rows)}")
    ft = collections.Counter(r["failing_test"]["failure_type"] for r in rows)
    print("نوع الفشل:", dict(ft))
    sim = collections.Counter(bucket(r["token_similarity"], [0.65, 0.75, 0.85, 0.95]) for r in rows)
    print("التشابه:", dict(sorted(sim.items())))
    cl = collections.Counter(bucket(changed_lines(r["diff"]), [2, 5, 10, 20, 40]) for r in rows)
    print("سطور متغيّرة في الفرق:", dict(cl))
    print("الصعوبة:", dict(collections.Counter(r.get("difficulty") for r in rows).most_common(6)))
    print("مسائل مميّزة:", len({r["problem"] for r in rows}))
    random.seed(seed)
    for r in random.sample(rows, min(n, len(rows))):
        ft_ = r["failing_test"]
        print("\n" + "=" * 70)
        print(f"{r['problem']} | {ft_['failure_type']} | sim={r['token_similarity']} | split={r['split']}")
        print("الوصف:", (r.get("description") or "").replace("\n", " ")[:200])
        print("اختبار فاشل: in=", repr(ft_["input"][:120]), "| expected=", repr(ft_["expected"][:60]),
              "| actual=", repr(ft_["actual"][:80]))
        print("\n".join(r["diff"].splitlines()[:25]))


if __name__ == "__main__":
    main()
