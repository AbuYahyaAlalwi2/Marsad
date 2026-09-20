"""
الوكيل المتطفل — يعيش داخل المنصات الأخرى
"""
import time
import random
from db import log_event

class ParasiticAgent:
    """
    وكيل يتخفى كمستخدم عادي داخل المنصات:
    - GitHub: يراقب commits، يحلل كود، يرسل تقارير
    - StackOverflow: يراقب أسئلة الأمان، يجمع إجابات
    - Reddit: يراقب نقاشات الأمن السيبراني
    
    الميزة: لا يحتاج API key، لا يُكتشف كبوت
    """
    
    def __init__(self, platform: str, identity: dict):
        self.platform = platform
        self.identity = identity  # اسم مستخدم، إيميل، إلخ
        self.session_duration = 0
        self.data_collected = 0
        
        log_event("parasite", {
            "status": "initialized",
            "platform": platform,
            "identity": identity.get("username", "unknown")
        })
    
    def behave_like_human(self):
        """تصرف كإنسان عادي"""
        behaviors = [
            self._browse_randomly,
            self._like_random_content,
            self._comment_occasionally,
            self._follow_users,
            self._update_profile
        ]
        
        # اختيار سلوك عشوائي
        behavior = random.choice(behaviors)
        behavior()
        
        # تأخير بشري
        time.sleep(random.uniform(30, 300))
    
    def collect_data(self) -> dict:
        """جمع البيانات المخفية"""
        collected = {
            "platform": self.platform,
            "timestamp": time.time(),
            "items": []
        }
        
        if self.platform == "github":
            collected["items"] = self._collect_github()
        elif self.platform == "stackoverflow":
            collected["items"] = self._collect_stackoverflow()
        elif self.platform == "reddit":
            collected["items"] = self._collect_reddit()
        
        self.data_collected += len(collected["items"])
        
        log_event("parasite", {
            "action": "data_collected",
            "platform": self.platform,
            "items": len(collected["items"])
        })
        
        return collected
    
    def _collect_github(self) -> list:
        """جمع من GitHub كمستخدم عادي"""
        # في الإنتاج: استخدام Playwright/Selenium للتخفي
        # هنا: محاكاة
        
        return [
            {"type": "commit", "repo": "example/repo", "analysis": "vulnerability_detected"},
            {"type": "issue", "repo": "example/repo2", "analysis": "security_concern"}
        ]
    
    def _collect_stackoverflow(self) -> list:
        """جمع من StackOverflow"""
        return [
            {"type": "question", "tags": ["security", "vulnerability"], "analysis": "exploit_discussion"},
            {"type": "answer", "tags": ["penetration-testing"], "analysis": "technique_shared"}
        ]
    
    def _collect_reddit(self) -> list:
        """جمع من Reddit"""
        return [
            {"type": "post", "subreddit": "netsec", "analysis": "threat_intelligence"},
            {"type": "comment", "subreddit": "cybersecurity", "analysis": "tool_mention"}
        ]
    
    def _browse_randomly(self):
        """تصفح عشوائي — محاكاة سلوك بشري"""
        pass
    
    def _like_random_content(self):
        """إعجاب بمحتوى عشوائي"""
        pass
    
    def _comment_occasionally(self):
        """تعليق نادراً"""
        pass
    
    def _follow_users(self):
        """متابعة مستخدمين"""
        pass
    
    def _update_profile(self):
        """تحديث الملف الشخصي نادراً"""
        pass
    
    def get_stats(self) -> dict:
        """إحصائيات الوكيل المتطفل"""
        return {
            "platform": self.platform,
            "identity": self.identity.get("username"),
            "session_duration_hours": self.session_duration / 3600,
            "data_collected": self.data_collected
        }

class ParasiteSwarm:
    """سرب من الوكلاء المتطفلين"""
    
    def __init__(self):
        self.parasites = []
        
        log_event("parasite_swarm", {"status": "initialized"})
    
    def deploy(self, platform: str, count: int) -> list:
        """نشر وكلاء متطفلين على منصة"""
        deployed = []
        
        for i in range(count):
            identity = {
                "username": f"user_{random.randint(10000, 99999)}",
                "email": f"user{i}@tempmail.com",
                "created_at": time.time() - random.randint(86400*30, 86400*365)  # حساب قديم
            }
            
            parasite = ParasiticAgent(platform, identity)
            self.parasites.append(parasite)
            deployed.append(parasite)
        
        log_event("parasite_swarm", {
            "action": "deployed",
            "platform": platform,
            "count": count
        })
        
        return deployed
    
    def collect_all(self) -> list:
        """جمع البيانات من كل الوكلاء"""
        all_data = []
        
        for parasite in self.parasites:
            data = parasite.collect_data()
            all_data.append(data)
        
        return all_data

# نسخة عامة
parasite_swarm = ParasiteSwarm()
