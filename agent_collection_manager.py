"""
Agent Collection Manager - نظام إدارة جمع الوكلاء
- منع جمع البيانات المكررة
- تحديد مصادر الجمع
- إدارة الفترات الزمنية
"""
import time
import hashlib
import sqlite3
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from config import (
    DATASET_PLATFORMS,
    AGENT_COLLECTION_DUPLICATE_CHECK,
    AGENT_COLLECTION_INTERVAL,
    DB_PATH
)
from db import log_event, get_conn


class AgentCollectionManager:
    """
    نظام إدارة جمع الوكلاء
    - منع جمع البيانات المكررة باستخدام hash
    - تحديد مصادر الجمع بناءً على الجودة والأولوية
    - إدارة الفترات الزمنية بين عمليات الجمع
    """
    
    def __init__(self):
        self.last_collection_time = {}
        self.collection_stats = {}
        self._init_collection_tracking()
    
    def _init_collection_tracking(self):
        """تهيئة تتبع عمليات الجمع"""
        self.last_collection_time = {}
        self.collection_stats = {
            "total_collections": 0,
            "duplicate_skipped": 0,
            "new_items": 0,
            "errors": 0
        }
    
    def get_sorted_platforms(self, min_quality: str = "medium") -> List[Dict]:
        """
        الحصول على قائمة المنصات مرتبة حسب الأولوية والجودة
        
        Args:
            min_quality: الحد الأدنى لجودة المنصة (high, medium, low)
            
        Returns:
            قائمة المنصات مرتبة
        """
        # تحديد أوزان الجودة
        quality_weights = {
            "high": 3,
            "medium": 2,
            "low": 1
        }
        
        # فلترة المنصات بناءً على الجودة
        platforms = []
        for platform_name, platform_info in DATASET_PLATFORMS.items():
            platform_quality = platform_info.get("quality", "medium")
            if quality_weights.get(platform_quality, 0) >= quality_weights.get(min_quality, 0):
                platforms.append({
                    "name": platform_name,
                    "info": platform_info,
                    "weight": platform_info.get("weight", 0.1),
                    "priority": platform_info.get("priority", 1),
                    "quality": platform_quality,
                    "quality_weight": quality_weights.get(platform_quality, 1)
                })
        
        # ترتيب المنصات
        # 1. حسب الأولوية (أقل رقم = أعلى أولوية)
        # 2. حسب الوزن
        # 3. حسب جودة البيانات
        platforms.sort(key=lambda x: (
            x["priority"],
            -x["weight"],
            -x["quality_weight"]
        ))
        
        return platforms
    
    def should_collect_from_platform(self, platform_name: str) -> bool:
        """
        تحديد ما إذا كان يجب جمع البيانات من منصة معينة
        
        Args:
            platform_name: اسم المنصة
            
        Returns:
            True إذا يجب الجمع، False إذا لم يجب
        """
        # التحقق من الوقت منذ آخر جمع
        last_time = self.last_collection_time.get(platform_name, 0)
        current_time = time.time()
        
        # الحصول على فترة الانتظار للمنصة
        platform_info = DATASET_PLATFORMS.get(platform_name, {})
        
        # إذا كانت المنصة لا تتطلب انتظارًا (مثل GitHub)
        if not platform_info.get("rate_limit"):
            return True
        
        # حساب الوقت المتبقي
        min_interval = AGENT_COLLECTION_INTERVAL
        elapsed = current_time - last_time
        
        if elapsed < min_interval:
            return False
        
        return True
    
    def mark_collection_complete(self, platform_name: str, items_collected: int = 0):
        """
        تسجيل إكمال عملية جمع من منصة
        
        Args:
            platform_name: اسم المنصة
            items_collected: عدد العناصر المجمعة
        """
        self.last_collection_time[platform_name] = time.time()
        self.collection_stats["total_collections"] += 1
        self.collection_stats["new_items"] += items_collected
        
        log_event("agent_collection", {
            "platform": platform_name,
            "items_collected": items_collected,
            "timestamp": time.time()
        })
    
    def generate_content_hash(self, content: str, metadata: Optional[Dict] = None) -> str:
        """
        إنشاء hash فريد للمحتوى
        
        Args:
            content: المحتوى
            metadata: البيانات الوصفية
            
        Returns:
            hash فريد
        """
        hash_input = content
        
        if metadata:
            # ترتيب المفاتيح لضمان نفس hash للمetadata نفسه
            sorted_metadata = json.dumps(metadata, sort_keys=True, ensure_ascii=False)
            hash_input += sorted_metadata
        
        return hashlib.sha256(hash_input.encode()).hexdigest()
    
    def is_duplicate_content(self, content: str, metadata: Optional[Dict] = None, 
                           table: str = "memory") -> bool:
        """
        التحقق مما إذا كان المحتوى مكررًا
        
        Args:
            content: المحتوى
            metadata: البيانات الوصفية
            table: الجدول للبحث فيه
            
        Returns:
            True إذا كان مكررًا، False إذا كان جديدًا
        """
        if not AGENT_COLLECTION_DUPLICATE_CHECK:
            return False
        
        content_hash = self.generate_content_hash(content, metadata)
        
        try:
            with get_conn() as conn:
                # التحقق في جدول memory
                if table == "memory":
                    existing = conn.execute(
                        "SELECT id FROM memory WHERE content_hash = ?",
                        (content_hash,)
                    ).fetchone()
                    return existing is not None
                
                # التحقق في جدول samples
                elif table == "samples":
                    existing = conn.execute(
                        "SELECT id FROM samples WHERE sha256 = ?",
                        (content_hash,)
                    ).fetchone()
                    return existing is not None
                
                # التحقق في جدول datasets
                elif table == "datasets":
                    # استخدام name + platform كمعرف فريد
                    name = metadata.get("name", "") if metadata else ""
                    platform = metadata.get("platform", "") if metadata else ""
                    existing = conn.execute(
                        "SELECT id FROM datasets WHERE name = ? AND platform = ?",
                        (name, platform)
                    ).fetchone()
                    return existing is not None
                
                return False
                
        except Exception as e:
            log_event("duplicate_check", {"error": str(e), "table": table})
            return False
    
    def get_platform_stats(self) -> Dict[str, Any]:
        """
        الحصول على إحصائيات المنصات
        
        Returns:
            إحصائيات المنصات
        """
        stats = {}
        
        for platform_name, platform_info in DATASET_PLATFORMS.items():
            stats[platform_name] = {
                "last_collection": self.last_collection_time.get(platform_name, 0),
                "rate_limit": platform_info.get("rate_limit", 0),
                "type": platform_info.get("type", "unknown"),
                "free": platform_info.get("free", False),
                "region_specific": platform_info.get("region_specific", False),
                "can_collect": self.should_collect_from_platform(platform_name)
            }
        
        return stats
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """
        الحصول على إحصائيات عمليات الجمع
        
        Returns:
            إحصائيات عمليات الجمع
        """
        return self.collection_stats.copy()
    
    def reset_stats(self):
        """إعادة تعيين إحصائيات الجمع"""
        self._init_collection_tracking()
    
    def get_region_specific_platforms(self, region: str = None) -> List[str]:
        """
        الحصول على قائمة المنصات الخاصة بمنطقة معينة
        
        Args:
            region: المنطقة (إذا كانت None، يتم إرجاع جميع المنصات غير الخاصة بالمنطقة)
            
        Returns:
            قائمة أسماء المنصات
        """
        region_platforms = []
        
        for platform_name, platform_info in DATASET_PLATFORMS.items():
            if platform_info.get("region_specific", False):
                if region:
                    regions = platform_info.get("regions", [])
                    if region in regions:
                        region_platforms.append(platform_name)
            else:
                if not region:
                    region_platforms.append(platform_name)
        
        return region_platforms
    
    def set_platform_region(self, platform_name: str, region: str) -> bool:
        """
        تعيين منطقة لمنصة معينة
        
        Args:
            platform_name: اسم المنصة
            region: المنطقة
            
        Returns:
            True إذا نجحت العملية
        """
        # هذا يمكن أن يتم استخدامه لتحديث إعدادات المنصة ديناميكيًا
        if platform_name in DATASET_PLATFORMS:
            DATASET_PLATFORMS[platform_name]["current_region"] = region
            return True
        return False


