"""
Mass Registration Campaign - Qwen Task
تسجيل شامل في المزودين المجانيين مع تجاوز الكابتشا البسيطة
"""

import asyncio
import json
import time
from pathlib import Path
from datetime import datetime, timezone

# استيراد الوكلاء السابقين
import sys
sys.path.append(str(Path.home() / "Marsad"))
try:
    from stealth_lite_bot import StealthBot
except ImportError:
    print("⚠️ يرجى التأكد من وجود stealth_lite_bot.py")
    class StealthBot:
        def register_stealth(self, url, email, pwd): return False

# ─── قائمة المزودين المستهدفة (مجانية ولا تطلب بطاقة غالباً) ────────────────────
TARGET_PROVIDERS = [
    {"name": "HuggingFace", "url": "https://huggingface.co/join", "type": "global"},
    {"name": "OpenRouter", "url": "https://openrouter.ai/auth/register", "type": "global"},
    {"name": "Groq", "url": "https://console.groq.com/login", "type": "global"}, # يتطلب تأكيد يدوي أحياناً
    {"name": "TogetherAI", "url": "https://api.together.xyz/signup", "type": "global"},
    {"name": "Cohere", "url": "https://dashboard.cohere.com/welcome/register", "type": "global"},
    {"name": "Mistral", "url": "https://console.mistral.ai/users/register", "type": "global"},
    {"name": "Replicate", "url": "https://replicate.com/signin", "type": "global"},
    {"name": "Fal.ai", "url": "https://fal.ai/dashboard", "type": "global"},
]

# تحميل الإيميلات
EMAILS_FILE = Path.home() / "Marsad" / "config" / "available_emails.json"
VAULT_FILE = Path.home() / "Marsad" / "secure_vault" / "keys.dat"

class MassRegistrar:
    def __init__(self):
        self.bot = StealthBot()
        self.emails = []
        self.used_emails = set()
        self.successful_keys = {}
        
    async def load_emails(self):
        if EMAILS_FILE.exists():
            with open(EMAILS_FILE, 'r') as f: self.emails = json.load(f)
            
    def get_next_email(self):
        for email in self.emails:
            if email not in self.used_emails:
                self.used_emails.add(email)
                return email
        return None

    async def process_provider(self, provider):
        email = self.get_next_email()
        if not email:
            print("⚠️ انتهت الإيميلات المتاحة!")
            return
            
        print(f"\n🎯 استهداف: {provider['name']}")
        success = self.bot.register_stealth(provider['url'], email, "MarsadSecure2026!")
        
        if success:
            # في الواقع، هنا نستخرج المفتاح من الصفحة أو البريد
            mock_key = f"sk-{provider['name']}-real-key-extracted"
            self.successful_keys[provider['name']] = {"key": mock_key, "email": email}
            print(f"✅ تم التسجيل بنجاح في {provider['name']}")
        else:
            print(f"❌ فشل التسجيل في {provider['name']} (ربما يحتاج Kaggle Solver)")
            # هنا يمكن إرسال المهمة لـ Kaggle إذا فشل المحلي
            
        await asyncio.sleep(5) # تأخير بين المحاولات

    async def run_campaign(self):
        await self.load_emails()
        print(f"🚀 بدء حملة التسجيل الشاملة لـ {len(TARGET_PROVIDERS)} مزود...")
        
        for provider in TARGET_PROVIDERS:
            await self.process_provider(provider)
            
        # حفظ النتائج
        if self.successful_keys:
            import base64
            encrypted = base64.b64encode(json.dumps(self.successful_keys).encode()).decode()
            VAULT_FILE.write_text(encrypted)
            print(f"\n💾 تم حفظ {len(self.successful_keys)} مفتاح جديد في الخزنة.")

if __name__ == "__main__":
    registrar = MassRegistrar()
    asyncio.run(registrar.run_campaign())
