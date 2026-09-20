"""
نظام مانع الخمول — يحافظ على تشغيل التطبيق بشكل مستمر
"""
import time
import threading
import requests
from config import KEEP_ALIVE_INTERVAL, MAX_RETRIES, REQUEST_TIMEOUT
from db import log_event


class KeepAliveManager:
    """
    إدارة نظام مانع الخمول
    - يرسل طلبات دورية للحفاظ على اتصال السحابة
    - يتحقق من صحة جميع الخدمات
    """

    def __init__(self):
        self._running = False
        self._thread = None
        self.keep_alive_url = None

    def start(self, keep_alive_url: str = None):
        """بدء نظام مانع الخمول"""
        self.keep_alive_url = keep_alive_url
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        log_event("keep_alive", {"status": "started", "interval": KEEP_ALIVE_INTERVAL})

    def stop(self):
        """إيقاف نظام مانع الخمول"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        log_event("keep_alive", {"status": "stopped"})

    def _run(self):
        """الحلقة الرئيسية لنظام مانع الخمول"""
        while self._running:
            try:
                self._ping_all_services()
                self._ping_external()
            except Exception as e:
                log_event("keep_alive", {"error": str(e)})
            
            # الانتظار للمدة المحددة
            for _ in range(KEEP_ALIVE_INTERVAL // 5):
                if not self._running:
                    break
                time.sleep(5)

    def _ping_all_services(self):
        """التحقق من جميع الخدمات الداخلية"""
        # هنا يمكن إضافة تحقق من خدمات داخلية
        pass

    def _ping_external(self):
        """إرسال طلب خارجي للحفاظ على الاتصال"""
        if self.keep_alive_url:
            self._ping_url(self.keep_alive_url)
        
        # محاولة الوصول إلى بعض المواقع الخارجية
        external_urls = [
            "https://www.google.com",
            "https://api.github.com",
            "https://huggingface.co"
        ]
        
        for url in external_urls:
            self._ping_url(url)

    def _ping_url(self, url: str, max_retries: int = MAX_RETRIES):
        """إرسال ping إلى URL معين"""
        for attempt in range(max_retries):
            try:
                response = requests.get(
                    url,
                    timeout=min(10, REQUEST_TIMEOUT),
                    headers={"User-Agent": "CYBERGUARD-KeepAlive/1.0"}
                )
                if response.status_code < 500:
                    log_event("keep_alive", {
                        "url": url,
                        "status": "success",
                        "status_code": response.status_code,
                        "attempt": attempt + 1
                    })
                    return True
            except Exception as e:
                if attempt == max_retries - 1:
                    log_event("keep_alive", {
                        "url": url,
                        "status": "failed",
                        "error": str(e),
                        "attempts": max_retries
                    })
                time.sleep(1)
        return False

    def ping(self, url: str) -> bool:
        """إرسال ping يدوي إلى URL"""
        return self._ping_url(url)


# إنشاء مثيل عالمي
keep_alive_manager = KeepAliveManager()


def start_keep_alive(keep_alive_url: str = None):
    """بدء نظام مانع الخمول"""
    keep_alive_manager.start(keep_alive_url)


def stop_keep_alive():
    """إيقاف نظام مانع الخمول"""
    keep_alive_manager.stop()
