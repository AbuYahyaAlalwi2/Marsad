import json, os, base64

class KeyVault:
    def __init__(self):
        self.keys = {}
    
    def save_key(self, platform, key):
        self.keys[platform] = key
        return True
    
    def get_key(self, platform):
        return self.keys.get(platform)
    
    def list_platforms(self):
        return list(self.keys.keys())
