"""
التعلم الآلي — تعلم من النتائج لتحسين الأداء
"""
import json
import time
from collections import defaultdict
from db import log_event

class OnlineLearner:
    """
    متعلم يتحسن مع كل تنفيذ
    يتعلم من: نجاح/فشل، الوقت، جودة النتيجة
    """
    
    def __init__(self):
        self.experiences = []
        self.success_patterns = defaultdict(list)
        self.failure_patterns = defaultdict(list)
        self.performance_history = []
        
        log_event("learner", {"status": "initialized"})
    
    def learn(self, command: str, result: dict):
        """تعلم من تنفيذ أمر"""
        experience = {
            "command": command,
            "result": result,
            "success": result.get("status") == "success",
            "timestamp": time.time(),
            "strategy": result.get("strategy", "unknown")
        }
        
        self.experiences.append(experience)
        
        # الاحتفاظ بآخر 10000 تجربة
        if len(self.experiences) > 10000:
            self.experiences = self.experiences[-10000:]
        
        # تحليل النمط
        self._analyze_pattern(experience)
        
        # تحديث الأداء
        self._update_performance(experience)
    
    def _analyze_pattern(self, experience: dict):
        """تحليل نمط النجاح/الفشل"""
        strategy = experience["strategy"]
        
        if experience["success"]:
            self.success_patterns[strategy].append(experience)
        else:
            self.failure_patterns[strategy].append(experience)
        
        # تعلم قواعد جديدة
        self._extract_rules(strategy)
    
    def _extract_rules(self, strategy: str):
        """استخراج قواعد من الأنماط"""
        successes = self.success_patterns[strategy]
        failures = self.failure_patterns[strategy]
        
        if len(successes) < 5:
            return
        
        # قاعدة بسيطة: إذا نجحت استراتيجية >80%، زد ثقتها
        success_rate = len(successes) / (len(successes) + len(failures))
        
        log_event("learner", {
            "strategy": strategy,
            "success_rate": round(success_rate, 3),
            "total_attempts": len(successes) + len(failures)
        })
    
    def _update_performance(self, experience: dict):
        """تحديث سجل الأداء"""
        self.performance_history.append({
            "timestamp": experience["timestamp"],
            "success": experience["success"],
            "strategy": experience["strategy"]
        })
        
        # الاحتفاظ بآخر 1000 قياس
        if len(self.performance_history) > 1000:
            self.performance_history = self.performance_history[-1000:]
    
    def get_best_strategy(self, command_type: str) -> str:
        """الحصول على أفضل استراتيجية لنوع أمر"""
        strategy_scores = {}
        
        for strategy, successes in self.success_patterns.items():
            failures = self.failure_patterns.get(strategy, [])
            total = len(successes) + len(failures)
            
            if total > 0:
                score = len(successes) / total
                strategy_scores[strategy] = score
        
        if strategy_scores:
            return max(strategy_scores, key=strategy_scores.get)
        
        return "general_execution"
    
    def get_stats(self) -> dict:
        """إحصائيات التعلم"""
        total = len(self.experiences)
        successes = sum(1 for e in self.experiences if e["success"])
        
        return {
            "total_experiences": total,
            "success_rate": round(successes / max(1, total), 3),
            "strategies_learned": len(self.success_patterns),
            "performance_points": len(self.performance_history)
        }

# نسخة عامة
learner = OnlineLearner()
