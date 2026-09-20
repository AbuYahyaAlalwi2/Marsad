"""Manual account onboarding records.

The application never creates accounts, submits registration forms, bypasses
CAPTCHA/MFA, or reads disposable mail. The operator registers each account on
the official website and stores only a local reference plus optional token in
secret environment variables.
"""
import json
import os
from pathlib import Path
from typing import Dict

from manual_provider_registry import provider_status

BASE_DIR = Path(__file__).resolve().parent
ONBOARDING_FILE = Path(os.getenv("MARSAD_ONBOARDING_FILE", BASE_DIR / "data" / "manual_accounts.json"))


def load_accounts() -> Dict[str, dict]:
    if not ONBOARDING_FILE.exists():
        return {}
    try:
        data = json.loads(ONBOARDING_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_account(provider: str, email: str, account_url: str = "", notes: str = "") -> dict:
    """Record an account created by the operator; never create or verify it."""
    if not provider or not email or "@" not in email:
        return {"status": "error", "reason": "provider_and_real_email_required"}
    accounts = load_accounts()
    accounts[provider] = {
        "provider": provider,
        "email": email,
        "account_url": account_url,
        "notes": notes,
        "registration": "operator_completed",
        "credential_status": provider_status(provider),
    }
    ONBOARDING_FILE.parent.mkdir(parents=True, exist_ok=True)
    ONBOARDING_FILE.write_text(json.dumps(accounts, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "recorded", "provider": provider, "email": email}


def onboarding_status() -> dict:
    accounts = load_accounts()
    return {
        provider: {**record, "credential_status": provider_status(provider)}
        for provider, record in accounts.items()
    }
