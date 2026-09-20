"""Real signup validator.

This file intentionally does not fabricate API keys or simulate successful account
creation. It only validates whether a real credential is configured.
"""
import os


class RealSignupAgent:
    def __init__(self):
        self.providers = {
            "huggingface": "HF_TOKEN",
            "github": "GITHUB_TOKEN",
            "gitlab": "GITLAB_TOKEN",
            "openrouter": "OPENROUTER_API_KEY",
            "groq": "GROQ_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
            "mistral": "MISTRAL_API_KEY",
            "cohere": "COHERE_API_KEY",
            "together": "TOGETHER_API_KEY",
        }

    def validate(self, platform: str) -> dict:
        env_key = self.providers.get(platform)
        if not env_key:
            return {"status": "unsupported", "provider": platform}

        value = os.environ.get(env_key, "").strip()
        if not value:
            return {"status": "missing_credentials", "provider": platform, "env_key": env_key}

        return {"status": "configured", "provider": platform, "env_key": env_key}

    def register_all(self, platforms=None):
        platforms = platforms or list(self.providers.keys())
        return {p: self.validate(p) for p in platforms}


real_signup = RealSignupAgent()
