"""
مزودي LLM — توليد النصوص الذكية عبر API
"""
import os
import requests
import time
from config import API_PROVIDERS
from db import (
    insert_api_provider, get_api_provider, get_available_provider,
    mark_provider_used, log_event
)


class LLMProviderManager:
    """
    إدارة مزودي LLM — تدعم جميع مزودي API المجانيين
    """

    def __init__(self):
        self._load_providers_from_config()

    def _load_providers_from_config(self):
        """تحميل مزودي API من الإعدادات"""
        for key, config in API_PROVIDERS.items():
            if config["category"] == "llm":
                api_key = os.environ.get(config["env_key"], "")
                insert_api_provider(
                    provider_key=key,
                    name=config["name"],
                    category=config["category"],
                    api_url=config["api_url"],
                    auth_type=config["auth_type"],
                    env_key=config["env_key"],
                    api_key=api_key,
                    daily_limit=1000 if config["free_tier"] else 100
                )

    def generate(self, prompt: str, model: str = None, max_tokens: int = 2000, temperature: float = 0.7) -> dict:
        """توليد نص باستخدام أفضل مزوّد متاح"""
        provider = get_available_provider(category="llm")

        if not provider:
            log_event("llm_providers", {"error": "no_available_provider"})
            return {"status": "error", "reason": "لا يوجد مزوّد LLM متاح"}

        # اختيار النموذج
        if not model:
            config = API_PROVIDERS.get(provider["provider_key"], {})
            models = config.get("models", [])
            model = models[0] if models else "default"

        try:
            result = self._call_provider(provider, prompt, model, max_tokens, temperature)
            mark_provider_used(provider["provider_key"])

            log_event("llm_providers", {
                "provider": provider["provider_key"],
                "model": model,
                "status": "success"
            })

            return result

        except Exception as e:
            log_event("llm_providers", {
                "provider": provider["provider_key"],
                "error": str(e)
            })
            # محاولة مع مزوّد آخر
            return self._retry_with_fallback(provider, prompt, model, max_tokens, temperature)

    def _retry_with_fallback(self, failed_provider: dict, prompt: str, model: str, max_tokens: int, temperature: float) -> dict:
        """محاولة مع مزوّد بديل"""
        providers = get_available_provider(category="llm")
        for provider in providers:
            if provider["provider_key"] != failed_provider["provider_key"]:
                try:
                    result = self._call_provider(provider, prompt, model, max_tokens, temperature)
                    mark_provider_used(provider["provider_key"])
                    return result
                except:
                    continue
        return {"status": "error", "reason": "فشل جميع مزودي LLM"}

    def _call_provider(self, provider: dict, prompt: str, model: str, max_tokens: int, temperature: float) -> dict:
        """استدعاء مزوّد معين"""
        api_key = provider["api_key"] or os.environ.get(provider["env_key"], "")
        api_url = provider["api_url"]
        auth_type = provider["auth_type"]
        provider_key = provider["provider_key"]

        headers = self._get_headers(auth_type, api_key)

        # استدعاء حسب نوع المزوّد
        if provider_key == "google_gemini":
            return self._call_gemini(api_key, prompt, model, max_tokens, temperature)
        elif provider_key == "huggingface":
            return self._call_huggingface(api_url, headers, prompt, model)
        elif provider_key == "anthropic":
            return self._call_anthropic(api_url, headers, prompt, model, max_tokens)
        elif provider_key == "perplexity":
            return self._call_perplexity(api_url, headers, prompt, model, max_tokens)
        elif provider_key == "text_embedding_ada_002":
            return self._call_openai_embeddings(api_url, headers, prompt, model)
        else:
            # معظم مزودي API متوافقون مع OpenAI
            return self._call_openai_compatible(api_url, headers, prompt, model, max_tokens, temperature)

    def _get_headers(self, auth_type: str, api_key: str) -> dict:
        """إعداد رأس التصريح"""
        headers = {"Content-Type": "application/json"}
        if auth_type == "bearer":
            headers["Authorization"] = f"Bearer {api_key}"
        elif auth_type == "api_key":
            headers["x-goog-api-key"] = api_key
        elif auth_type == "token":
            headers["Authorization"] = f"Token {api_key}"
        return headers

    def _call_gemini(self, api_key: str, prompt: str, model: str, max_tokens: int, temperature: float) -> dict:
        """استدعاء Google Gemini"""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        response = requests.post(
            url,
            params={"key": api_key},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "maxOutputTokens": max_tokens,
                    "temperature": temperature
                }
            },
            timeout=60
        )
        if response.status_code == 200:
            data = response.json()
            text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            return {"status": "success", "text": text, "provider": "gemini", "model": model}
        else:
            raise Exception(f"Gemini error: {response.status_code} - {response.text}")

    def _call_openai_compatible(self, api_url: str, headers: dict, prompt: str, model: str, max_tokens: int, temperature: float) -> dict:
        """استدعاء مزودي API المتوافقين مع OpenAI (Groq, OpenRouter, Together, etc.)"""
        response = requests.post(
            f"{api_url}/chat/completions",
            headers=headers,
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": temperature
            },
            timeout=60
        )
        if response.status_code == 200:
            data = response.json()
            text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return {"status": "success", "text": text, "provider": "openai_compatible", "model": model}
        else:
            raise Exception(f"API error: {response.status_code} - {response.text}")

    def _call_huggingface(self, api_url: str, headers: dict, prompt: str, model: str) -> dict:
        """استدعاء HuggingFace Inference API"""
        response = requests.post(
            f"{api_url}/models/{model}",
            headers=headers,
            json={"inputs": prompt},
            timeout=60
        )
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                text = data[0].get("generated_text", "")
            else:
                text = str(data)
            return {"status": "success", "text": text, "provider": "huggingface", "model": model}
        else:
            raise Exception(f"HF error: {response.status_code} - {response.text}")

    def _call_anthropic(self, api_url: str, headers: dict, prompt: str, model: str, max_tokens: int) -> dict:
        """استدعاء Anthropic Claude"""
        response = requests.post(
            f"{api_url}/v1/messages",
            headers={**headers, "x-api-key": headers.get("Authorization", "").replace("Bearer ", "")},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens
            },
            timeout=60
        )
        if response.status_code == 200:
            data = response.json()
            text = data.get("content", [{}])[0].get("text", "")
            return {"status": "success", "text": text, "provider": "anthropic", "model": model}
        else:
            raise Exception(f"Anthropic error: {response.status_code}")

    def _call_perplexity(self, api_url: str, headers: dict, prompt: str, model: str, max_tokens: int) -> dict:
        """استدعاء Perplexity AI"""
        response = requests.post(
            f"{api_url}/chat/completions",
            headers=headers,
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens
            },
            timeout=60
        )
        if response.status_code == 200:
            data = response.json()
            text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return {"status": "success", "text": text, "provider": "perplexity", "model": model}
        else:
            raise Exception(f"Perplexity error: {response.status_code}")

    def _call_openai_embeddings(self, api_url: str, headers: dict, text: str, model: str) -> dict:
        """استدعاء OpenAI Embeddings"""
        response = requests.post(
            f"{api_url}/embeddings",
            headers=headers,
            json={"model": model, "input": text},
            timeout=60
        )
        if response.status_code == 200:
            data = response.json()
            return {"status": "success", "embedding": data.get("data", [{}])[0].get("embedding", []), "provider": "openai"}
        else:
            raise Exception(f"Embedding error: {response.status_code}")

    def list_available_providers(self) -> list:
        """قائمة جميع مزودي LLM المتاحين"""
        from db import list_providers
        return list_providers(category="llm")

    def get_provider_stats(self) -> dict:
        """إحصائيات مزودي LLM"""
        from db import list_providers
        providers = list_providers(category="llm")
        return {
            "total_providers": len(providers),
            "active_providers": len([p for p in providers if p["status"] == "active"]),
            "providers": providers
        }


# إنشاء مثيل عالمي
llm_providers = LLMProviderManager()
