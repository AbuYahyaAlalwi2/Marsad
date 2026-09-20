"""
خزنة آمنة للمفاتيح — تشفير Fernet + ملف محمي + قاعدة بيانات
كل API يُنشأ يُحفظ هنا تلقائياً
"""
import os
import json
import time
import base64
import hashlib
import threading
from pathlib import Path
from typing import Optional, Dict, List, Any

try:
    from cryptography.fernet import Fernet
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

from db import log_event, insert_api_provider

BASE = Path(__file__).resolve().parent
VAULT_FILE = BASE / "data" / "secure_vault.enc"
VAULT_KEY_FILE = BASE / "data" / ".vault_master.key"
LEGACY_JSON = BASE / "encrypted_keys.json"

class SecureVault:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if getattr(self, "_ready", False):
            return
        self._ready = True
        (BASE / "data").mkdir(parents=True, exist_ok=True)
        self.master_key = self._load_or_create_master_key()
        self.fernet = Fernet(self.master_key) if HAS_CRYPTO else None
        self._data: Dict[str, List[dict]] = {}
        self._load()
        # مزامنة مع KeyManager إن وُجد
        try:
            from key_manager import key_manager
            self.km = key_manager
        except Exception:
            self.km = None

    def _load_or_create_master_key(self) -> bytes:
        if VAULT_KEY_FILE.exists():
            key = VAULT_KEY_FILE.read_bytes().strip()
            if len(key) >= 32:
                return key if HAS_CRYPTO else key
        # إنشاء مفتاح جديد
        if HAS_CRYPTO:
            key = Fernet.generate_key()
        else:
            key = base64.urlsafe_b64encode(os.urandom(32))
        VAULT_KEY_FILE.write_bytes(key)
        try:
            os.chmod(VAULT_KEY_FILE, 0o600)
        except Exception:
            pass
        log_event("vault", {"action": "master_key_created"})
        return key

    def _encrypt(self, plain: str) -> str:
        if self.fernet:
            return self.fernet.encrypt(plain.encode()).decode()
        # fallback ضعيف (XOR بسيط) إذا لم تتوفر cryptography
        k = self.master_key[:16]
        return base64.b64encode(bytes(c ^ k[i % len(k)] for i, c in enumerate(plain.encode()))).decode()

    def _decrypt(self, token: str) -> str:
        if self.fernet:
            return self.fernet.decrypt(token.encode()).decode()
        k = self.master_key[:16]
        raw = base64.b64decode(token)
        return bytes(c ^ k[i % len(k)] for i, c in enumerate(raw)).decode()

    def _load(self):
        if VAULT_FILE.exists():
            try:
                raw = VAULT_FILE.read_text(encoding="utf-8")
                payload = json.loads(raw)
                # فك تشفير كل مفتاح
                for platform, entries in payload.items():
                    self._data[platform] = []
                    for e in entries:
                        try:
                            plain = self._decrypt(e["key_encrypted"])
                            self._data[platform].append({
                                **e,
                                "key": plain  # مؤقت في الذاكرة فقط
                            })
                        except Exception:
                            self._data[platform].append(e)
                return
            except Exception as e:
                log_event("vault_error", {"action": "load", "error": str(e)})
        # ترحيل من الملف القديم إن وُجد
        if LEGACY_JSON.exists():
            try:
                legacy = json.loads(LEGACY_JSON.read_text(encoding="utf-8"))
                for platform, entries in legacy.items():
                    for e in entries:
                        # المفاتيح القديمة مشفرة بطريقة أخرى — نحتفظ بها كما هي
                        self._data.setdefault(platform, []).append(e)
                self._persist()
            except Exception:
                pass

    def _persist(self):
        out = {}
        for platform, entries in self._data.items():
            out[platform] = []
            for e in entries:
                # لا نحفظ المفتاح الصريح على القرص
                safe = {k: v for k, v in e.items() if k != "key"}
                if "key_encrypted" not in safe and e.get("key"):
                    safe["key_encrypted"] = self._encrypt(e["key"])
                out[platform].append(safe)
        VAULT_FILE.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
        try:
            os.chmod(VAULT_FILE, 0o600)
        except Exception:
            pass

    def save_api_key(
        self,
        platform: str,
        api_key: str,
        account_id: str = None,
        email: str = None,
        meta: dict = None
    ) -> bool:
        """حفظ مفتاح API بشكل مشفر وآمن"""
        if not api_key or not platform:
            return False
        account_id = account_id or f"acc_{int(time.time())}"
        entry = {
            "key_encrypted": self._encrypt(api_key),
            "key": api_key,  # في الذاكرة فقط
            "account_id": account_id,
            "email": email,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "meta": meta or {},
            "real": True
        }
        with self._lock:
            self._data.setdefault(platform, []).append(entry)
            self._persist()

        # أيضاً في قاعدة البيانات عبر KeyManager
        if self.km:
            try:
                self.km.set_key(
                    key_name=f"{platform.upper()}_API_KEY_{account_id}",
                    key_value=api_key,
                    key_type="api_key",
                    platform=platform
                )
            except Exception as e:
                log_event("vault", {"action": "km_sync_fail", "error": str(e)})

        # تسجيل في جدول المزودين
        try:
            insert_api_provider(
                provider_key=platform,
                name=platform.replace("_", " ").title(),
                category="auto_registered",
                api_url="",
                auth_type="bearer",
                env_key=f"{platform.upper()}_API_KEY",
                api_key=api_key,
                daily_limit=1000
            )
        except Exception:
            pass

        log_event("vault", {
            "action": "saved",
            "platform": platform,
            "account_id": account_id,
            "email": email
        })
        return True

    def get_keys(self, platform: str) -> List[str]:
        """إرجاع قائمة المفاتيح الصريحة لمنصة (من الذاكرة)"""
        return [e.get("key") or self._decrypt(e["key_encrypted"]) for e in self._data.get(platform, []) if e.get("key_encrypted") or e.get("key")]

    def get_one(self, platform: str) -> Optional[str]:
        keys = self.get_keys(platform)
        return keys[0] if keys else None

    def list_platforms(self) -> Dict[str, int]:
        return {p: len(v) for p, v in self._data.items()}

    def export_masked(self) -> dict:
        """عرض بدون كشف المفاتيح"""
        out = {}
        for p, entries in self._data.items():
            out[p] = []
            for e in entries:
                masked = (e.get("key") or "")[:4] + "****" if e.get("key") else "****"
                out[p].append({
                    "account_id": e.get("account_id"),
                    "email": e.get("email"),
                    "created_at": e.get("created_at"),
                    "masked": masked
                })
        return out

secure_vault = SecureVault()


# ============================================================
# Compatibility patch: add get_next_key
# ============================================================
def _get_next_key(self, platform: str):
    """Rotation-friendly alias: returns next key for platform."""
    keys = self.get_keys(platform)
    if not keys:
        return None
    # Simple rotation via round-robin index
    idx = getattr(self, "_rotation_idx", {})
    i = idx.get(platform, 0) % len(keys)
    idx[platform] = i + 1
    self._rotation_idx = idx
    return keys[i]


def _get_keys_safe(self, platform: str):
    """Safe alias (returns list)."""
    try:
        return self.get_keys(platform)
    except Exception:
        return []


# Attach to class (works for existing + new instances)
SecureVault.get_next_key = _get_next_key
SecureVault.get_keys = _get_keys_safe
