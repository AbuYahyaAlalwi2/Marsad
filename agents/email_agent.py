"""Email integration using user-owned mail only.

This module deliberately does not create disposable mailboxes or fallback fake
addresses for account registration. Provider registration must use a mailbox and
credentials controlled by the operator, with the provider's official OAuth/API
flow.
"""
import os
import time
from collections import Counter
from typing import Optional

import requests
from db import log_event


class EmailAgent:
    def __init__(self):
        self.created_emails = []
        self.service_url = os.environ.get("MARSAD_MAIL_API_URL", "").strip()
        log_event("email_agent", {"status": "initialized", "mode": "user_owned_mail_only"})

    def generate_batch(self, count: int = 1) -> list:
        """Return configured operator-owned mail identities, never fake mail."""
        configured = os.environ.get("MARSAD_OWNER_EMAIL", "").strip()
        if not configured:
            log_event("email_agent", {"action": "skipped", "reason": "MARSAD_OWNER_EMAIL_missing"})
            return []
        result = [{"email": configured, "service": "operator_configured", "real": True}]
        self.created_emails.extend(result)
        return result

    def create_mail_tm(self):
        return None

    def create_1secmail(self):
        return None

    def wait_for_mail(self, email_data: dict, timeout: int = 120, keywords=None):
        if not self.service_url:
            return {"status": "not_configured", "message": "Configure an operator-owned mail API."}
        try:
            response = requests.get(self.service_url, timeout=min(timeout, 30))
            response.raise_for_status()
            return {"status": "connected", "data": response.json()}
        except Exception as exc:
            log_event("email_error", {"error": str(exc)})
            return {"status": "error", "error": str(exc)}

    def get_latest(self) -> Optional[dict]:
        return self.created_emails[-1] if self.created_emails else None

    def get_stats(self) -> dict:
        return {
            "total_created": len(self.created_emails),
            "by_service": dict(Counter(e.get("service", "unknown") for e in self.created_emails)),
        }


email_agent = EmailAgent()
