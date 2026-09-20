"""Real API validation only.

This module does not create fake provider keys. It checks whether a real key is
provided in the environment and, when possible, validates it against the real
provider endpoint.
"""
import os
import time

import requests


class APIAgent:
    """Validate real API credentials and expose them in a safe way."""

    def __init__(self):
        self.platforms = {
            "google_gemini": "GOOGLE_API_KEY",
            "groq": "GROQ_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
            "huggingface": "HF_TOKEN",
            "cohere": "COHERE_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
            "together": "TOGETHER_API_KEY",
            "fireworks": "FIREWORKS_API_KEY",
            "replicate": "REPLICATE_API_TOKEN",
            "mistral": "MISTRAL_API_KEY",
            "nvidia_nim": "NVIDIA_API_KEY",
            "sambanova": "SAMBANOVA_API_KEY",
            "ai21": "AI21_API_KEY",
            "baseten": "BASETEN_API_KEY",
            "modal": "MODAL_API_KEY",
            "cloudflare_workers_ai": "CLOUDFLARE_API_TOKEN",
        }

    def _validate_platform(self, platform: str, token: str) -> dict:
        if not token:
            return {"status": "missing_credentials", "provider": platform}

        try:
            endpoints = {
                "google_gemini": "https://generativelanguage.googleapis.com/v1beta/models?key={token}",
                "groq": "https://api.groq.com/openai/v1/models",
                "openrouter": "https://openrouter.ai/api/v1/models",
                "huggingface": "https://huggingface.co/api/whoami",
                "cohere": "https://api.cohere.ai/v1/models",
                "deepseek": "https://api.deepseek.com/models",
                "mistral": "https://api.mistral.ai/v1/models",
            }
            url = endpoints.get(platform)
            headers = {}
            if platform in {"google_gemini"}:
                headers = {"Content-Type": "application/json"}
                resp = requests.get(url.format(token=token), headers=headers, timeout=15)
            elif platform == "huggingface":
                headers = {"Authorization": f"Bearer {token}"}
                resp = requests.get(url, headers=headers, timeout=15)
            elif platform == "openrouter":
                headers = {"Authorization": f"Bearer {token}"}
                resp = requests.get(url, headers=headers, timeout=15)
            elif platform in {"groq", "cohere", "deepseek", "mistral"}:
                headers = {"Authorization": f"Bearer {token}"}
                resp = requests.get(url, headers=headers, timeout=15)
            else:
                return {"status": "configured", "provider": platform}

            if resp.status_code in (200, 201, 202):
                return {"status": "connected", "provider": platform, "code": resp.status_code}
            return {"status": "invalid_credentials", "provider": platform, "code": resp.status_code}
        except Exception as exc:
            return {"status": "error", "provider": platform, "error": str(exc)}

    def register(self, platform: str) -> dict:
        env_key = self.platforms.get(platform)
        if not env_key:
            return {"status": "unsupported", "provider": platform}

        token = os.environ.get(env_key, "").strip()
        if not token:
            return {"status": "missing_credentials", "provider": platform, "env_key": env_key}

        return self._validate_platform(platform, token)

    def register_all(self) -> dict:
        results = {}
        for platform in self.platforms:
            results[platform] = self.register(platform)
            time.sleep(0.2)
        return results

    def get_all_keys(self) -> dict:
        return {
            platform: {
                "status": "configured" if os.environ.get(env_key, "").strip() else "missing_credentials",
                "env_key": env_key,
            }
            for platform, env_key in self.platforms.items()
        }


api_agent = APIAgent()
