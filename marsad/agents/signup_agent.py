class SignupAgent:
    def __init__(self, platform):
        self.platform = platform
    
    def signup(self, email_data):
        return f"key_{self.platform}"
