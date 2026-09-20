"""Real provider validation only.

This module never creates fake API keys or fake account registrations.
It validates credentials from environment variables only.
"""
import os
import time


class SignupAgent:
    """Validate real provider credentials instead of generating fake keys."""

    def __init__(self):
        self.platforms = {
            "github": "GITHUB_TOKEN",
            "gitlab": "GITLAB_TOKEN",
            "huggingface": "HF_TOKEN",
            "groq": "GROQ_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
            "together": "TOGETHER_API_KEY",
            "fireworks": "FIREWORKS_API_KEY",
            "replicate": "REPLICATE_API_TOKEN",
            "mistral": "MISTRAL_API_KEY",
            "cohere": "COHERE_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
        }

    def register(self, platform: str, email_data: dict = None) -> dict:
        if platform not in self.platforms:
            return {"status": "unsupported", "provider": platform}

        env_key = self.platforms[platform]
        value = os.environ.get(env_key, "").strip()
        if not value:
            return {
                "status": "missing_credentials",
                "provider": platform,
                "env_key": env_key,
                "message": "يجب إدخال المفتاح الحقيقي في متغيرات البيئة."
            }

        return {
            "status": "configured",
            "provider": platform,
            "env_key": env_key,
            "has_real_value": True,
            "message": "المفتاح موجود وهو جاهز للاستخدام الحقيقي."
        }

    def register_all(self, email_data: dict = None) -> dict:
        results = {}
        for platform in self.platforms:
            results[platform] = self.register(platform, email_data)
            time.sleep(0.2)
        return results

    def _save_api_key(self, platform: str, result: dict):
        return False


signup_agent = SignupAgent()