# كائن عالمي
collection_manager = AgentCollectionManager()


# دوال مختصرة
def get_sorted_platforms(min_quality: str = "medium") -> List[Dict]:
    """دالة مختصرة للحصول على المنصات مرتبة"""
    return collection_manager.get_sorted_platforms(min_quality)


def should_collect_from_platform(platform_name: str) -> bool:
    """دالة مختصرة للتحقق مما إذا كان يجب الجمع من منصة"""
    return collection_manager.should_collect_from_platform(platform_name)


def mark_collection_complete(platform_name: str, items_collected: int = 0):
    """دالة مختصرة لتسجيل إكمال عملية جمع"""
    collection_manager.mark_collection_complete(platform_name, items_collected)


def is_duplicate_content(content: str, metadata: Optional[Dict] = None, 
                         table: str = "memory") -> bool:
    """دالة مختصرة للتحقق من المحتوى المكرر"""
    return collection_manager.is_duplicate_content(content, metadata, table)


def get_platform_stats() -> Dict[str, Any]:
    """دالة مختصرة للحصول على إحصائيات المنصات"""
    return collection_manager.get_platform_stats()


def get_collection_stats() -> Dict[str, Any]:
    """دالة مختصرة للحصول على إحصائيات عمليات الجمع"""
    return collection_manager.get_collection_stats()


# استيراد json
import json
