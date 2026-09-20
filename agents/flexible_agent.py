"""
وكيل مرن — إضافة وكلاء جديدة بسهولة
"""
import os
import importlib
import inspect
from db import log_event, insert_agent


class FlexibleAgentSystem:
    """
    نظام وكلاء مرن:
    - إضافة وكلاء جديدة بملف Python واحد
    - تسجيل تلقائي للـhooks
    - إدارة دورة حياة الوكلاء
    - مراقبة الأداء
    """

    def __init__(self):
        self.agents = {}
        self.agent_dir = os.path.join(os.path.dirname(__file__), "custom")

        os.makedirs(self.agent_dir, exist_ok=True)

        log_event("flexible_agent", {"status": "initialized"})

    def create_agent_template(self, name: str) -> str:
        """إنشاء قالب وكيل جديد"""
        template = f'''"""
وكيل {name} — وصف الوكيل
"""
from db import log_event


class {name.title().replace("_", "")}Agent:
    """
    وكيل {name}
    """

    def __init__(self):
        self.name = "{name}"
        self.status = "initialized"
        self.task_count = 0

        log_event("agent_{name}", {{"status": "initialized"}})

    def run(self, **kwargs):
        """تشغيل الوكيل"""
        self.task_count += 1

        # منطق الوكيل هنا
        result = {{
            "status": "success",
            "agent": self.name,
            "task": self.task_count,
            "params": kwargs
        }}

        log_event("agent_{name}", {{
            "action": "executed",
            "task": self.task_count
        }})

        return result

    def get_status(self):
        """حالة الوكيل"""
        return {{
            "name": self.name,
            "status": self.status,
            "tasks_completed": self.task_count
        }}


# نسخة عامة
agent = {name.title().replace("_", "")}Agent()
'''

        path = os.path.join(self.agent_dir, f"{name}.py")

        with open(path, "w", encoding="utf-8") as f:
            f.write(template)

        log_event("flexible_agent", {"created_template": name})

        return path

    def load_agent(self, name: str):
        """تحميل وكيل"""
        path = os.path.join(self.agent_dir, f"{name}.py")

        if not os.path.exists(path):
            return None

        try:
            spec = importlib.util.spec_from_file_location(name, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            self.agents[name] = module

            # تسجيل في قاعدة البيانات
            insert_agent(
                agent_id=f"custom_{name}",
                level=5,  # مستوى الوكلاء المخصصة
                parent_id="root",
                cloud_provider="local"
            )

            log_event("flexible_agent", {"loaded": name})

            return module

        except Exception as e:
            log_event("flexible_agent_errors", {"agent": name, "error": str(e)})
            return None

    def load_all_agents(self):
        """تحميل كل الوكلاء المخصصة"""
        loaded = []

        for filename in os.listdir(self.agent_dir):
            if filename.endswith(".py") and not filename.startswith("_"):
                name = filename[:-3]
                module = self.load_agent(name)

                if module:
                    loaded.append(name)

        return loaded

    def run_agent(self, name: str, **kwargs):
        """تشغيل وكيل"""
        if name not in self.agents:
            module = self.load_agent(name)
            if not module:
                return {"status": "error", "reason": f"وكيل غير موجود: {name}"}

        agent = self.agents[name]

        # البحث عن دالة run
        if hasattr(agent, 'agent') and hasattr(agent.agent, 'run'):
            return agent.agent.run(**kwargs)
        elif hasattr(agent, 'run'):
            return agent.run(**kwargs)
        else:
            return {"status": "error", "reason": "وكيل لا يحتوي على دالة run"}

    def list_agents(self):
        """قائمة الوكلاء"""
        agents = []

        # الوكلاء المحملة
        for name, module in self.agents.items():
            status = {}
            if hasattr(module, 'agent') and hasattr(module.agent, 'get_status'):
                status = module.agent.get_status()

            agents.append({
                "name": name,
                "loaded": True,
                "status": status.get("status", "unknown"),
                "tasks": status.get("tasks_completed", 0)
            })

        # الوكلاء غير المحملة
        for filename in os.listdir(self.agent_dir):
            if filename.endswith(".py") and not filename.startswith("_"):
                name = filename[:-3]
                if name not in self.agents:
                    agents.append({
                        "name": name,
                        "loaded": False,
                        "status": "not_loaded",
                        "tasks": 0
                    })

        return agents

    def delete_agent(self, name: str):
        """حذف وكيل"""
        path = os.path.join(self.agent_dir, f"{name}.py")

        if os.path.exists(path):
            os.remove(path)

        if name in self.agents:
            del self.agents[name]

        log_event("flexible_agent", {"deleted": name})

        return {"status": "success", "deleted": name}


# نسخة عامة
flexible_agents = FlexibleAgentSystem()
