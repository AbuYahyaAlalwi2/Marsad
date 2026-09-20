"""
وكلاء مراقبة الدارك ويب
جمع الثغرات والأخبار الأمنية من المنتديات
"""

import os
import time
import requests
import threading
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from bs4 import BeautifulSoup
from datetime import datetime

try:
    from db import insert_sample, log_event, get_conn
    from config import DARKWEB_FORUMS, DARKWEB_SCRAPE_INTERVAL, DARKWEB_USER_AGENT, ENABLE_DARKWEB_MONITORING
    from vpn_config import vpn_manager
except ImportError:
    DARKWEB_FORUMS = []
    DARKWEB_SCRAPE_INTERVAL = 86400
    DARKWEB_USER_AGENT = "Mozilla/5.0"
    ENABLE_DARKWEB_MONITORING = False
    vpn_manager = None

    def insert_sample(*args, **kwargs): pass
    def log_event(*args, **kwargs): pass
    def get_conn(): pass


class ForumType(Enum):
    """أنواع المنتديات"""
    CLEARNET = "clearnet"
    TOR = "tor"
    I2P = "i2p"


@dataclass
class ForumConfig:
    """إعدادات المنتدى"""
    name: str
    url: str
    enabled: bool = True
    forum_type: ForumType = ForumType.CLEARNET
    scrape_interval: int = 86400
    user_agent: str = DARKWEB_USER_AGENT
    max_pages: int = 5
    keywords: List[str] = field(default_factory=lambda: [
        "exploit", "vulnerability", "CVE", "0day", "RCE", "SQLi",
        "XSS", "LFI", "RFI", "poc", "payload", "hack", "breach"
    ])


@dataclass
class ScrapedPost:
    """المنشورات المجمعة"""
    post_id: str
    title: str
    content: str
    url: str
    forum: str
    author: str = ""
    timestamp: float = field(default_factory=time.time)
    keywords_found: List[str] = field(default_factory=list)
    is_relevant: bool = False


