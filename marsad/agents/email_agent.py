class EmailAgent:
    def create_batch(self, count=10):
        return [{"email": f"test{i}@example.com"} for i in range(count)]
