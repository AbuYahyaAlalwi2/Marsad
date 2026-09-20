"""
التسلسل الهرمي للوكلاء — مليون وكيل
"""
import time
import uuid
from config import (
    MAX_AGENTS, AGENT_HIERARCHY_LEVELS,
    AGENTS_PER_SUPERVISOR, WORKERS_PER_SUPERVISOR, AGENTS_PER_WORKER,
    CLOUD_PROVIDERS
)
from db import insert_agent, get_agent, update_agent_status, count_agents_by_level, log_event

class AgentHierarchy:
    """
    بنية هرمية لتشغيل مليون وكيل:
    
    Level 0: Root (1)
    Level 1: Supervisors (100)
    Level 2: Workers (1,000)
    Level 3: Agents (10,000)
    Level 4: Sub-agents (1,000,000)
    """
    
    def __init__(self):
        self.root_id = None
        self.cloud_cycle = 0
        
        log_event("hierarchy", {
            "status": "initialized",
            "max_agents": MAX_AGENTS
        })
    
    def initialize(self) -> str:
        """تهيئة الهيكل الهرمي"""
        # إنشاء الجذر
        self.root_id = self._create_agent(level=0, parent_id=None, cloud="local")
        
        # إنشاء المشرفين
        supervisor_ids = []
        for i in range(100):  # 100 مشرف
            cloud = self._get_next_cloud()
            sid = self._create_agent(level=1, parent_id=self.root_id, cloud=cloud)
            supervisor_ids.append(sid)
        
        log_event("hierarchy", {
            "status": "initialized",
            "root": self.root_id,
            "supervisors": len(supervisor_ids)
        })
        
        return self.root_id
    
    def expand(self, supervisor_id: str, target_agents: int = 1000000) -> dict:
        """
        توسيع الهيكل ليصل لعدد الوكلاء المطلوب
        
        الخوارزمية:
        1. كل مشرف يُنشئ 10 عمال
        2. كل عامل يُنشئ 100 وكيل
        3. كل وكيل يُنشئ 10 وكلاء فرعيين
        
        النتيجة: 100 × 10 × 100 × 10 = 1,000,000
        """
        created = {
            "workers": 0,
            "agents": 0,
            "sub_agents": 0
        }
        
        # إنشاء عمال للمشرف
        worker_ids = []
        for i in range(WORKERS_PER_SUPERVISOR):
            wid = self._create_agent(level=2, parent_id=supervisor_id, cloud=self._get_next_cloud())
            worker_ids.append(wid)
            created["workers"] += 1
        
        # إنشاء وكلاء لكل عامل
        for wid in worker_ids:
            agent_ids = []
            for j in range(AGENTS_PER_WORKER):
                aid = self._create_agent(level=3, parent_id=wid, cloud=self._get_next_cloud())
                agent_ids.append(aid)
                created["agents"] += 1
            
            # إنشاء وكلاء فرعيين لكل وكيل
            for aid in agent_ids:
                for k in range(10):  # 10 وكلاء فرعيين
                    self._create_agent(level=4, parent_id=aid, cloud=self._get_next_cloud())
                    created["sub_agents"] += 1
        
        log_event("hierarchy", {
            "action": "expanded",
            "supervisor": supervisor_id,
            **created
        })
        
        return created
    
    def _create_agent(self, level: int, parent_id: str = None, cloud: str = None) -> str:
        """إنشاء وكيل جديد"""
        agent_id = f"agent_{level}_{uuid.uuid4().hex[:12]}"
        
        insert_agent(
            agent_id=agent_id,
            level=level,
            parent_id=parent_id,
            cloud_provider=cloud
        )
        
        return agent_id
    
    def _get_next_cloud(self) -> str:
        """تدوير السحابات لتوزيع الوكلاء"""
        cloud = CLOUD_PROVIDERS[self.cloud_cycle % len(CLOUD_PROVIDERS)]
        self.cloud_cycle += 1
        return cloud["name"]
    
    def get_stats(self) -> dict:
        """إحصائيات الهيكل"""
        return {
            "root": self.root_id,
            "supervisors": count_agents_by_level(1),
            "workers": count_agents_by_level(2),
            "agents": count_agents_by_level(3),
            "sub_agents": count_agents_by_level(4),
            "total": sum(count_agents_by_level(i) for i in range(5))
        }
    
    def assign_task(self, agent_id: str, task_type: str, payload: dict) -> dict:
        """تعيين مهمة لوكيل"""
        agent = get_agent(agent_id)
        
        if not agent:
            return {"status": "error", "reason": "agent_not_found"}
        
        if agent["status"] != "active":
            return {"status": "error", "reason": "agent_not_active"}
        
        # في الإنتاج: إرسال المهمة للوكيل عبر السحابة
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        
        log_event("hierarchy", {
            "action": "task_assigned",
            "agent_id": agent_id,
            "task_id": task_id,
            "task_type": task_type
        })
        
        return {
            "status": "assigned",
            "task_id": task_id,
            "agent_id": agent_id,
            "cloud": agent["cloud_provider"]
        }

# نسخة عامة
hierarchy = AgentHierarchy()
