"""
Stealth Lite Bot - Qwen Task
وكيل خفيف يحاكي البشر، يدور الـ IP عبر Tor، ويتخطى الفحوصات الأساسية
"""

import requests
from fake_useragent import UserAgent
import stem.process
import time
import random
from stem.control import Controller

# ─── إعدادات التمويه ────────────────────────────────────────────────────────────
ua = UserAgent()

class StealthBot:
    def __init__(self):
        self.session = requests.Session()
        self.tor_port = 9050
        self.tor_control_port = 9051
        
    def get_new_identity(self):
        """تغيير هوية الـ IP عبر Tor (New Circuit)"""
        try:
            with Controller.from_port(port=self.tor_control_port) as controller:
                controller.authenticate()
                controller.signal(stem.Signal.NEWNYM)
                print("🔄 تم تغيير هوية Tor (IP جديد).")
                time.sleep(5) # انتظار لاستقرار الاتصال الجديد
        except Exception as e:
            print(f"⚠️ فشل تغيير الهوية: {e}. تأكد أن Tor يعمل.")

    def prepare_human_headers(self):
        """إعداد هيدرز تحاكي متصفح بشري حقيقي"""
        headers = {
            'User-Agent': ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
        }
        self.session.headers.update(headers)
        
    def human_delay(self):
        """انتظار عشوائي بين الطلبات"""
        time.sleep(random.uniform(2, 6))

    def register_stealth(self, url, email, password):
        """محاولة تسجيل دخول خفية"""
        self.get_new_identity()
        self.prepare_human_headers()
        
        print(f"🕵️ [{url}] جاري التسجيل بهوية جديدة...")
        
        try:
            # 1. زيارة الصفحة الرئيسية لكسب الـ Cookies
            self.session.get(url, timeout=20)
            self.human_delay()
            
            # 2. إرسال طلب التسجيل (POST)
            payload = {
                'email': email, 
                'password': password, 
                'confirm_password': password,
                'terms': 'on'
            }
            
            # ملاحظة: يجب تعديل اسماء الحقول (email, password) حسب كل موقع
            response = self.session.post(url, data=payload, timeout=20)
            
            if response.status_code in [200, 201, 302]:
                print(f"✅ نجاح! الاستجابة: {response.status_code}")
                # هنا يمكن البحث عن مفتاح API في الـ Response إذا كان JSON
                return True
            else:
                print(f"❌ فشل. الاستجابة: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ خطأ في الاتصال: {e}")
            return False

# ─── اختبار الوكيل ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    bot = StealthBot()
    # تجربة على رابط وهمي للتأكد من عمل المنطق
    bot.register_stealth("https://httpbin.org/post", "test@delfin.security", "Pass123!")
