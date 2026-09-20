"""
وكيل الإيميل الحقيقي — mail.tm + 1secmail
"""
import requests
import random
import time
import re
from db import log_event

class RealEmailAgent:
    def __init__(self):
        self.created_emails = []
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })

    def create_mail_tm(self):
        try:
            resp = self.session.get("https://api.mail.tm/domains", timeout=20)
            domains = resp.json().get("hydra:member", [])
            if not domains:
                return None
            domain = domains[0]["domain"]
            username = f"cg_{random.randint(10000,99999)}_{int(time.time())%100000}"
            password = f"Cg{random.randint(100000,999999)}!X{random.randint(10,99)}"
            address = f"{username}@{domain}"
            resp = self.session.post(
                "https://api.mail.tm/accounts",
                json={"address": address, "password": password},
                timeout=20
            )
            if resp.status_code not in (200, 201):
                return None
            token_resp = self.session.post(
                "https://api.mail.tm/token",
                json={"address": address, "password": password},
                timeout=20
            )
            token = token_resp.json().get("token")
            data = {
                "email": address,
                "password": password,
                "token": token,
                "service": "mail.tm",
                "real": True,
                "created_at": time.time()
            }
            self.created_emails.append(data)
            log_event("email", {"action": "created", "email": address, "service": "mail.tm"})
            return data
        except Exception as e:
            log_event("email_error", {"service": "mail.tm", "error": str(e)})
            return None

    def create_1secmail(self):
        try:
            resp = self.session.get(
                "https://www.1secmail.com/api/v1/?action=genRandomMailbox&count=1",
                timeout=15
            )
            emails = resp.json()
            if not emails:
                return None
            address = emails[0]
            login, domain = address.split("@")
            data = {
                "email": address,
                "login": login,
                "domain": domain,
                "service": "1secmail",
                "real": True,
                "created_at": time.time()
            }
            self.created_emails.append(data)
            log_event("email", {"action": "created", "email": address, "service": "1secmail"})
            return data
        except Exception as e:
            log_event("email_error", {"service": "1secmail", "error": str(e)})
            return None

    def wait_for_mail(self, email_data: dict, timeout: int = 120, keywords=None):
        keywords = keywords or ["verify", "confirm", "activation", "code", "otp", "token"]
        start = time.time()
        service = email_data.get("service")
        while time.time() - start < timeout:
            try:
                if service == "mail.tm" and email_data.get("token"):
                    headers = {"Authorization": f"Bearer {email_data['token']}"}
                    resp = self.session.get("https://api.mail.tm/messages", headers=headers, timeout=15)
                    msgs = resp.json().get("hydra:member", [])
                    for m in msgs:
                        mid = m["id"]
                        detail = self.session.get(f"https://api.mail.tm/messages/{mid}", headers=headers, timeout=15).json()
                        text = (detail.get("text") or "") + (detail.get("html") or "")
                        if any(k.lower() in text.lower() for k in keywords):
                            return {"status": "found", "body": text, "subject": detail.get("subject")}
                elif service == "1secmail":
                    login = email_data["login"]
                    domain = email_data["domain"]
                    resp = self.session.get(
                        f"https://www.1secmail.com/api/v1/?action=getMessages&login={login}&domain={domain}",
                        timeout=15
                    )
                    msgs = resp.json()
                    for m in msgs:
                        mid = m["id"]
                        detail = self.session.get(
                            f"https://www.1secmail.com/api/v1/?action=readMessage&login={login}&domain={domain}&id={mid}",
                            timeout=15
                        ).json()
                        text = (detail.get("textBody") or "") + (detail.get("htmlBody") or "")
                        if any(k.lower() in text.lower() for k in keywords):
                            return {"status": "found", "body": text, "subject": detail.get("subject")}
            except Exception as e:
                log_event("email_poll_error", {"error": str(e)})
            time.sleep(5)
        return {"status": "timeout"}

    def extract_link(self, body: str):
        links = re.findall(r'https?://[^\s<>"\']+', body)
        for link in links:
            if any(x in link.lower() for x in ["verify", "confirm", "activate", "token", "code"]):
                return link
        return links[0] if links else None

    def extract_otp(self, body: str):
        m = re.search(r'\b(\d{4,8})\b', body)
        return m.group(1) if m else None

    def generate_batch(self, count=20):
        emails = []
        for _ in range(count):
            e = self.create_mail_tm() or self.create_1secmail()
            if e:
                emails.append(e)
            time.sleep(1.5)
        return emails

    def get_latest(self):
        return self.created_emails[-1] if self.created_emails else None

real_email_agent = RealEmailAgent()
