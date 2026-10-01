"""يبني tasks.json من CVEfixes dataset."""
import json
from pathlib import Path

OUT = Path.home() / "Marsad" / "challenge" / "repo"
OUT.mkdir(parents=True, exist_ok=True)
TASKS_FILE = OUT / "tasks.json"


def build(limit: int = 200):
    from datasets import load_dataset
    print("→ loading CVEfixes...")
    ds = load_dataset("ASSERT-KTH/CVEfixes", split="train", streaming=True)

    print("→ collecting tasks...")
    tasks = []
    for i, row in enumerate(ds):
        if i >= limit:
            break
        # احصل على الكود (من أي حقل متاح)
        before = (row.get("func_before") or
                  row.get("code_before") or
                  row.get("before") or "")
        after = (row.get("func_after") or
                 row.get("code_after") or
                 row.get("after") or "")
        if not before or not after:
            continue
        tasks.append({
            "id": f"cve-{row.get('cve_id', i)}",
            "cve": row.get("cve_id", ""),
            "language": row.get("language", "python"),
            "before": str(before)[:5000],
            "after": str(after)[:5000],
            "commit": row.get("hash", ""),
            "cvss": float(row.get("cvss") or 5.0),
        })
        if len(tasks) % 50 == 0 and len(tasks) > 0:
            print(f"   collected {len(tasks)}")

    TASKS_FILE.write_text(json.dumps(tasks, ensure_ascii=False, indent=2))
    print(f"✓ saved {len(tasks)} tasks to {TASKS_FILE}")

    # إحصاءات
    from collections import Counter
    langs = Counter(t["language"] for t in tasks)
    print(f"   languages: {dict(langs)}")
    cvss_buckets = {"low": 0, "med": 0, "high": 0, "crit": 0}
    for t in tasks:
        c = t["cvss"]
        if c < 4: cvss_buckets["low"] += 1
        elif c < 7: cvss_buckets["med"] += 1
        elif c < 9: cvss_buckets["high"] += 1
        else: cvss_buckets["crit"] += 1
    print(f"   cvss: {cvss_buckets}")


if __name__ == "__main__":
    build(limit=200)
