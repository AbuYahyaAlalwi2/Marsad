"""
Key Manager - نظام إدارة المفاتيح
- حفظ المفاتيح في متغيرات بيئية (مفضل)
- حفظ المفاتيح في ملف .env
- حفظ المفاتيح في قاعدة البيانات (مشفرة)
- تخزين المفاتيح في قاعدة البيانات مع اتصال مباشر مع جميع collectors
"""
import os
import json
import hashlib
import sqlite3
import threading
from pathlib import Path
from typing import Dict, Optional, Any
from cryptography.fernet import Fernet
import base64
import logging

# إعداد تسجيل الأحداث
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class KeyManager:
    """
    نظام إدارة المفاتيح الرئيسي
    يدعم: متغيرات بيئية, ملف .env, قاعدة بيانات (مشفرة)
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, storage_method: str = None, db_path: str = None, encryption_key: str = None):
        """
        تهيئة KeyManager
        
        Args:
            storage_method: طريقة حفظ المفاتيح (env, file, db)
            db_path: مسار قاعدة البيانات (إذا كانت الطريقة db)
            encryption_key: مفتاح التشفير (إذا كانت الطريقة db)
        """
        # منع التهيئة المتكررة
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self.storage_method = storage_method or os.environ.get("CG_KEY_STORAGE", "db")
        self.db_path = db_path or os.environ.get("CG_DB_PATH", "data/cyberguard.db")
        self.encryption_key = encryption_key or os.environ.get("CG_ENCRYPTION_KEY")
        
        # إذا كانت الطريقة db وتوافر مفتاح التشفير
        if self.storage_method == "db" and not self.encryption_key:
            self.encryption_key = self._generate_encryption_key()
            logger.warning("Generated new encryption key. Please save it in CG_ENCRYPTION_KEY environment variable")
        
        # إذا كانت الطريقة db وتوافر مفتاح التشفير لكن قصيرا
        if self.storage_method == "db" and len(self.encryption_key) < 32:
            self.encryption_key = self._generate_encryption_key()
            logger.warning("Generated new encryption key. Previous key was too short. Please save it in CG_ENCRYPTION_KEY environment variable")
        
        # إذا كانت الطريقة file، تأكد من وجود ملف .env
        if self.storage_method == "file":
            self._ensure_env_file()
        
        # تهيئة قاعدة البيانات إذا كانت الطريقة db
        if self.storage_method == "db":
            self._ensure_db()
        
        self._initialized = True
        logger.info(f"KeyManager initialized with storage method: {self.storage_method}")
    
    def _generate_encryption_key(self) -> str:
        """
        إنشاء مفتاح تشفير جديد
        """
        return Fernet.generate_key().decode()
    
    def _ensure_env_file(self):
        """
        تأكد من وجود ملف .env
        """
        env_path = Path(".env")
        if not env_path.exists():
            env_path.touch()
            logger.info("Created .env file")
    
    def _ensure_db(self):
        """
        تأكد من وجود جدول secure_keys في قاعدة البيانات
        """
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            conn = sqlite3.connect(self.db_path, timeout=30)
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS secure_keys (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key_name TEXT UNIQUE NOT NULL,
                    encrypted_value TEXT NOT NULL,
                    key_type TEXT DEFAULT 'api_key',
                    platform TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    last_used_at REAL,
                    usage_count INTEGER DEFAULT 0
                )
            """)
            
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_secure_keys_name ON secure_keys(key_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_secure_keys_type ON secure_keys(key_type)")
            
            conn.commit()
            conn.close()
            logger.info("Ensured secure_keys table exists in database")
        except Exception as e:
            logger.error(f"Error ensuring database: {e}")
            raise
    
    def _get_fernet(self) -> Fernet:
        """
        الحصول على كائن Fernet للتشفير
        """
        if not self.encryption_key:
            raise ValueError("Encryption key not set")
        return Fernet(self.encryption_key.encode())
    
    # ==================== طرق الحصول على المفاتيح ====================
    
    def get_key(self, key_name: str, default: Optional[str] = None) -> Optional[str]:
        """
        الحصول على مفتاح من طريقة التخزين المحددة
        
        Args:
            key_name: اسم المفتاح
            default: قيمة افتراضية إذا لم يتم العثور عليه
            
        Returns:
            قيمة المفتاح أو None
        """
        if self.storage_method == "env":
            return self._get_key_from_env(key_name, default)
        elif self.storage_method == "file":
            return self._get_key_from_file(key_name, default)
        elif self.storage_method == "db":
            return self._get_key_from_db(key_name, default)
        else:
            raise ValueError(f"Unknown storage method: {self.storage_method}")
    
    def _get_key_from_env(self, key_name: str, default: Optional[str] = None) -> Optional[str]:
        """
        الحصول على مفتاح من متغيرات البيئة
        """
        return os.environ.get(key_name, default)
    
    def _get_key_from_file(self, key_name: str, default: Optional[str] = None) -> Optional[str]:
        """
        الحصول على مفتاح من ملف .env
        """
        try:
            from dotenv import dotenv_values
            env_vars = dotenv_values(".env")
            return env_vars.get(key_name, default)
        except ImportError:
            logger.error("python-dotenv not installed. Install with: pip install python-dotenv")
            return default
    
    def _get_key_from_db(self, key_name: str, default: Optional[str] = None) -> Optional[str]:
        """
        الحصول على مفتاح من قاعدة البيانات (مشفرة)
        """
        if not self.db_path:
            logger.error("Database path not set")
            return default
        
        try:
            conn = sqlite3.connect(self.db_path, timeout=30)
            cursor = conn.cursor()
            
            # الحصول على المفتاح المشفر
            cursor.execute("SELECT encrypted_value FROM secure_keys WHERE key_name = ?", (key_name,))
            result = cursor.fetchone()
            
            if result:
                encrypted_value = result[0]
                fernet = self._get_fernet()
                decrypted_value = fernet.decrypt(encrypted_value.encode()).decode()
                
                # تحديث إحصائيات الاستخدام
                self._update_key_usage(conn, key_name)
                
                conn.close()
                return decrypted_value
            
            conn.close()
            return default
            
        except Exception as e:
            logger.error(f"Error getting key from database: {e}")
            return default
    
    def _update_key_usage(self, conn, key_name: str):
        """
        تحديث إحصائيات استخدام المفتاح
        """
        try:
            cursor = conn.cursor()
            cursor.execute(
                """UPDATE secure_keys 
                   SET last_used_at = ?, usage_count = usage_count + 1
                   WHERE key_name = ?""",
                (time.time(), key_name)
            )
            conn.commit()
        except Exception as e:
            logger.error(f"Error updating key usage: {e}")
    
    # ==================== طرق حفظ المفاتيح ====================
    
    def set_key(self, key_name: str, key_value: str, key_type: str = "api_key", platform: str = None) -> bool:
        """
        حفظ مفتاح
        
        Args:
            key_name: اسم المفتاح
            key_value: قيمة المفتاح
            key_type: نوع المفتاح (api_key, token, etc.)
            platform: المنصة التي ينتمي إليها المفتاح
            
        Returns:
            True إذا نجحت العملية, False إذا فشلت
        """
        if self.storage_method == "env":
            logger.warning("Cannot set environment variable at runtime. Use export or .env file")
            return False
        elif self.storage_method == "file":
            return self._set_key_in_file(key_name, key_value)
        elif self.storage_method == "db":
            return self._set_key_in_db(key_name, key_value, key_type, platform)
        else:
            raise ValueError(f"Unknown storage method: {self.storage_method}")
    
    def _set_key_in_file(self, key_name: str, key_value: str) -> bool:
        """
        حفظ مفتاح في ملف .env
        """
        try:
            env_path = Path(".env")
            
            # قراءة الملف الحالي
            env_lines = []
            if env_path.exists():
                with open(env_path, 'r') as f:
                    env_lines = f.readlines()
            
            # تحديث أو إضافة المفتاح
            found = False
            new_lines = []
            for line in env_lines:
                if line.startswith(f"{key_name}="):
                    new_lines.append(f"{key_name}={key_value}\n")
                    found = True
                else:
                    new_lines.append(line)
            
            if not found:
                new_lines.append(f"{key_name}={key_value}\n")
            
            # كتابة الملف
            with open(env_path, 'w') as f:
                f.writelines(new_lines)
            
            logger.info(f"Saved key {key_name} to .env file")
            return True
            
        except Exception as e:
            logger.error(f"Error saving key to .env file: {e}")
            return False
    
    def _set_key_in_db(self, key_name: str, key_value: str, key_type: str = "api_key", platform: str = None) -> bool:
        """
        حفظ مفتاح في قاعدة البيانات (مشفرة)
        """
        if not self.db_path:
            logger.error("Database path not set")
            return False
        
        try:
            import time
            conn = sqlite3.connect(self.db_path, timeout=30)
            cursor = conn.cursor()
            
            # تشفير قيمة المفتاح
            fernet = self._get_fernet()
            encrypted_value = fernet.encrypt(key_value.encode()).decode()
            
            # حفظ المفتاح
            cursor.execute("""
                INSERT OR REPLACE INTO secure_keys 
                (key_name, encrypted_value, key_type, platform, created_at, updated_at)
                VALUES (?, ?, ?, ?, COALESCE((SELECT created_at FROM secure_keys WHERE key_name = ?), ?), ?)
            """, (key_name, encrypted_value, key_type, platform, key_name, time.time(), time.time()))
            
            conn.commit()
            conn.close()
            logger.info(f"Saved key {key_name} to database (encrypted)")
            return True
            
        except Exception as e:
            logger.error(f"Error saving key to database: {e}")
            if conn:
                conn.rollback()
                conn.close()
            return False
    
    # ==================== طرق حذف المفاتيح ====================
    
    def delete_key(self, key_name: str) -> bool:
        """
        حذف مفتاح
        
        Args:
            key_name: اسم المفتاح
            
        Returns:
            True إذا نجحت العملية, False إذا فشلت
        """
        if self.storage_method == "env":
            logger.warning("Cannot delete environment variable at runtime")
            return False
        elif self.storage_method == "file":
            return self._delete_key_from_file(key_name)
        elif self.storage_method == "db":
            return self._delete_key_from_db(key_name)
        else:
            raise ValueError(f"Unknown storage method: {self.storage_method}")
    
    def _delete_key_from_file(self, key_name: str) -> bool:
        """
        حذف مفتاح من ملف .env
        """
        try:
            env_path = Path(".env")
            
            if not env_path.exists():
                return False
            
            with open(env_path, 'r') as f:
                lines = f.readlines()
            
            new_lines = [line for line in lines if not line.startswith(f"{key_name}=")]
            
            with open(env_path, 'w') as f:
                f.writelines(new_lines)
            
            logger.info(f"Deleted key {key_name} from .env file")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting key from .env file: {e}")
            return False
    
    def _delete_key_from_db(self, key_name: str) -> bool:
        """
        حذف مفتاح من قاعدة البيانات
        """
        if not self.db_path:
            logger.error("Database path not set")
            return False
        
        try:
            conn = sqlite3.connect(self.db_path, timeout=30)
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM secure_keys WHERE key_name = ?", (key_name,))
            conn.commit()
            
            if cursor.rowcount > 0:
                logger.info(f"Deleted key {key_name} from database")
                conn.close()
                return True
            
            conn.close()
            return False
            
        except Exception as e:
            logger.error(f"Error deleting key from database: {e}")
            if conn:
                conn.rollback()
                conn.close()
            return False
    
    # ==================== طرق قائمة المفاتيح ====================
    
    def list_keys(self) -> Dict[str, str]:
        """
        قائمة بجميع المفاتيح المخزنة
        
        Returns:
            قاموس يحتوي على أسماء المفاتيح وقيمها (إذا كانت طريقة التخزين file أو env)
        """
        if self.storage_method == "env":
            # لا يمكن قائمة مفاتيح بيئية
            return {}
        elif self.storage_method == "file":
            return self._list_keys_from_file()
        elif self.storage_method == "db":
            return self._list_keys_from_db()
        else:
            raise ValueError(f"Unknown storage method: {self.storage_method}")
    
    def _list_keys_from_file(self) -> Dict[str, str]:
        """
        قائمة المفاتيح من ملف .env
        """
        try:
            from dotenv import dotenv_values
            return dotenv_values(".env")
        except ImportError:
            logger.error("python-dotenv not installed")
            return {}
    
    def _list_keys_from_db(self) -> Dict[str, str]:
        """
        قائمة المفاتيح من قاعدة البيانات
        """
        if not self.db_path:
            logger.error("Database path not set")
            return {}
        
        try:
            conn = sqlite3.connect(self.db_path, timeout=30)
            cursor = conn.cursor()
            
            cursor.execute("SELECT key_name, key_type, platform FROM secure_keys ORDER BY key_name")
            results = cursor.fetchall()
            
            keys = {}
            for row in results:
                keys[row[0]] = {"type": row[1], "platform": row[2], "value": "***ENCRYPTED***"}
            
            conn.close()
            return keys
            
        except Exception as e:
            logger.error(f"Error listing keys from database: {e}")
            return {}
    
    # ==================== طرق التحقق من المفاتيح ====================
    
    def validate_key(self, key_name: str, key_value: str) -> bool:
        """
        التحقق من صحة مفتاح
        
        Args:
            key_name: اسم المفتاح
            key_value: قيمة المفتاح
            
        Returns:
            True إذا كان المفتاح صالحاً
        """
        # قائمة المدققين لكل نوع من المفاتيح
        validators = {
            "GOOGLE_API_KEY": self._validate_google_key,
            "GITHUB_TOKEN": self._validate_github_token,
            "HF_TOKEN": self._validate_hf_token,
            "MISTRAL_API_KEY": self._validate_mistral_key,
            "GROQ_API_KEY": self._validate_groq_key,
        }
        
        validator = validators.get(key_name)
        if validator:
            return validator(key_value)
        
        # إذا لم يتم العثور على مدقق، افترض أنه صالح
        return True
    
    def _validate_google_key(self, api_key: str) -> bool:
        """
        التحقق من مفتاح Google API
        """
        try:
            import requests
            url = "https://generativelanguage.googleapis.com/v1beta/models"
            params = {"key": api_key}
            response = requests.get(url, params=params, timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def _validate_github_token(self, token: str) -> bool:
        """
        التحقق من token GitHub
        """
        try:
            import requests
            url = "https://api.github.com/user"
            headers = {"Authorization": f"token {token}"}
            response = requests.get(url, headers=headers, timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def _validate_hf_token(self, token: str) -> bool:
        """
        التحقق من token Hugging Face
        """
        try:
            import requests
            url = "https://api-inference.huggingface.co/models"
            headers = {"Authorization": f"Bearer {token}"}
            response = requests.get(url, headers=headers, timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def _validate_mistral_key(self, api_key: str) -> bool:
        """
        التحقق من مفتاح Mistral API
        """
        try:
            import requests
            url = "https://api.mistral.ai/v1/models"
            headers = {"Authorization": f"Bearer {api_key}"}
            response = requests.get(url, headers=headers, timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def _validate_groq_key(self, api_key: str) -> bool:
        """
        التحقق من مفتاح Groq API
        """
        try:
            import requests
            url = "https://api.groq.com/openai/v1/models"
            headers = {"Authorization": f"Bearer {api_key}"}
            response = requests.get(url, headers=headers, timeout=5)
            return response.status_code == 200
        except:
            return False


# كائن عالمي
key_manager = KeyManager()


def get_key(key_name: str, default: Optional[str] = None) -> Optional[str]:
    """
    دالة مختصرة للحصول على مفتاح
    """
    return key_manager.get_key(key_name, default)


def set_key(key_name: str, key_value: str, key_type: str = "api_key", platform: str = None) -> bool:
    """
    دالة مختصرة لحفظ مفتاح
    """
    return key_manager.set_key(key_name, key_value, key_type, platform)


def validate_key(key_name: str, key_value: str) -> bool:
    """
    دالة مختصرة للتحقق من مفتاح
    """
    return key_manager.validate_key(key_name, key_value)


def delete_key(key_name: str) -> bool:
    """
    دالة مختصرة لحذف مفتاح
    """
    return key_manager.delete_key(key_name)


def list_keys() -> Dict[str, str]:
    """
    دالة مختصرة لقائمة المفاتيح
    """
    return key_manager.list_keys()


# إضافة دعم للاتصال المباشر مع collectors
class KeyManagerCollectorProxy:
    """
    واجهة connecting بين key_manager و collectors
    """
    
    def __init__(self):
        self.key_manager = key_manager
    
    def get_api_key(self, platform: str) -> Optional[str]:
        """
        الحصول على مفتاح API لمنصة معينة
        """
        # قائمة mapping بين المنصات و أسماء المفاتيح
        platform_keys = {
            "github": "GITHUB_TOKEN",
            "gitlab": "GITLAB_TOKEN",
            "huggingface": "HF_TOKEN",
            "google": "GOOGLE_API_KEY",
            "groq": "GROQ_API_KEY",
            "mistral": "MISTRAL_API_KEY",
            "cerebras": "CEREBRAS_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
            "fireworks": "FIREWORKS_API_KEY",
            "together": "TOGETHER_API_KEY",
            "cohere": "COHERE_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
            "replicate": "REPLICATE_API_TOKEN",
            "cloudflare": "CLOUDFLARE_API_TOKEN",
            "nvidia": "NVIDIA_API_KEY",
            "sambanova": "SAMBANOVA_API_KEY",
            "ai21": "AI21_API_KEY",
            "baseten": "BASETEN_API_KEY",
            "perplexity": "PERPLEXITY_API_KEY",
            "voyage": "VOYAGE_API_KEY",
            "jina": "JINA_API_KEY",
            "openai": "OPENAI_API_KEY",
            "sourcegraph": "SOURCEGRAPH_TOKEN",
            "virus_total": "VIRUSTOTAL_API_KEY",
            "shodan": "SHODAN_API_KEY",
        }
        
        key_name = platform_keys.get(platform.lower(), platform.upper())
        return self.key_manager.get_key(key_name)
    
    def get_all_platform_keys(self) -> Dict[str, Optional[str]]:
        """
        الحصول على جميع مفاتيح المنصات
        """
        platforms = [
            "github", "gitlab", "huggingface", "google", "groq", "mistral",
            "cerebras", "openrouter", "fireworks", "together", "cohere",
            "deepseek", "replicate", "cloudflare", "nvidia", "sambanova",
            "ai21", "baseten", "perplexity", "voyage", "jina", "openai",
            "sourcegraph", "virus_total", "shodan"
        ]
        
        keys = {}
        for platform in platforms:
            keys[platform] = self.get_api_key(platform)
        
        return keys


# كائن proxy عالمي
key_collector_proxy = KeyManagerCollectorProxy()
