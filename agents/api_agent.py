"""
وكيل API — التسجيل في منصات API
"""
import time
import random
from db import log_event, insert_api_provider
from agents.signup_agent import signup_agent


class APIAgent:
    """
    التسجيل في منصات API والحصول على المفاتيح
    """

    def __init__(self):
        self.platforms = [
            "google_gemini", "groq", "openrouter", "huggingface",
            "cohere", "deepseek", "together", "fireworks",
            "replicate", "mistral", "nvidia_nim", "sambanova",
            "ai21", "baseten", "modal", "cloudflare_workers_ai"
        ]

        log_event("api_agent", {"status": "initialized"})

    def register(self, platform: str) -> dict:
        """التسجيل في منصة API"""
        try:
            # استخدام SignupAgent للتسجيل
            result = signup_agent.register(platform)

            # إذا نجح، حفظ المفتاح
            if result.get("status") == "success" and result.get("api_key"):
                self._save_key(platform, result["api_key"])

            return result

        except Exception as e:
            log_event("api_agent_errors", {
                "platform": platform,
                "error": str(e)
            })
            return {"status": "error", "error": str(e)}

    def _save_key(self, platform: str, api_key: str):
        """حفظ المفتاح"""
        insert_api_provider(
            provider_key=platform,
            name=platform.replace("_", " ").title(),
            category="llm",
            api_url="",
            auth_type="bearer",
            env_key=f"{platform.upper()}_API_KEY",
            api_key=api_key,
            daily_limit=1000
        )

    def register_all(self) -> dict:
        """التسجيل في كل المنصات"""
        results = {}

        for platform in self.platforms:
            results[platform] = self.register(platform)
            time.sleep(random.uniform(2, 5))

        return results

    def get_all_keys(self) -> dict:
        """الحصول على كل المفاتيح"""
        from db import list_providers
        providers = list_providers()

        return {
            p["provider_key"]: {
                "api_key": p["api_key"],
                "status": p["status"],
                "used_today": p["used_today"],
                "daily_limit": p["daily_limit"]
            }
            for p in providers if p.get("api_key")
        }


# نسخة عامة
api_agent = APIAgent()
