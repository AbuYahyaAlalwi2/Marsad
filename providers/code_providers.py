"""
مزودي الكود — توليد وإصلاح وتحسين الكود عبر API
"""
import os
import requests
from config import API_PROVIDERS
from db import (
    insert_api_provider, get_available_provider, mark_provider_used, log_event
)


class CodeProviderManager:
    """
    إدارة مزودي الكود — Codestral, DeepSeek Coder, etc.
    """

    def __init__(self):
        self._load_code_providers()

    def _load_code_providers(self):
        """تحميل مزودي API الخاصين بالكود"""
        for key, config in API_PROVIDERS.items():
            if config["category"] == "code":
                api_key = os.environ.get(config["env_key"], "")
                insert_api_provider(
                    provider_key=key,
                    name=config["name"],
                    category=config["category"],
                    api_url=config["api_url"],
                    auth_type=config["auth_type"],
                    env_key=config["env_key"],
                    api_key=api_key,
                    daily_limit=2000 if config["free_tier"] else 500
                )

    def generate_code(self, prompt: str, language: str = "python", max_tokens: int = 4000) -> dict:
        """توليد كود باستخدام أفضل مزوّد متاح"""
        provider = get_available_provider(category="code")

        if not provider:
            # استخدام LLM كبديل
            from providers.llm_providers import llm_providers
            enhanced_prompt = f"Generate {language} code:\n\n{prompt}"
            return llm_providers.generate(enhanced_prompt, max_tokens=max_tokens)

        try:
            result = self._call_code_provider(provider, prompt, language, max_tokens)
            mark_provider_used(provider["provider_key"])

            log_event("code_providers", {
                "provider": provider["provider_key"],
                "language": language,
                "status": "success"
            })

            return result

        except Exception as e:
            log_event("code_providers", {"error": str(e)})
            # استخدام LLM كبديل
            from providers.llm_providers import llm_providers
            return llm_providers.generate(f"Generate {language} code:\n\n{prompt}", max_tokens=max_tokens)

    def fix_code(self, code: str, error: str = None, language: str = "auto") -> dict:
        """إصلاح الكود"""
        prompt = f"Fix this {language} code:\n\n```\n{code}\n```"
        if error:
            prompt += f"\n\nError:\n{error}"
        return self.generate_code(prompt, language=language)

    def explain_code(self, code: str, language: str = "auto") -> dict:
        """شرح الكود"""
        prompt = f"Explain this {language} code in detail:\n\n```\n{code}\n```"
        return self.generate_code(prompt, language=language)

    def optimize_code(self, code: str, language: str = "auto") -> dict:
        """تحسين الكود للأداء"""
        prompt = f"Optimize this {language} code for performance:\n\n```\n{code}\n```"
        return self.generate_code(prompt, language=language)

    def analyze_code(self, code: str, language: str = "auto") -> dict:
        """تحليل الكود (الأخطاء، التحسينات، الأمان)"""
        prompt = f"Analyze this {language} code for errors, improvements, and security issues:\n\n```\n{code}\n```"
        return self.generate_code(prompt, language=language)

    def _call_code_provider(self, provider: dict, prompt: str, language: str, max_tokens: int) -> dict:
        """استدعاء مزوّد كود معين"""
        api_key = provider["api_key"] or os.environ.get(provider["env_key"], "")
        api_url = provider["api_url"]
        provider_key = provider["provider_key"]

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        # اختيار النموذج حسب المزوّد
        if provider_key == "codestral":
            model = "codestral-latest"
        elif provider_key == "deepseek_code":
            model = "deepseek-coder"
        else:
            config = API_PROVIDERS.get(provider_key, {})
            models = config.get("models", [])
            model = models[0] if models else "default"

        # معظم مزودي الكود متوافقون مع OpenAI API
        response = requests.post(
            f"{api_url}/chat/completions",
            headers=headers,
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": f"You are an expert {language} programmer. Respond only with valid {language} code."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": max_tokens,
                "temperature": 0.3
            },
            timeout=60
        )

        if response.status_code == 200:
            data = response.json()
            text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return {"status": "success", "code": text, "provider": provider_key, "model": model, "language": language}
        else:
            raise Exception(f"Code provider error: {response.status_code} - {response.text}")

    def list_available_providers(self) -> list:
        """قائمة جميع مزودي الكود المتاحين"""
        from db import list_providers
        return list_providers(category="code")

    def get_provider_stats(self) -> dict:
        """إحصائيات مزودي الكود"""
        from db import list_providers
        providers = list_providers(category="code")
        return {
            "total_providers": len(providers),
            "active_providers": len([p for p in providers if p["status"] == "active"]),
            "providers": providers
        }


# إنشاء مثيل عالمي
code_providers = CodeProviderManager()
