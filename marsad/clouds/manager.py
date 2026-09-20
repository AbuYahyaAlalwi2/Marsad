class CloudManager:
    def __init__(self):
        self.clouds = []
    
    def add_cloud(self, name, region="us-east-1"):
        self.clouds.append({"name": name, "region": region})
        return {"status": "success"}
    
    def list_clouds(self):
        return self.clouds
