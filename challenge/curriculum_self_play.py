"""
حلقة Self-Play بمنهج تدريجي (Curriculum Learning)
"""
import json, time, random
from datetime import datetime
from pathlib import Path
from challenge.judge import judge
from core.agent_loop import get_agent

REPO = Path.home() / "Marsad" / "challenge" / "repo" / "tasks.json"
LOG = Path.home() / "Marsad" / "challenge" / "curriculum_runs.jsonl"
PROGRESS = Path.home() / "Marsad" / "challenge" / "curriculum_progress.json"

TIERS = [
    {"name": "الصف 1 — بسيط",   "cvss_min": 0.0, "cvss_max": 3.9},
    {"name": "الصف 2 — متوسط",  "cvss_min": 4.0, "cvss_max": 6.9},
    {"name": "الصف 3 — عالٍ",   "cvss_min": 7.0, "cvss_max": 8.9},
    {"name": "الصف 4 — حرج",    "cvss_min": 9.0, "cvss_max": 10.0},
]
PROMOTE_THRESHOLD = 70
ROUNDS_PER_CHECK = 5


def load_tasks_by_tier():
    tasks = json.loads(REPO.read_text())
    by_tier = {i: [] for i in range(len(TIERS))}
    for t in tasks:
        cvss = float(t.get("cvss", 5.0))
        for i, tier in enumerate(TIERS):
            if tier["cvss_min"] <= cvss <= tier["cvss_max"]:
                by_tier[i].append(t); break
    return by_tier


def load_progress():
    if PROGRESS.exists():
        return json.loads(PROGRESS.read_text())
    return {"current_tier": 0, "recent_scores": []}


def save_progress(p):
    PROGRESS.write_text(json.dumps(p, ensure_ascii=False, indent=2))


def run_round(task, agent):
    prompt = (f"حلّل الثغرة {task.get('cve', '')}.\n"
              f"الكود قبل الإصلاح:\n{task.get('before', '')[:500]}\n"
              f"اقترح الإصلاح المناسب.")
    result = agent.run(prompt)
    answer = result.get("final", "")
    score = judge(task, answer)
    return {"ts": datetime.now().isoformat(), "cve": task.get("cve", ""),
            "tier": task.get("_tier_name", ""),
            "solver_status": result.get("status"),
            "solver_answer": answer[:500], "judge": score}


def curriculum_loop(max_rounds=200):
    by_tier = load_tasks_by_tier()
    progress = load_progress()
    agent = get_agent()
    for round_i in range(max_rounds):
        tier_idx = progress["current_tier"]
        tier = TIERS[tier_idx]
        pool = by_tier.get(tier_idx) or []
        if not pool:
            print(f"[curriculum] {tier['name']} فارغ — تخطي")
            progress["current_tier"] = min(tier_idx + 1, len(TIERS) - 1)
            save_progress(progress); continue
        task = dict(random.choice(pool))
        task["_tier_name"] = tier["name"]
        print(f"\n=== جولة {round_i + 1} | {tier['name']} | {task.get('cve')} ===")
        entry = run_round(task, agent)
        score = entry["judge"]["score"]
        print(f"[judge] {score}/100")
        with LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        progress["recent_scores"].append(score)
        progress["recent_scores"] = progress["recent_scores"][-ROUNDS_PER_CHECK:]
        if len(progress["recent_scores"]) >= ROUNDS_PER_CHECK:
            avg = sum(progress["recent_scores"]) / len(progress["recent_scores"])
            if avg >= PROMOTE_THRESHOLD and tier_idx < len(TIERS) - 1:
                progress["current_tier"] += 1
                progress["recent_scores"] = []
                print(f"🎓 ترقية! متوسط {avg:.1f}")
        save_progress(progress)
        time.sleep(2)


if __name__ == "__main__":
    curriculum_loop()
