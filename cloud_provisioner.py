"""
CYBERGUARD OS - Cloud Provisioner
Auto-creates accounts on cloud providers (respects multi-key policy).
"""
import time
import logging
from typing import Dict, Optional, Any

from config import MULTI_KEY_POLICY, CLOUD_MAX_ACCOUNTS_PER_PROVIDER
from db import get_conn, log_event, insert_api_provider

logger = logging.getLogger(__name__)


class CloudProvisioner:
    def __init__(self):
        self._vpn = None
        self._signup = None
        self._email = None

    def _get_vpn(self):
        if self._vpn is None:
            try:
                from vpn_manager import vpn_manager
                self._vpn = vpn_manager
            except Exception as e:
                logger.warning(f"[Provision] VPN not available: {e}")
                self._vpn = False
        return self._vpn or None

    def _get_signup(self):
        if self._signup is None:
            try:
                from agents.real_signup_agent import real_signup
                self._signup = real_signup
            except Exception:
                try:
                    from agents.signup_agent import signup_agent
                    self._signup = signup_agent
                except Exception as e:
                    logger.warning(f"[Provision] Signup not available: {e}")
                    self._signup = False
        return self._signup or None

    def _get_email(self):
        if self._email is None:
            try:
                from agents.real_email_agent import real_email_agent
                self._email = real_email_agent
            except Exception:
                try:
                    from agents.email_agent import email_agent
                    self._email = email_agent
                except Exception as e:
                    logger.warning(f"[Provision] Email not available: {e}")
                    self._email = False
        return self._email or None

    def provision(self, provider_name: str, country: Optional[str] = None) -> Dict[str, Any]:
        policy = MULTI_KEY_POLICY.get(provider_name, MULTI_KEY_POLICY["default"])

        if not policy.get("allows_multi"):
            return {"status": "skipped", "reason": "multi_not_allowed",
                    "provider": provider_name}

        current = self._count_accounts(provider_name)
        max_allowed = min(
            policy.get("max_accounts", 1),
            CLOUD_MAX_ACCOUNTS_PER_PROVIDER,
        )

        if current >= max_allowed:
            return {"status": "skipped", "reason": "max_reached",
                    "current": current, "max": max_allowed}

        if country:
            vpn = self._get_vpn()
            if vpn:
                try:
                    vpn.connect(country)
                    logger.info(f"[Provision] VPN -> {country}")
                except Exception as e:
                    logger.warning(f"[Provision] VPN failed: {e}")

        email = self._get_email()
        email_data = None
        if email:
            try:
                if hasattr(email, "create_mail_tm"):
                    email_data = email.create_mail_tm() or email.create_1secmail()
                elif hasattr(email, "create_email"):
                    email_data = email.create_email()
                elif hasattr(email, "generate_batch"):
                    batch = email.generate_batch(1)
                    email_data = batch[0] if batch else None
            except Exception as e:
                logger.warning(f"[Provision] Email failed: {e}")

        if not email_data:
            email_data = {"email": f"prov_{int(time.time())}@temp.local",
                          "simulated": True}

        signup = self._get_signup()
        result = {"status": "simulated", "provider": provider_name}

        if signup:
            try:
                if hasattr(signup, "signup_huggingface") and provider_name == "huggingface":
                    result = signup.signup_huggingface(email_data)
                elif hasattr(signup, "signup_openrouter") and provider_name == "openrouter":
                    result = signup.signup_openrouter(email_data)
                elif hasattr(signup, "signup_groq") and provider_name == "groq":
                    result = signup.signup_groq(email_data)
                elif hasattr(signup, "register"):
                    result = signup.register(provider_name, email_data)
                else:
                    result = {"status": "no_handler", "provider": provider_name}
            except Exception as e:
                logger.error(f"[Provision] Signup failed: {e}")
                result = {"status": "error", "error": str(e)}

        if result.get("api_key"):
            try:
                insert_api_provider(
                    provider_key=f"{provider_name}_{current + 1}",
                    name=f"{provider_name} #{current + 1}",
                    category="auto_provisioned",
                    api_url=result.get("api_url", ""),
                    auth_type="bearer",
                    env_key=f"{provider_name.upper()}_API_KEY_{current + 1}",
                    api_key=result["api_key"],
                    daily_limit=1000,
                )
                logger.info(f"[Provision] Saved key for {provider_name} #{current + 1}")
            except Exception as e:
                logger.error(f"[Provision] Save key failed: {e}")

        try:
            log_event("cloud_provision", {
                "provider": provider_name,
                "country": country,
                "status": result.get("status"),
                "account_number": current + 1,
            })
        except Exception:
            pass

        return {
            "status": result.get("status", "unknown"),
            "provider": provider_name,
            "account_number": current + 1,
            "email": email_data.get("email") if email_data else None,
            "api_key": result.get("api_key"),
        }

    def _count_accounts(self, provider_name: str) -> int:
        try:
            with get_conn() as conn:
                row = conn.execute(
                    "SELECT COUNT(*) as c FROM api_providers WHERE provider_key LIKE ?",
                    (f"{provider_name}%",)
                ).fetchone()
                return row["c"] if row else 0
        except Exception:
            return 0


cloud_provisioner = CloudProvisioner()
