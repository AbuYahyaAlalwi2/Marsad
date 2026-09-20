class GeneralAgent:
    def __init__(self, name="agent", task=None):
        self.name = name
        self.task = task
    
    def run(self, **kwargs):
        return {"status": "success", "agent": self.name}
