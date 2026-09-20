class WorkerAgent:
    def __init__(self, name="worker"):
        self.name = name
    
    def run(self, task="collect", **kwargs):
        return {"status": "success", "task": task}
