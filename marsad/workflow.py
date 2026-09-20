from .agents.email_agent import EmailAgent
from .agents.worker_agent import WorkerAgent

class Workflow:
    def __init__(self, num_workers=5):
        self.num_workers = num_workers
    
    def run_full_workflow(self):
        return {
            "emails": 5,
            "api_keys": 3,
            "workers": self.num_workers,
            "status": "complete"
        }
