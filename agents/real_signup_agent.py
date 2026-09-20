"""
وكيل التسجيل الحقيقي — Playwright + إيميل حقيقي
"""
import time
import random
import json
from db import log_event, insert_api_provider
from secure_vault import secure_vault

try:
    from playwright.sync_api import sync_playwright
    HAS_PW = True
except ImportError:
    HAS_PW = False

from agents.real_email_agent import real_email_agent

class RealSignupAgent:
    def __init__(self, headless=True):
        self.headless = headless
        self.results = {}

    def _launch(self):
        if not HAS_PW:
            return None, None, None
        pw = sync_playwright().start()
        browser = pw.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ]
        )
        ctx = browser.new_context(
            viewport={"width": 1366, "height": 768},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="en-US",
        )
        page = ctx.new_page()
        return pw, browser, page

    def signup_huggingface(self, email_data=None):
        if not email_data:
            email_data = real_email_agent.create_mail_tm() or real_email_agent.create_1secmail()
        if not email_data:
            return {"status": "error", "reason": "no_email"}
        if not HAS_PW:
            return {"status": "error", "reason": "playwright_missing"}
        pw, browser, page = self._launch()
        try:
            page.goto("https://huggingface.co/join", wait_until="domcontentloaded", timeout=60000)
            time.sleep(2)
            page.fill('input[name="email"]', email_data["email"])
            page.fill('input[name="password"]', email_data.get("password", "CgPass123!X"))
            page.fill('input[name="username"]', f"cg{random.randint(10000,99999)}")
            page.click('button[type="submit"]')
            time.sleep(5)
            # انتظار بريد التفعيل
            mail = real_email_agent.wait_for_mail(email_data, timeout=90)
            if mail.get("status") == "found":
                link = real_email_agent.extract_link(mail["body"])
                if link:
                    page.goto(link, timeout=60000)
                    time.sleep(3)
            # محاولة استخراج token من settings (بعد تسجيل الدخول)
            page.goto("https://huggingface.co/settings/tokens", timeout=60000)
            time.sleep(3)
            # لو ظهر زر create
            try:
                page.click('text=New token', timeout=5000)
                page.fill('input[name="name"]', f"cg_{int(time.time())}")
                page.click('button:has-text("Generate")')
                time.sleep(2)
                token_el = page.query_selector('code, input[readonly], .token')
                token = token_el.inner_text() if token_el else None
            except Exception:
                token = None
            result = {
                "status": "success" if token else "partial",
                "platform": "huggingface",
                "email": email_data["email"],
                "api_key": token,
                "real": True
            }
            if token:
                insert_api_provider(
                    provider_key="huggingface",
                    name="Hugging Face",
                    category="llm",
                    api_url="https://huggingface.co",
                    auth_type="bearer",
                    env_key="HF_TOKEN",
                    api_key=token,
                    daily_limit=10000
                )
                secure_vault.save_api_key(
                    platform="huggingface",
                    api_key=token,
                    email=email_data.get("email"),
                    meta={"source": "real_signup"}
                )
            self.results["huggingface"] = result
            log_event("signup", result)
            return result
        except Exception as e:
            log_event("signup_error", {"platform": "huggingface", "error": str(e)})
            return {"status": "error", "error": str(e)}
        finally:
            try:
                browser.close()
                pw.stop()
            except Exception:
                pass

    def signup_openrouter(self, email_data=None):
        if not email_data:
            email_data = real_email_agent.create_mail_tm()
        if not email_data:
            return {"status": "error", "reason": "no_email"}
        # OpenRouter غالباً يحتاج Google/GitHub — نسجل عبر API إن أمكن أو نتركه للـbrowser لاحقاً
        return {"status": "manual_needed", "platform": "openrouter", "email": email_data["email"]}

    def signup_groq(self, email_data=None):
        if not email_data:
            email_data = real_email_agent.create_mail_tm()
        return {"status": "manual_needed", "platform": "groq", "email": email_data["email"] if email_data else None}

    def register_all(self, platforms=None):
        platforms = platforms or ["huggingface"]
        results = {}
        for p in platforms:
            if p == "huggingface":
                results[p] = self.signup_huggingface()
            elif p == "openrouter":
                results[p] = self.signup_openrouter()
            elif p == "groq":
                results[p] = self.signup_groq()
            time.sleep(random.uniform(3, 7))
        return results


    def save_key_secure(self, platform: str, api_key: str, email: str = None, meta: dict = None):
        """حفظ أي مفتاح في الخزنة الآمنة"""
        return secure_vault.save_api_key(platform=platform, api_key=api_key, email=email, meta=meta or {})

real_signup = RealSignupAgent(headless=True)
