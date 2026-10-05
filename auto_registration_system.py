"""
Smart Auto-Registration System - Qwen Task
نظام التسجيل التلقائي الذكي لـ 70+ مزود باستخدام 50 إيميلاً
يحفظ المفاتيح في MemoryVault ليستخدمها مرصد (الكابل) لاحقاً
"""

import json
import os
import asyncio
import aiohttp
from datetime import datetime, timezone
from pathlib import Path

# ─── إعدادات النظام ────────────────────────────────────────────────────────────
PROVIDERS_FILE = Path.home() / "Marsad" / "config" / "providers_list.json" # ملف الـ 70+ مزود
EMAILS_FILE = Path.home() / "Marsad" / "config" / "available_emails.json"   # ملف الـ 50 إيميلاً
MEMORY_VAULT_PATH = Path.home() / "Marsad" / "memory_vault" / "api_keys.json" # مكان حفظ المفاتيح

class SmartAutoRegistrar:
    def __init__(self):
        self.providers = []
        self.emails = []
        self.used_emails = set()
        self.api_keys = {}
        
    async def load_config(self):
        """تحميل قائمة المزودين والإيميلات المتاحة"""
        if PROVIDERS_FILE.exists():
            with open(PROVIDERS_FILE, 'r') as f:
                self.providers = json.load(f)
        else:
            print("⚠️ ملف المزودين غير موجود. يرجى إنشاؤه في config/providers_list.json")
            return False
            
        if EMAILS_FILE.exists():
            with open(EMAILS_FILE, 'r') as f:
                self.emails = json.load(f)
        else:
            print("⚠️ ملف الإيميلات غير موجود. يرجى إنشاؤه في config/available_emails.json")
            return False
            
        # تحميل المفاتيح المحفوظة سابقاً
        if MEMORY_VAULT_PATH.exists():
            with open(MEMORY_VAULT_PATH, 'r') as f:
                self.api_keys = json.load(f)
                
        print(f"✅ تم تحميل {len(self.providers)} مزود و {len(self.emails)} إيميلاً.")
        return True
    
    def get_available_email(self):
        """الحصول على إيميل غير مستخدم حالياً"""
        for email in self.emails:
            if email not in self.used_emails and email not in self.api_keys.values():
                self.used_emails.add(email)
                return email
        return None # لا يوجد إيميل متاح
    
    async def register_provider(self, provider_info):
        """
        تسجيل دخول لمزود واحد والحصول على مفتاح API
        هذه الدالة هي القلب النابض للنظام
        """
        provider_name = provider_info.get("name")
        registration_url = provider_info.get("registration_endpoint")
        
        # التحقق مما إذا كان لدينا مفتاح محفوظ مسبقاً لهذا المزود
        if provider_name in self.api_keys:
            print(f"ℹ️ [{provider_name}] مفتاح API موجود مسبقاً. تخطي التسجيل.")
            return True
            
        # الحصول على إيميل متاح
        email = self.get_available_email()
        if not email:
            print(f"❌ [{provider_name}] لا يوجد إيميل متاح للتسجيل.")
            return False
            
        print(f"🔄 [{provider_name}] جاري التسجيل باستخدام {email}...")
        
        try:
            async with aiohttp.ClientSession() as session:
                # محاكاة طلب التسجيل (في الواقع يختلف حسب كل مزود)
                payload = {
                    "email": email,
                    "password": provider_info.get("default_password", "SecurePass123!"),
                    "agree_terms": True
                }
                
                async with session.post(registration_url, json=payload, timeout=30) as resp:
                    if resp.status == 200 or resp.status == 201:
                        data = await resp.json()
                        api_key = data.get("api_key") or data.get("token") or data.get("key")
                        
                        if api_key:
                            # حفظ المفتاح في MemoryVault مع الختم الزمني
                            self.api_keys[provider_name] = {
                                "key": api_key,
                                "email_used": email,
                                "registered_at": datetime.now(timezone.utc).isoformat(),
                                "status": "active"
                            }
                            print(f"✅ [{provider_name}] تم التسجيل بنجاح! المفتاح محفوظ.")
                            return True
                        else:
                            print(f"⚠️ [{provider_name}] تم التسجيل لكن لم يتم استرجاع مفتاح API.")
                            return False
                    else:
                        print(f"❌ [{provider_name}] فشل التسجيل. الحالة: {resp.status}")
                        return False
                        
        except Exception as e:
            print(f"❌ [{provider_name}] خطأ أثناء التسجيل: {e}")
            return False
    
    async def save_keys_to_vault(self):
        """حفظ جميع المفاتيح في MemoryVault بشكل آمن"""
        MEMORY_VAULT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(MEMORY_VAULT_PATH, 'w') as f:
            json.dump(self.api_keys, f, indent=2, ensure_ascii=False)
        print(f"💾 تم حفظ {len(self.api_keys)} مفتاح API في MemoryVault.")
    
    async def run_full_registration(self):
        """تشغيل عملية التسجيل الكاملة لجميع المزودين"""
        if not await self.load_config():
            return
            
        success_count = 0
        fail_count = 0
        
        for provider in self.providers:
            result = await self.register_provider(provider)
            if result:
                success_count += 1
            else:
                fail_count += 1
                
            # تأخير صغير لتجنب الحظر من قبل المزودين
            await asyncio.sleep(2)
            
        await self.save_keys_to_vault()
        
        print(f"\n📊 ملخص التسجيل:")
        print(f"   • ناجح: {success_count}")
        print(f"   • فاشل/متخطى: {fail_count}")
        print(f"   • إجمالي المفاتيح المحفوظة: {len(self.api_keys)}")

# ─── نقطة الدخول الرئيسية ───────────────────────────────────────────────────────
async def main():
    registrar = SmartAutoRegistrar()
    await registrar.run_full_registration()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️ تم إيقاف نظام التسجيل يدوياً.")
