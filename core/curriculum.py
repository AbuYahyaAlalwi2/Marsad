"""
Curriculum Engine — محرك رفع الصعوبة التدريجي
يرفع مستوى التحدي تلقائياً بناءً على أداء النموذج
"""

import json
import time
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional
from enum import Enum

from knowledge_store import get_store, Severity


# ─── Difficulty Levels ────────────────────────────────────────────────────────

@dataclass
class DifficultyLevel:
    name:         str
    cvss_min:     float
    cvss_max:     float
    description:  str
    pass_rate:    float   # نسبة النجاح المطلوبة للترقي (0.0-1.0)


LEVELS = [
    DifficultyLevel("L1_BASIC",    0.0,  3.9,  "SQL Injection, XSS بسيط",         0.85),
    DifficultyLevel("L2_LOW",      4.0,  5.9,  "Buffer Overflow, Path Traversal",  0.80),
    DifficultyLevel("L3_MEDIUM",   6.0,  6.9,  "CSRF, XXE, Deserialization",       0.75),
    DifficultyLevel("L4_HIGH",     7.0,  8.4,  "RCE, Privilege Escalation",        0.70),
    DifficultyLevel("L5_CRITICAL", 8.5,  9.4,  "Zero-days, APT Techniques",        0.65),
    DifficultyLevel("L6_APEX",     9.5, 10.0,  "Nation-state level, 0-day chains", 0.60),
]


# ─── Session State ────────────────────────────────────────────────────────────

STATE_PATH = Path(__file__).parent.parent / "database" / "curriculum_state.json"

def _load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {
        "current_level": 0,
        "session_results": [],
        "total_pass": 0,
        "total_fail": 0,
        "level_history": [],
    }

def _save_state(state: dict):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2))


# ─── Curriculum Engine ────────────────────────────────────────────────────────

