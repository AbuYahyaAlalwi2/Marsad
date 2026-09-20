"""
IP Rotator — تدوير IP مجاني (Tor + Proxy List)
"""
import requests
import random
import time
from datetime import datetime

class IPRotator:
    """
    تدوير IP باستخدام:
    1. Tor (إذا متاح)
    2. Proxy List مجانية
    3. Direct (كآخر حل)
    """
    
    def __init__(self):
        self.tor_available = self._check_tor()
        self.proxy_list = []
        self.failed_proxies = set()
        self.current_index = 0
        self.request_count = 0
        
        # تحميل بروكسيات مجانية
        self._load_free_proxies()
    
    def _check_tor(self):
        """التحقق من توفر Tor"""
        try:
            session = requests.Session()
            session.proxies = {
                'http': 'socks5://127.0.0.1:9050',
                'https': 'socks5://127.0.0.1:9050'
            }
            resp = session.get("https://api.ipify.org?format=json", timeout=5)
            print("✓ Tor is available")
            return True
        except:
            print("⚠ Tor not available — using proxy list")
            return False
    
    def _load_free_proxies(self):
        """تحميل بروكسيات مجانية من مصادر عامة"""
        sources = [
            "https://api.proxyscrape.com/v2/?request=get&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all",
            "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
            "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
        ]
        
        for url in sources:
            try:
                resp = requests.get(url, timeout=10)
                if resp.status_code == 200:
                    proxies = resp.text.strip().split('\n')
                    self.proxy_list.extend([p.strip() for p in proxies if ':' in p])
                    print(f"✓ Loaded {len(proxies)} proxies from {url[:50]}...")
            except:
                pass
        
        # إضافة بروكسيات افتراضية (للاختبار)
        if not self.proxy_list:
            self.proxy_list = [
                "http://103.152.112.234:80",
                "http://185.132.242.142:80",
                "http://45.77.56.114:80",
            ]
        
        print(f"✓ Total proxies loaded: {len(self.proxy_list)}")
    
    def get_session(self):
        """الحصول على جلسة requests مع IP جديد"""
        self.request_count += 1
        
        # استخدام Tor إذا متاح (كل 10 طلبات)
        if self.tor_available and self.request_count % 10 == 0:
            return self._get_tor_session()
        
        # استخدام Proxy List
        return self._get_proxy_session()
    
    def _get_tor_session(self):
        """جلسة عبر Tor"""
        session = requests.Session()
        session.proxies = {
            'http': 'socks5://127.0.0.1:9050',
            'https': 'socks5://127.0.0.1:9050'
        }
        return session
    
    def _get_proxy_session(self):
        """جلسة عبر Proxy"""
        available = [p for p in self.proxy_list if p not in self.failed_proxies]
        
        if not available:
            # إعادة تعيين الفاشلة
            self.failed_proxies.clear()
            available = self.proxy_list
        
        proxy = available[self.current_index % len(available)]
        self.current_index += 1
        
        session = requests.Session()
        session.proxies = {
            'http': proxy,
            'https': proxy
        }
        
        return session
    
    def rotate_ip(self):
        """تغيير IP صراحة"""
        if self.tor_available:
            try:
                from stem import Signal
                from stem.control import Controller
                
                with Controller.from_port(port=9051) as controller:
                    controller.authenticate()
                    controller.signal(Signal.NEWNYM)
                    print("✓ Tor IP rotated")
                    return True
            except:
                pass
        
        # تغيير Proxy
        self.current_index += 1
        print(f"✓ Switched to proxy #{self.current_index}")
        return True
    
    def get_current_ip(self):
        """الحصول على IP الحالي"""
        try:
            session = self.get_session()
            resp = session.get("https://api.ipify.org?format=json", timeout=10)
            return resp.json()["ip"]
        except:
            return None
    
    def mark_failed(self, proxy_or_error):
        """تعليم بروكسي كفاشل"""
        if isinstance(proxy_or_error, str):
            self.failed_proxies.add(proxy_or_error)
    
    def get_stats(self):
        """إحصائيات"""
        return {
            "tor_available": self.tor_available,
            "total_proxies": len(self.proxy_list),
            "failed_proxies": len(self.failed_proxies),
            "request_count": self.request_count,
            "current_ip": self.get_current_ip()
        }


class SmartRequest:
    """
    طلبات ذكية مع:
    - IP rotation تلقائي
    - Retry عند الفشل
    - User-Agent rotation
    """
    
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    ]
    
    def __init__(self):
        self.rotator = IPRotator()
        self.max_retries = 3
    
    def get(self, url, **kwargs):
        """GET request مع IP rotation"""
        for attempt in range(self.max_retries):
            try:
                session = self.rotator.get_session()
                session.headers.update({
                    "User-Agent": random.choice(self.USER_AGENTS)
                })
                
                resp = session.get(url, timeout=15, **kwargs)
                
                # التحقق من الحظر
                if resp.status_code == 403:
                    print(f"⚠ Blocked (attempt {attempt + 1}) — rotating IP...")
                    self.rotator.rotate_ip()
                    continue
                
                return resp
                
            except requests.exceptions.RequestException as e:
                print(f"⚠ Request failed (attempt {attempt + 1}): {e}")
                self.rotator.rotate_ip()
                time.sleep(2)
        
        return None
    
    def post(self, url, **kwargs):
        """POST request مع IP rotation"""
        for attempt in range(self.max_retries):
            try:
                session = self.rotator.get_session()
                session.headers.update({
                    "User-Agent": random.choice(self.USER_AGENTS)
                })
                
                resp = session.post(url, timeout=15, **kwargs)
                
                if resp.status_code == 403:
                    self.rotator.rotate_ip()
                    continue
                
                return resp
                
            except requests.exceptions.RequestException:
                self.rotator.rotate_ip()
                time.sleep(2)
        
        return None


# ═══════════════════════════════════════════════════════════════
# Usage
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # اختبار
    print("Testing IP Rotator...")
    
    smart = SmartRequest()
    
    # اختبار IP الحالي
    ip = smart.rotator.get_current_ip()
    print(f"Current IP: {ip}")
    
    # اختبار طلب
    resp = smart.get("https://api.ipify.org?format=json")
    if resp:
        print(f"Request successful: {resp.json()}")
    
    # إحصائيات
    print(f"\nStats: {smart.rotator.get_stats()}")
