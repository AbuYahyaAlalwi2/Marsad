"""
وكيل السرب — تشغيل مليون وكيل
"""
import time
from db import log_event
from agents.hierarchy import hierarchy


class SwarmAgent:
    """
    تشغيل سرب الوكلاء
    """

    def __init__(self):
        log_event("swarm_agent", {"status": "initialized"})

    def deploy(self, count: int = 1000) -> dict:
        """نشر الوكلاء"""
        try:
            # توسيع الهيكل الهرمي
            result = hierarchy.expand(hierarchy.root_id, target_agents=count)

            log_event("swarm_agent", {
                "deployed": result.get("sub_agents", 0),
                "target": count
            })

            return {
                "status": "success",
                "deployed": result.get("sub_agents", 0),
                "stats": hierarchy.get_stats()
            }

        except Exception as e:
            log_event("swarm_agent_errors", {"error": str(e)})
            return {"status": "error", "error": str(e)}

    def deploy_full(self) -> dict:
        """نشر المليون وكيل كاملاً"""
        return self.deploy(count=1000000)


# نسخة عامة
swarm_agent = SwarmAgent()
