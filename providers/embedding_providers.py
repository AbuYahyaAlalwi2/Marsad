"""
مزودو Embeddings — للذاكرة المتجهة
"""
import os
import requests
from config import API_PROVIDERS
from db import (
    insert_api_provider, get_available_provider, mark_provider_used, log_event
)


class EmbeddingProviderManager:
    """
    إدارة مزودي Embeddings — للبحث الدلالي
    """

    def __init__(self):
        self._load_embedding_providers()

    def _load_embedding_providers(self):
        """تحميل مزودي Embeddings"""
        for key, config in API_PROVIDERS.items():
            if config["category"] == "embedding":
                api_key = os.environ.get(config["env_key"], "")
                insert_api_provider(
                    provider_key=key,
                    name=config["name"],
                    category=config["category"],
                    api_url=config["api_url"],
                    auth_type=config["auth_type"],
                    env_key=config["env_key"],
                    api_key=api_key,
                    daily_limit=5000
                )

    def embed(self, text: str, model: str = None) -> dict:
        """
        توليد embedding — يختار المزود المتاح
        """
        provider = get_available_provider(category="embedding")

        if not provider:
            # fallback: embedding محلي بسيط
            return self._local_embed(text)

        try:
            result = self._call_embedding_provider(provider, text, model)
            mark_provider_used(provider["provider_key"])
            return result
        except Exception as e:
            log_event("embedding_providers", {"error": str(e)})
            return self._local_embed(text)

    def _call_embedding_provider(self, provider: dict, text: str, model: str = None) -> dict:
        """استدعاء مزود embedding"""
        api_key = provider["api_key"] or os.environ.get(provider["env_key"], "")
        api_url = provider["api_url"]
        provider_key = provider["provider_key"]

        if not model:
            config = API_PROVIDERS.get(provider_key, {})
            models = config.get("models", [])
            model = models[0] if models else "default"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        if provider_key == "cohere_embed":
            response = requests.post(
                f"{api_url}/embed",
                headers=headers,
                json={"texts": [text], "model": model, "input_type": "search_document"},
                timeout=30
            )
        elif provider_key == "jina":
            response = requests.post(
                f"{api_url}/embeddings",
                headers=headers,
                json={"input": [text], "model": model},
                timeout=30
            )
        else:
            # OpenAI-compatible
            response = requests.post(
                f"{api_url}/embeddings",
                headers=headers,
                json={"input": text, "model": model},
                timeout=30
            )

        if response.status_code == 200:
            data = response.json()
            # استخراج embedding حسب تنسيق المزود
            if "embeddings" in data:
                embedding = data["embeddings"][0]
            elif "data" in data:
                embedding = data["data"][0].get("embedding", [])
            else:
                embedding = data

            return {"status": "success", "embedding": embedding, "provider": provider_key}
        else:
            raise Exception(f"Embedding error: {response.status_code}")

    def _local_embed(self, text: str) -> dict:
        """Embedding محلي بسيط (fallback)"""
        # hashing بسيط كـ fallback
        import hashlib

        # تقسيم النص لكلمات
        words = text.lower().split()

        # إنشاء vector بسيط (256-dimensional)
        vector = [0.0] * 256
        for word in words:
            hash_val = int(hashlib.md5(word.encode()).hexdigest(), 16)
            idx = hash_val % 256
            vector[idx] += 1.0

        # تطبيع
        magnitude = sum(x**2 for x in vector) ** 0.5
        if magnitude > 0:
            vector = [x / magnitude for x in vector]

        return {"status": "success", "embedding": vector, "provider": "local"}


# نسخة عامة
embedding_providers = EmbeddingProviderManager()
