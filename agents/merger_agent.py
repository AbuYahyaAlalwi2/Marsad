"""
وكيل الصهر — صهر النماذج تلقائياً
"""
import time
from db import log_event
from merge.omni_merger import merger


class MergerAgent:
    """
    صهر النماذج البرمجية
    """

    def __init__(self):
        log_event("merger_agent", {"status": "initialized"})

    def merge_all(self) -> dict:
        """صهر كل النماذج"""
        try:
            result = merger.merge_all()

            log_event("merger_agent", {
                "status": result.get("status"),
                "models_merged": result.get("models_merged", 0)
            })

            return result

        except Exception as e:
            log_event("merger_agent_errors", {"error": str(e)})
            return {"status": "error", "error": str(e)}

    def merge_programming(self) -> dict:
        """صهر النماذج البرمجية فقط"""
        # تخصيص للنماذج البرمجية
        return self.merge_all()

    def get_merge_plan(self) -> dict:
        """خطة الصهر"""
        return merger.get_merge_plan()


# نسخة عامة
merger_agent = MergerAgent()
