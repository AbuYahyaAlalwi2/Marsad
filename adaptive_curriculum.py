"""
المنهج التدريبي التكيفي — Adaptive Curriculum
مبني على أبحاث: AdaCuRL, EvoCurr, AdaRFT, VCRL

يدير دورة تدريب النموذج عبر 5 مستويات صعوبة.
"""

import json
import time
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ============================================================
# خريطة المهارات — Skill Map
# ============================================================
SKILL_MAP = {
    "programming": {
        "level_1": {
            "name": "أساسيات",
            "skills": ["طباعة", "متغيرات", "أنواع بيانات", "عمليات حسابية"],
            "difficulty": 1,
            "pass_threshold": 0.8,
        },
        "level_2": {
            "name": "تحكم",
            "skills": ["if/else", "حلقات", "دوال", "معاملات"],
            "difficulty": 2,
            "pass_threshold": 0.75,
        },
        "level_3": {
            "name": "هياكل بيانات",
            "skills": ["قوائم", "قواميس", "مجموعات", "قوائم مرتبطة"],
            "difficulty": 3,
            "pass_threshold": 0.7,
        },
        "level_4": {
            "name": "خوارزميات",
            "skills": ["ترتيب", "بحث", "برمجة ديناميكية", "graphs"],
            "difficulty": 4,
            "pass_threshold": 0.65,
        },
        "level_5": {
            "name": "مشاريع",
            "skills": ["تصميم أنظمة", "تحسين", "اختبار", "نشر"],
            "difficulty": 5,
            "pass_threshold": 0.6,
        },
    },
    "cybersecurity": {
        "level_1": {"name": "مفاهيم", "skills": ["CIA", "تهديدات", "مصادقة"], "difficulty": 1, "pass_threshold": 0.8},
        "level_2": {"name": "أدوات", "skills": ["nmap", "wireshark", "burp"], "difficulty": 2, "pass_threshold": 0.75},
        "level_3": {"name": "ثغرات", "skills": ["OWASP Top 10", "CVE", "سلسلة الاستغلال"], "difficulty": 3, "pass_threshold": 0.7},
        "level_4": {"name": "دفاع", "skills": ["SIEM", "IDS/IPS", "تحليل"], "difficulty": 4, "pass_threshold": 0.65},
        "level_5": {"name": "تحقيق", "skills": ["Forensics", "IR", "Threat Hunting"], "difficulty": 5, "pass_threshold": 0.6},
    },
}


# ============================================================
# نموذج بيانات
# ============================================================
@dataclass
class Performance:
    domain: str
    level: int
    attempts: int = 0
    successes: int = 0
    avg_score: float = 0.0
    last_attempt: float = 0


class AdaptiveCurriculum:
    def __init__(self):
        self.performance: Dict[str, Performance] = {}
        self.task_history: List[Dict] = []

    def get_current_level(self, domain: str = "programming") -> int:
        key = f"{domain}"
        if key not in self.performance:
            self.performance[key] = Performance(domain=domain, level=1)
        return self.performance[key].level

    def should_advance(self, domain: str = "programming") -> bool:
        key = f"{domain}"
        p = self.performance.get(key)
        if not p or p.attempts < 5:
            return False
        config = SKILL_MAP.get(domain, {}).get(f"level_{p.level}", {})
        threshold = config.get("pass_threshold", 0.7)
        return p.avg_score >= threshold

    def get_next_task_level(self, domain: str = "programming") -> int:
        if self.should_advance(domain):
            key = f"{domain}"
            self.performance[key].level = min(5, self.performance[key].level + 1)
            logger.info(f"[Curriculum] {domain} → level {self.performance[key].level}")
        return self.get_current_level(domain)

    def record_attempt(self, domain: str, score: float, task_id: str = None):
        key = f"{domain}"
        if key not in self.performance:
            self.performance[key] = Performance(domain=domain, level=1)
        p = self.performance[key]
        p.attempts += 1
        if score >= 0.7:
            p.successes += 1
        p.avg_score = (p.avg_score * (p.attempts - 1) + score) / p.attempts
        p.last_attempt = time.time()
        self.task_history.append({
            "domain": domain,
            "level": p.level,
            "task_id": task_id,
            "score": score,
            "ts": time.time(),
        })

    def status(self) -> Dict:
        return {
            "domains": {
                d: {
                    "level": p.level,
                    "attempts": p.attempts,
                    "successes": p.successes,
                    "avg_score": round(p.avg_score, 3),
                }
                for d, p in self.performance.items()
            },
            "total_tasks": len(self.task_history),
        }


adaptive_curriculum = AdaptiveCurriculum()
