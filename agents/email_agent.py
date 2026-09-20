"""
وكيل الإيميلات — إنشاء إيميلات مؤقتة تلقائياً
"""
import random
import time
import requests
from db import log_event


class EmailAgent:
    """
    إنشاء إيميلات مؤقتة من عدة خدمات:
    - temp-mail.org
    - guerrillamail.com
    - mail.tm
    - emailfake.com
    """

    def __init__(self):
        self.base_name = "cyberguard"
        self.counter = 0
        self.created_emails = []

        log_event("email_agent", {"status": "initialized"})

    def generate_batch(self, count: int = 50) -> list:
        """إنشاء دفعة إيميلات"""
        emails = []

        for i in range(count):
            try:
                email = self._create_email()
                emails.append(email)
                self.created_emails.append(email)

                # تأخير عشوائي لتجنب الحظر
                time.sleep(random.uniform(1, 3))

            except Exception as e:
                log_event("email_agent_errors", {"error": str(e)})

        log_event("email_agent", {
            "action": "batch_created",
            "count": len(emails)
        })

        return emails

    def _create_email(self) -> dict:
        """إنشاء إيميل واحد"""
        self.counter += 1

        # محاولة الخدمات بالترتيب
        services = [
            self._create_mail_tm,
            self._create_guerrilla,
            self._create_tempmail
        ]

        for service in services:
            try:
                result = service()
                if result:
                    return result
            except:
                continue

        # fallback: إيميل وهمي
        return self._create_fake()

    def _create_mail_tm(self) -> dict:
        """إنشاء إيميل من mail.tm"""
        # 1. الحصول على نطاقات متاحة
        domains_resp = requests.get("https://api.mail.tm/domains", timeout=10)
        domains = domains_resp.json()["hydra:member"]
        domain = domains[0]["domain"]

        # 2. إنشاء حساب
        username = f"{self.base_name}_{random.randint(10000, 99999)}"
        password = f"Pass{random.randint(100000, 999999)}!"

        account_resp = requests.post(
            "https://api.mail.tm/accounts",
            json={
                "address": f"{username}@{domain}",
                "password": password
            },
            timeout=10
        )

        if account_resp.status_code == 201:
            # 3. الحصول على token
            token_resp = requests.post(
                "https://api.mail.tm/token",
                json={
                    "address": f"{username}@{domain}",
                    "password": password
                },
                timeout=10
            )

            token = token_resp.json().get("token")

            return {
                "email": f"{username}@{domain}",
                "password": password,
                "token": token,
                "service": "mail.tm",
                "created_at": time.time()
            }

        return None

    def _create_guerrilla(self) -> dict:
        """إنشاء إيميل من guerrillamail"""
        session = requests.Session()

        # إنشاء جلسة
        resp = session.get("https://www.guerrillamail.com/ajax.php?f=get_email_address", timeout=10)
        data = resp.json()

        return {
            "email": data.get("email_addr"),
            "sid_token": data.get("sid_token"),
            "service": "guerrillamail",
            "created_at": time.time()
        }

    def _create_tempmail(self) -> dict:
        """إنشاء إيميل من temp-mail"""
        resp = requests.post(
            "https://api.temp-mail.org/request/mail/id/",
            data={"locale": "en"},
            timeout=10
        )

        if resp.status_code == 200:
            data = resp.json()
            return {
                "email": data.get("mail"),
                "id": data.get("id"),
                "service": "tempmail",
                "created_at": time.time()
            }

        return None

    def _create_fake(self) -> dict:
        """إيميل وهمي كـ fallback"""
        domains = ["example.com", "test.com", "mail.com"]
        username = f"{self.base_name}_{self.counter:05d}"

        return {
            "email": f"{username}@{random.choice(domains)}",
            "password": f"Fake{random.randint(100000, 999999)}",
            "service": "fake",
            "created_at": time.time()
        }

    def check_inbox(self, email_data: dict) -> list:
        """فحص صندوق الوارد"""
        service = email_data.get("service")

        if service == "mail.tm":
            return self._check_mail_tm(email_data)
        elif service == "guerrillamail":
            return self._check_guerrilla(email_data)

        return []

    def _check_mail_tm(self, email_data: dict) -> list:
        """فحص mail.tm"""
        headers = {"Authorization": f"Bearer {email_data['token']}"}

        resp = requests.get(
            "https://api.mail.tm/messages",
            headers=headers,
            timeout=10
        )

        if resp.status_code == 200:
            messages = resp.json()["hydra:member"]
            return [
                {
                    "id": msg["id"],
                    "from": msg["from"]["address"],
                    "subject": msg["subject"],
                    "intro": msg["intro"]
                }
                for msg in messages
            ]

        return []

    def _check_guerrilla(self, email_data: dict) -> list:
        """فحص guerrillamail"""
        resp = requests.get(
            f"https://www.guerrillamail.com/ajax.php?f=check_email&sid_token={email_data['sid_token']}",
            timeout=10
        )

        if resp.status_code == 200:
            data = resp.json()
            return data.get("list", [])

        return []

    def get_stats(self) -> dict:
        """إحصائيات"""
        return {
            "total_created": len(self.created_emails),
            "by_service": {}
        }


# نسخة عامة
email_agent = EmailAgent()