class CurriculumEngine:
    """
    يتحكم في صعوبة التحديات تلقائياً:
    - النموذج يمر 85%+ من L1 → ينتقل لـ L2
    - النموذج يفشل في L3 → يرجع لـ L2 مع تركيز على نقاط الضعف
    - الفشل يُحفظ كبيانات تدريب أيضاً
    """

    def __init__(self):
        self.state = _load_state()
        self.store = get_store()

    @property
    def current_level(self) -> DifficultyLevel:
        idx = min(self.state["current_level"], len(LEVELS) - 1)
        return LEVELS[idx]

    def next_challenge(self) -> dict:
        """
        يختار التحدي التالي من قاعدة البيانات
        بناءً على المستوى الحالي
        """
        lvl = self.current_level
        store = get_store()

        with store._conn() as conn:
            rows = conn.execute("""
                SELECT cve_id, title, vulnerable_code, explanation, cvss_score, severity
                FROM records
                WHERE cvss_score BETWEEN ? AND ?
                  AND vulnerable_code != ''
                  AND verified = 1
                ORDER BY RANDOM()
                LIMIT 1
            """, (lvl.cvss_min, lvl.cvss_max)).fetchall()

        if not rows:
            # لا توجد بيانات بعد — أعطِ مثالاً اصطناعياً
            return self._synthetic_challenge(lvl)

        r = rows[0]
        return {
            "level":          lvl.name,
            "cvss":           r[4],
            "severity":       r[5],
            "cve_id":         r[0],
            "title":          r[1],
            "task":           f"اكتشف وأصلح الثغرة في الكود التالي:\n\n{r[2]}",
            "hint_available": lvl.cvss_min >= 7.0,  # تلميح للمستويات العالية فقط
        }

    def record_result(
        self,
        challenge:    dict,
        model_answer: str,
        is_correct:   bool,
        model_id:     str = "marsad-v1",
    ):
        """
        يسجل نتيجة التحدي:
        - نجاح → يحسب للترقي
        - فشل → يحفظ الخطأ في قاعدة الأخطاء (لا يكرره)
        """
        result = {
            "level":      challenge["level"],
            "cvss":       challenge.get("cvss", 0),
            "correct":    is_correct,
            "timestamp":  time.time(),
        }
        self.state["session_results"].append(result)

        if is_correct:
            self.state["total_pass"] += 1
        else:
            self.state["total_fail"] += 1
            # احفظ الخطأ لمنع التكرار
            self.store.log_error(
                error_type    = f"WRONG_DETECTION_{challenge['level']}",
                context       = challenge.get("task", "")[:200],
                wrong_answer  = model_answer[:500],
                correct_answer= challenge.get("cve_id", "unknown"),
                lesson        = f"النموذج فشل في اكتشاف ثغرة CVSS={challenge.get('cvss')}",
                cve_related   = challenge.get("cve_id"),
            )

        self._maybe_advance()
        _save_state(self.state)

    def _maybe_advance(self):
        """يقرر الترقي أو التراجع بناءً على آخر 10 نتائج"""
        recent = self.state["session_results"][-10:]
        if len(recent) < 5:
            return  # انتظر بيانات كافية

        pass_rate = sum(1 for r in recent if r["correct"]) / len(recent)
        lvl_idx   = self.state["current_level"]
        lvl       = LEVELS[lvl_idx]

        if pass_rate >= lvl.pass_rate and lvl_idx < len(LEVELS) - 1:
            # ترقي
            self.state["current_level"] += 1
            self.state["level_history"].append({
                "from":      lvl.name,
                "to":        LEVELS[lvl_idx + 1].name,
                "pass_rate": pass_rate,
                "timestamp": time.time(),
            })
            print(f"🎯 ترقي: {lvl.name} → {LEVELS[lvl_idx+1].name} (نجاح {pass_rate:.0%})")

        elif pass_rate < 0.40 and lvl_idx > 0:
            # تراجع — النموذج يحتاج مراجعة
            self.state["current_level"] -= 1
            print(f"⬇ تراجع: {lvl.name} → {LEVELS[lvl_idx-1].name} (نجاح {pass_rate:.0%})")

    def _synthetic_challenge(self, lvl: DifficultyLevel) -> dict:
        """تحدي اصطناعي عندما لا توجد بيانات كافية"""
        examples = {
            "L1_BASIC": {
                "task": "اكتشف الثغرة:\n```python\nquery = f\"SELECT * FROM users WHERE id={user_input}\"\n```",
                "cve_id": "SYNTHETIC-SQLi-001",
            },
            "L2_LOW": {
                "task": "اكتشف الثغرة:\n```c\nchar buf[64]; strcpy(buf, user_input);\n```",
                "cve_id": "SYNTHETIC-BOF-001",
            },
            "L3_MEDIUM": {
                "task": "اكتشف الثغرة:\n```python\nimport pickle; pickle.loads(user_data)\n```",
                "cve_id": "SYNTHETIC-DESER-001",
            },
        }
        ex = examples.get(lvl.name, examples["L1_BASIC"])
        return {
            "level":          lvl.name,
            "cvss":           (lvl.cvss_min + lvl.cvss_max) / 2,
            "severity":       "MEDIUM",
            "cve_id":         ex["cve_id"],
            "title":          f"تحدي اصطناعي - {lvl.name}",
            "task":           ex["task"],
            "hint_available": False,
        }

    def status(self) -> dict:
        recent = self.state["session_results"][-10:]
        pass_rate = (
            sum(1 for r in recent if r["correct"]) / len(recent)
            if recent else 0
        )
        return {
            "current_level":  self.current_level.name,
            "description":    self.current_level.description,
            "pass_rate":      f"{pass_rate:.0%}",
            "total_pass":     self.state["total_pass"],
            "total_fail":     self.state["total_fail"],
            "next_level":     LEVELS[min(self.state["current_level"]+1, len(LEVELS)-1)].name,
            "needed_to_advance": f"{self.current_level.pass_rate:.0%}",
        }
