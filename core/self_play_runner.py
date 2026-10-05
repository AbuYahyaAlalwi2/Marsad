"""self_play_runner.py — حلقة تحسين ذاتي من CVEfixes.
كل جولة: LLM يحلل مهمة → يقترح إصلاح → judge_v2 يقيّم → تسجيل → ترقية tier عند النجاح المتكرر.
"""
import json, time, random, hashlib
from pathlib import Path
from datetime import datetime

LOG = Path.home() / "Marsad" / "logs" / "self_play.jsonl"
LOG.parent.mkdir(exist_ok=True, parents=True)

TIERS = [(0.0, 3.9, "T1"), (4.0, 6.9, "T2"), (7.0, 8.9, "T3"), (9.0, 10.0, "T4")]
PROMOTE_THRESHOLD = 65
PROMOTE_AFTER = 3
DEMOTE_AFTER = 3


def load_tasks(path=None):
    """يحمّل مهام من task_builder (ملف JSON) أو من datasets مباشرة."""
    if path and Path(path).exists():
        return json.loads(Path(path).read_text())
    from datasets import load_dataset
    from core._handoff.task_builder import build_tasks
    ds = load_dataset("hitoshura25/cvefixes", split="train", streaming=True)
    rows = []
    for i, row in enumerate(ds):
        if i >= 400: break
        rows.append(row)
    tasks, stats = build_tasks(rows, limit=200)
    print(f"✓ built {len(tasks)} tasks | {stats}")
    return tasks


def pick_task(tasks, tier):
    lo, hi, name = TIERS[tier]
    pool = [t for t in tasks if t.get("split") == "train" and lo <= t.get("cvss", 0) <= hi]
    return random.choice(pool) if pool else None


def run(llm, tasks, max_rounds=50, tier=0):
    from core._handoff.judge_v2 import judge
    import httpx

    history = []
    recent = []
    for r in range(max_rounds):
        task = pick_task(tasks, tier)
        if not task:
            # لو مافيش مهام في الـ tier الحالي، نرقّي. لو وصلنا الآخر، نرجع للأول.
            tried = 0
            while not task and tried < len(TIERS):
                tier = (tier + 1) % len(TIERS)
                task = pick_task(tasks, tier)
                tried += 1
            if not task:
                print(f"[{r:03d}] no tasks available — stopping")
                break

        prompt = (
            f"أنت محلل أمني. حلّل هذه الثغرة {task['cve']} (CVSS {task['cvss']:.1f}, {task['cwe']}).\n\n"
            f"الكود قبل:\n```{task['language']}\n{task['before'][:1500]}\n```\n\n"
            f"أعطِ:\n1) نوع الثغرة (CWE)\n2) الإصلاح في كتلة ``` كود واحدة."
        )
        try:
            resp = llm.chat([{"role": "user", "content": prompt}], max_tokens=800, temperature=0.3)
            answer = resp.get("content", "")
            err = resp.get("error")
        except Exception as e:
            answer, err = "", str(e)

        j = judge(task, answer)
        score = j["score"]

        entry = {
            "round": r, "ts": time.time(),
            "cve": task["cve"], "cvss": task["cvss"], "tier": tier,
            "score": score, "judge_details": j["details"],
            "error": err,
        }
        history.append(entry)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        recent.append(score); recent = recent[-PROMOTE_AFTER:]
        print(f"[{r:03d}] T{tier} {task['cve']} cvss={task['cvss']:.1f} score={score}")

        if len(recent) >= PROMOTE_AFTER:
            avg = sum(recent) / len(recent)
            if avg >= PROMOTE_THRESHOLD and tier < len(TIERS) - 1:
                tier += 1; recent = []
                print(f"  ↑ promoted to T{tier}")

    return history


if __name__ == "__main__":
    from core.llm_adapter import MarsadLLM
    llm = MarsadLLM()
    print("llm:", llm.base_url)
    tasks = load_tasks()
    h = run(llm, tasks, max_rounds=3)
    print(f"\n--- {len(h)} rounds done ---")
