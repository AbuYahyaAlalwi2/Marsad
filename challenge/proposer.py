"""Proposer — يختار مهمة من Repository، مع دعم Curriculum."""
import json
import random
from pathlib import Path

REPO = Path.home() / "Marsad" / "challenge" / "repo" / "tasks.json"

TIERS = [
    {"name": "الصف 1 — بسيط",   "cvss_min": 0.0, "cvss_max": 3.9},
    {"name": "الصف 2 — متوسط",  "cvss_min": 4.0, "cvss_max": 6.9},
    {"name": "الصف 3 — عالٍ",   "cvss_min": 7.0, "cvss_max": 8.9},
    {"name": "الصف 4 — حرج",    "cvss_min": 9.0, "cvss_max": 10.0},
]


def _load():
    if not REPO.exists():
        return []
    return json.loads(REPO.read_text())


def propose(tier_idx: int = None):
    """يختار مهمة عشوائية. إن حُدد tier_idx، يختار من نفس الصف."""
    tasks = _load()
    if not tasks:
        return None

    if tier_idx is None:
        return random.choice(tasks)

    tier = TIERS[tier_idx]
    pool = [t for t in tasks
            if tier["cvss_min"] <= float(t.get("cvss", 5.0)) <= tier["cvss_max"]]
    if not pool:
        return None

    task = dict(random.choice(pool))
    task["_tier_name"] = tier["name"]
    task["_tier_idx"] = tier_idx
    return task


def stats():
    """إحصاءات المهام لكل صف."""
    tasks = _load()
    out = {}
    for i, tier in enumerate(TIERS):
        pool = [t for t in tasks
                if tier["cvss_min"] <= float(t.get("cvss", 5.0)) <= tier["cvss_max"]]
        out[tier["name"]] = len(pool)
    out["total"] = len(tasks)
    return out


if __name__ == "__main__":
    print("Repository stats:", stats())
    t = propose()
    if t:
        print(f"\nSample task: {t.get('cve')} ({t.get('language')})")
        print(f"  before: {t.get('before','')[:80]}...")
    else:
        print("لا يوجد repository — شغّل build_repo.py أولاً")
