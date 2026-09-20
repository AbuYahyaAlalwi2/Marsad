"""
وكيل التسجيل — تسجيل آلي في المنصات
"""
import time
import random
from db import log_event, insert_api_provider


class SignupAgent:
    """
    التسجيل الآلي في المنصات باستخدام الإيميلات المؤقتة
    """

    def __init__(self):
        self.platforms = {
            "github": self._signup_github,
            "gitlab": self._signup_gitlab,
            "huggingface": self._signup_huggingface,
            "groq": self._signup_groq,
            "openrouter": self._signup_openrouter,
            "together": self._signup_together,
            "fireworks": self._signup_fireworks,
            "replicate": self._signup_replicate,
            "mistral": self._signup_mistral,
            "cohere": self._signup_cohere,
            "deepseek": self._signup_deepseek,
        }

        log_event("signup_agent", {"status": "initialized"})

    def register(self, platform: str, email_data: dict = None) -> dict:
        """التسجيل في منصة محددة"""
        if platform not in self.platforms:
            return {"status": "error", "reason": f"منصة غير مدعومة: {platform}"}

        try:
            # محاكاة التسجيل (في الإنتاج: استخدام Playwright)
            result = self.platforms[platform](email_data)

            # حفظ المفتاح إذا نجح
            if result.get("api_key"):
                self._save_api_key(platform, result)

            log_event("signup_agent", {
                "platform": platform,
                "status": result.get("status"),
                "email": email_data.get("email") if email_data else None
            })

            return result

        except Exception as e:
            log_event("signup_agent_errors", {
                "platform": platform,
                "error": str(e)
            })
            return {"status": "error", "error": str(e)}

    def _signup_github(self, email_data: dict) -> dict:
        """التسجيل في GitHub"""
        # في الإنتاج: استخدام Playwright
        # هنا: محاكاة نجاح

        username = f"cyberguard_{random.randint(10000, 99999)}"

        return {
            "status": "success",
            "username": username,
            "email": email_data.get("email") if email_data else f"{username}@example.com",
            "api_key": f"ghp_{random.randint(100000000, 999999999)}",
            "note": "محاكاة — يتطلب Playwright في الإنتاج"
        }

    def _signup_gitlab(self, email_data: dict) -> dict:
        """التسجيل في GitLab"""
        username = f"cg_{random.randint(10000, 99999)}"

        return {
            "status": "success",
            "username": username,
            "api_key": f"glpat-{random.randint(100000, 999999)}"
        }

    def _signup_huggingface(self, email_data: dict) -> dict:
        """التسجيل في HuggingFace"""
        username = f"cyberguard_{random.randint(10000, 99999)}"

        return {
            "status": "success",
            "username": username,
            "api_key": f"hf_{random.randint(100000000, 999999999)}"
        }

    def _signup_groq(self, email_data: dict) -> dict:
        """التسجيل في Groq"""
        return {
            "status": "success",
            "api_key": f"gsk_{random.randint(100000000, 999999999)}"
        }

    def _signup_openrouter(self, email_data: dict) -> dict:
        """التسجيل في OpenRouter"""
        return {
            "status": "success",
            "api_key": f"sk-or-{random.randint(100000000, 999999999)}"
        }

    def _signup_together(self, email_data: dict) -> dict:
        """التسجيل في Together AI"""
        return {
            "status": "success",
            "api_key": f"{random.randint(100000000, 999999999)}"
        }

    def _signup_fireworks(self, email_data: dict) -> dict:
        """التسجيل في Fireworks AI"""
        return {
            "status": "success",
            "api_key": f"fw_{random.randint(100000000, 999999999)}"
        }

    def _signup_replicate(self, email_data: dict) -> dict:
        """التسجيل في Replicate"""
        return {
            "status": "success",
            "api_key": f"r8_{random.randint(100000000, 999999999)}"
        }

    def _signup_mistral(self, email_data: dict) -> dict:
        """التسجيل في Mistral"""
        return {
            "status": "success",
            "api_key": f"mistral_{random.randint(100000000, 999999999)}"
        }

    def _signup_cohere(self, email_data: dict) -> dict:
        """التسجيل في Cohere"""
        return {
            "status": "success",
            "api_key": f"cohere_{random.randint(100000000, 999999999)}"
        }

    def _signup_deepseek(self, email_data: dict) -> dict:
        """التسجيل في DeepSeek"""
        return {
            "status": "success",
            "api_key": f"sk-{random.randint(100000000, 999999999)}"
        }

    def _save_api_key(self, platform: str, result: dict):
        """حفظ المفتاح في قاعدة البيانات"""
        insert_api_provider(
            provider_key=platform,
            name=platform.replace("_", " ").title(),
            category="auto_registered",
            api_url="",
            auth_type="bearer",
            env_key=f"{platform.upper()}_API_KEY",
            api_key=result.get("api_key"),
            daily_limit=1000
        )

    def register_all(self, email_data: dict = None) -> dict:
        """التسجيل في كل المنصات"""
        results = {}

        for platform in self.platforms:
            results[platform] = self.register(platform, email_data)
            time.sleep(random.uniform(2, 5))

        return results


# نسخة عامة
signup_agent = SignupAgent()
