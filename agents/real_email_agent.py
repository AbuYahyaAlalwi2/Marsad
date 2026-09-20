"""User-owned email adapter. No mailbox creation is performed."""
import os
from typing import Optional


class EmailAgent:
    def __init__(self):
        self.created_emails = []

    def generate_batch(self, count: int = 1) -> list:
        email = os.environ.get("MARSAD_OWNER_EMAIL", "").strip()
        if not email or "@" not in email:
            return []
        result = [{"email": email, "service": "operator_configured", "real": True}]
        self.created_emails.extend(result)
        return result

    def create_mail_tm(self):
        return None

    def create_1secmail(self):
        return None

    def wait_for_mail(self, email_data: dict, timeout: int = 120, keywords=None):
        return {"status": "manual_required", "message": "افتح البريد الحقيقي وأكمل التحقق يدويًا."}

    def get_latest(self) -> Optional[dict]:
        return self.created_emails[-1] if self.created_emails else None

    def get_stats(self):
        return {"total_configured": len(self.created_emails)}


email_agent = EmailAgent()