class DarkWebMonitor:
    """
    نظام مراقبة الدارك ويب
    """
    
    def __init__(self):
        self.forums: Dict[str, ForumConfig] = {}
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_scrape: Dict[str, float] = {}
        
        # تحميل إعدادات المنتديات
        self._load_forums()
        
    def _load_forums(self):
        """تحميل إعدادات المنتديات"""
        for forum_info in DARKWEB_FORUMS:
            forum_config = ForumConfig(
                name=forum_info.get("name", ""),
                url=forum_info.get("url", ""),
                enabled=forum_info.get("enabled", True),
                forum_type=ForumType.TOR if forum_info.get("tor", False) else ForumType.CLEARNET
            )
            self.forums[forum_config.name] = forum_config
            self._last_scrape[forum_config.name] = 0
            
    def start(self):
        """بدء مراقبة الدارك ويب"""
        if not ENABLE_DARKWEB_MONITORING:
            print("[!] Dark Web monitoring is disabled")
            return
            
        if self._running:
            print("[!] Already running")
            return
            
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        print("[+] Dark Web monitoring started")
        
    def stop(self):
        """إيقاف مراقبة الدارك ويب"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)
        print("[+] Dark Web monitoring stopped")
        
    def _monitor_loop(self):
        """حلبة المراقبة الدورية"""
        while self._running:
            for forum_name, forum_config in self.forums.items():
                if not forum_config.enabled:
                    continue
                    
                # التحقق من الوقت المنقضي
                last_time = self._last_scrape.get(forum_name, 0)
                elapsed = time.time() - last_time
                
                if elapsed < forum_config.scrape_interval:
                    continue
                    
                # البدء في جمع البيانات
                try:
                    if forum_config.forum_type == ForumType.TOR:
                        # الاتصال عبر Tor
                        self._scrape_tor_forum(forum_config)
                    else:
                        # الاتصال العادي
                        self._scrape_clearnet_forum(forum_config)
                    
                    self._last_scrape[forum_name] = time.time()
                    log_event("darkweb", {"action": "scrape", "forum": forum_name, "status": "success"})
                except Exception as e:
                    log_event("darkweb", {"action": "scrape", "forum": forum_name, "error": str(e)})
            
            # الانتظار
            time.sleep(60)
            
    def _scrape_clearnet_forum(self, forum_config: ForumConfig):
        """جمع البيانات من منتديات Clearnet"""
        try:
            headers = {"User-Agent": forum_config.user_agent}
            response = requests.get(forum_config.url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                posts = self._extract_posts(soup, forum_config)
                self._process_posts(posts, forum_config)
            else:
                print(f"[-] Failed to scrape {forum_config.name}: HTTP {response.status_code}")
        except Exception as e:
            print(f"[-] Error scraping {forum_config.name}: {e}")
            
    def _scrape_tor_forum(self, forum_config: ForumConfig):
        """جمع البيانات من منتديات Tor"""
        # هنا يمكن استخدام Tor مع requests
        # أو استخدام proxies
        try:
            # إعداد proxy إذا كان Tor مفعلاً
            proxies = {
                'http': 'socks5h://127.0.0.1:9050',
                'https': 'socks5h://127.0.0.1:9050'
            }
            
            headers = {"User-Agent": forum_config.user_agent}
            response = requests.get(
                forum_config.url,
                headers=headers,
                proxies=proxies,
                timeout=60
            )
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                posts = self._extract_posts(soup, forum_config)
                self._process_posts(posts, forum_config)
            else:
                print(f"[-] Failed to scrape Tor forum {forum_config.name}: HTTP {response.status_code}")
        except Exception as e:
            print(f"[-] Error scraping Tor forum {forum_config.name}: {e}")
            
    def _extract_posts(self, soup: BeautifulSoup, forum_config: ForumConfig) -> List[ScrapedPost]:
        """استخراج المنشورات من الصفحة"""
        posts = []
        
        # محاولة العثور على المنشورات
        # هذه طريقة عامة ويمكن تحسينها لكل منتدى
        post_elements = soup.find_all(['div', 'article', 'li'], class_=lambda x: x and ('post' in x.lower() or 'thread' in x.lower()))
        
        for element in post_elements[:forum_config.max_pages]:
            try:
                title = element.find(['h1', 'h2', 'h3', 'a']).get_text(strip=True) if element.find(['h1', 'h2', 'h3', 'a']) else ""
                content = element.get_text(strip=True)
                url = element.find('a', href=True)['href'] if element.find('a', href=True) else ""
                author = element.find(class_=lambda x: x and 'author' in x.lower()).get_text(strip=True) if element.find(class_=lambda x: x and 'author' in x.lower()) else ""
                
                # التحقق من وجود كلمات مفتاحية
                keywords_found = [kw for kw in forum_config.keywords if kw.lower() in content.lower() or kw.lower() in title.lower()]
                is_relevant = len(keywords_found) > 0
                
                if is_relevant:
                    post_id = hashlib.sha256(f"{forum_config.name}{url}{time.time()}".encode()).hexdigest()[:16]
                    posts.append(ScrapedPost(
                        post_id=post_id,
                        title=title,
                        content=content,
                        url=url,
                        forum=forum_config.name,
                        author=author,
                        keywords_found=keywords_found,
                        is_relevant=True
                    ))
            except Exception:
                continue
                
        return posts
        
    def _process_posts(self, posts: List[ScrapedPost], forum_config: ForumConfig):
        """معالجة المنشورات المجمعة"""
        for post in posts:
            try:
                # حفظ في قاعدة البيانات
                insert_sample(
                    content=f"[DARKWEB] {post.title}\n\n{post.content}",
                    source=post.url,
                    platform=f"darkweb_{forum_config.name}",
                    language="text",
                    sample_type="vulnerability_report"
                )
                
                # تسجيل الحدث
                log_event("darkweb", {
                    "action": "collect",
                    "forum": forum_config.name,
                    "post_id": post.post_id,
                    "title": post.title,
                    "keywords": post.keywords_found
                })
                
                print(f"[+] Collected post from {forum_config.name}: {post.title}")
            except Exception as e:
                log_event("darkweb", {
                    "action": "process",
                    "error": str(e),
                    "post_id": post.post_id
                })
                
    def scrape_manual(self, forum_name: str) -> List[ScrapedPost]:
        """جمع يدوي من منتدى معين"""
        if forum_name not in self.forums:
            return []
            
        forum_config = self.forums[forum_name]
        try:
            if forum_config.forum_type == ForumType.TOR:
                self._scrape_tor_forum(forum_config)
            else:
                self._scrape_clearnet_forum(forum_config)
            
            # إرجاع آخر المنشورات
            return []
        except Exception as e:
            print(f"[-] Error: {e}")
            return []
            
    def add_custom_forum(self, name: str, url: str, forum_type: ForumType = ForumType.CLEARNET):
        """إضافة منتدى مخصص"""
        forum_config = ForumConfig(
            name=name,
            url=url,
            enabled=True,
            forum_type=forum_type
        )
        self.forums[name] = forum_config
        self._last_scrape[name] = 0
        
    def get_collected_posts(self, limit: int = 100) -> List[ScrapedPost]:
        """الحصول على آخر المنشورات المجمعة"""
        # هنا يمكن استرجاع البيانات من قاعدة البيانات
        return []


# إنشاء مثيل عالمي
darkweb_monitor = DarkWebMonitor()

if __name__ == "__main__":
    print("[+] Starting Dark Web Monitor")
    darkweb_monitor.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        darkweb_monitor.stop()
