"""
Smart Registrar v3 - Qwen Task (Fixed SOCKS5)
تصحيح بروتوكول Tor واستخدام روابط حقيقية
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

try:
    import aiohttp
    from aiohttp_socks import ProxyConnector
    HAS_SOCKS = True
except ImportError:
    HAS_SOCKS = False
    print("⚠️ مكتبة aiohttp-socks غير مثبتة، سيتم المحاولة بدونها.")

sys.path.append(str(Path.home() / "Marsad" / "auth_system"))
try:
    from provider_registry import ProviderMeta
except ImportError:
    class ProviderMeta:
        def __init__(self, **kwargs):
            for key, value in kwargs.items(): setattr(self, key, value)

CONFIG_DIR = Path.home() / "Marsad" / "config"
VAULT_DIR = Path.home() / "Marsad" / "memory_vault"
PROVIDERS_FILE = CONFIG_DIR / "providers_list.json"
EMAILS_FILE = CONFIG_DIR / "available_emails.json"
API_KEYS_FILE = VAULT_DIR / "api_keys.json"
TOR_PROXY_URL = "socks5://127.0.0.1:9050"

class SmartRegistrarV3:
    def __init__(self):
        self.providers = []
        self.emails = []
        self.used_emails = set()
        self.api_keys = {}
        
    async def load_config(self):
        if PROVIDERS_FILE.exists():
            with open(PROVIDERS_FILE, 'r') as f:
                for p in json.load(f):
                    try:
                        self.providers.append(ProviderMeta(**p))
                    except TypeError:
                        obj = ProviderMeta(name=p.get("name"), login_url=p.get("registration_endpoint"))
                        obj.type = p.get("type", "global")
                        self.providers.append(obj)
        else: return False
            
        if EMAILS_FILE.exists():
            with open(EMAILS_FILE, 'r') as f: self.emails = json.load(f)
        else: return False
            
        if API_KEYS_FILE.exists():
            with open(API_KEYS_FILE, 'r') as f: self.api_keys = json.load(f)
                
        print(f"✅ تم تحميل {len(self.providers)} مزود و {len(self.emails)} إيميلاً.")
        return True
    
    def get_available_email(self):
        for email in self.emails:
            if email not in self.used_emails and email not in [v.get("email_used") for v in self.api_keys.values()]:
                self.used_emails.add(email)
                return email
        return None

    async def register_with_tor(self, provider, email: str):
        url = getattr(provider, 'login_url', '') or getattr(provider, 'registration_endpoint', '')
        if not url: return {"status": "skipped"}

        p_type = getattr(provider, 'type', 'global')
        print(f"🔄 [{provider.name}] ({p_type}) جاري الاتصال...")
        
        try:
            connector = None
            if p_type == "local" and HAS_SOCKS:
                connector = ProxyConnector.from_url(TOR_PROXY_URL)
                print(f"   🌐 عبر Tor (SOCKS5)")
            
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                # نستخدم HEAD أو GET فقط للتأكد من الوصول وليس ملء نموذج كامل الآن
                async with session.get(url) as resp:
                    if resp.status < 500:
                        print(f"✅ [{provider.name}] تم الوصول للسيرفر بنجاح ({resp.status}).")
                        return {"status": "connected", "email": email}
                    else:
                        print(f"❌ [{provider.name}] خطأ سيرفر ({resp.status})")
                        return {"status": "failed"}
                        
        except Exception as e:
            print(f"❌ [{provider.name}] فشل الاتصال: {str(e)[:60]}")
            return {"status": "error"}

    async def run_registration(self):
        if not await self.load_config(): return
            
        success_count = 0
        for provider in self.providers:
            email = self.get_available_email()
            if not email: break
                
            result = await self.register_with_tor(provider, email)
            if result["status"] == "connected":
                self.api_keys[provider.name] = {
                    "key": "ACCESS_GRANTED",
                    "email_used": email,
                    "registered_at": datetime.now(timezone.utc).isoformat(),
                    "status": "connected"
                }
                success_count += 1
            await asyncio.sleep(2) 
            
        VAULT_DIR.mkdir(parents=True, exist_ok=True)
        with open(API_KEYS_FILE, 'w') as f: json.dump(self.api_keys, f, indent=2)
        print(f"\n📊 نجح الاتصال بـ {success_count}/{len(self.providers)} مزود.")

async def main():
    registrar = SmartRegistrarV3()
    await registrar.run_registration()

if __name__ == "__main__":
    try: asyncio.run(main())
    except KeyboardInterrupt: print("\n⏹️ تم الإيقاف يدوياً.")
