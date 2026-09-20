"""Manual-only provider registry.

This module is intentionally conservative: the project never creates accounts,
email aliases, or fake credentials. Providers are enabled only when the operator
provides real credentials manually and they pass a health check.
"""

import os
from typing import Dict, List

FREE_ONLY = True
ALLOW_AUTOMATED_SIGNUP = False
MANUAL_ONLY = True
REQUIRE_OPERATOR_CREDENTIALS = True

MANUAL_PROVIDER_REGISTRY: Dict[str, dict] = {
    "huggingface": {
        "name": "Hugging Face",
        "category": "llm",
        "requires_manual_setup": True,
        "free": True,
        "env_keys": ["HF_TOKEN"],
        "status": "disabled",
    },
    "github": {
        "name": "GitHub",
        "category": "code",
        "requires_manual_setup": True,
        "free": True,
        "env_keys": ["GITHUB_TOKEN"],
        "status": "disabled",
    },
    "gitlab": {
        "name": "GitLab",
        "category": "code",
        "requires_manual_setup": True,
        "free": True,
        "env_keys": ["GITLAB_TOKEN"],
        "status": "disabled",
    },
    "groq": {
        "name": "Groq",
        "category": "llm",
        "requires_manual_setup": True,
        "free": True,
        "env_keys": ["GROQ_API_KEY"],
        "status": "disabled",
    },
    "openrouter": {
        "name": "OpenRouter",
        "category": "llm",
        "requires_manual_setup": True,
        "free": True,
        "env_keys": ["OPENROUTER_API_KEY"],
        "status": "disabled",
    },
    "deepseek": {
        "name": "DeepSeek",
        "category": "llm",
        "requires_manual_setup": True,
        "free": True,
        "env_keys": ["DEEPSEEK_API_KEY"],
        "status": "disabled",
    },
    "mistral": {
        "name": "Mistral",
        "category": "llm",
        "requires_manual_setup": True,
        "free": True,
        "env_keys": ["MISTRAL_API_KEY"],
        "status": "disabled",
    },
    "cohere": {
        "name": "Cohere",
        "category": "llm",
        "requires_manual_setup": True,
        "free": True,
        "env_keys": ["COHERE_API_KEY"],
        "status": "disabled",
    },
    "cerebras": {
        "name": "Cerebras",
        "category": "llm",
        "requires_manual_setup": True,
        "free": True,
        "env_keys": ["CEREBRAS_API_KEY"],
        "status": "disabled",
    },
    "cloudflare": {
        "name": "Cloudflare Workers AI",
        "category": "llm",
        "requires_manual_setup": True,
        "free": True,
        "env_keys": ["CLOUDFLARE_API_TOKEN"],
        "status": "disabled",
    },
    "sourcegraph": {
        "name": "Sourcegraph",
        "category": "code",
        "requires_manual_setup": True,
        "free": True,
        "env_keys": ["SOURCEGRAPH_TOKEN"],
        "status": "disabled",
    },
    "kaggle": {
        "name": "Kaggle",
        "category": "dataset",
        "requires_manual_setup": True,
        "free": True,
        "env_keys": ["KAGGLE_USERNAME", "KAGGLE_KEY"],
        "status": "disabled",
    },
    "arxiv": {
        "name": "arXiv",
        "category": "research",
        "requires_manual_setup": False,
        "free": True,
        "env_keys": [],
        "status": "public_read_only",
    },
}

PAID_OR_BILLING_PROVIDERS = {
    "aws",
    "gcp",
    "azure",
    "oracle",
    "render",
    "railway",
    "fly",
    "replicate",
    "baseten",
    "perplexity",
    "fireworks",
    "together",
}


def _env_value(key: str) -> str:
    return os.environ.get(key, "").strip()


def provider_status(name: str) -> dict:
    """Return only a real status. Never invent success."""
    provider = MANUAL_PROVIDER_REGISTRY.get(name)
    if not provider:
        return {"name": name, "status": "unsupported"}

    missing = [k for k in provider.get("env_keys", []) if not _env_value(k)]
    if missing:
        return {
            "name": name,
            "status": "missing_credentials",
            "required_env": provider.get("env_keys", []),
            "missing": missing,
        }

    if name in PAID_OR_BILLING_PROVIDERS:
        return {"name": name, "status": "billing_required"}

    if provider.get("requires_manual_setup"):
        return {"name": name, "status": "manual_ready"}

    return {"name": name, "status": "public_read_only"}


def active_manual_providers() -> List[str]:
    return [
        name
        for name, provider in MANUAL_PROVIDER_REGISTRY.items()
        if provider.get("status") == "disabled" and not any(_env_value(k) == "" for k in provider.get("env_keys", []))
    ]


def list_supported_providers() -> List[str]:
    return sorted(MANUAL_PROVIDER_REGISTRY.keys())


__all__ = [
    "MANUAL_PROVIDER_REGISTRY",
    "FREE_ONLY",
    "ALLOW_AUTOMATED_SIGNUP",
    "MANUAL_ONLY",
    "REQUIRE_OPERATOR_CREDENTIALS",
    "PAID_OR_BILLING_PROVIDERS",
    "provider_status",
    "active_manual_providers",
    "list_supported_providers",
]
