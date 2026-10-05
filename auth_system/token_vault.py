"""
Token Vault — الخزنة المشفرة لكل المفاتيح والبيانات الحساسة
يستخدم Fernet (AES-128-CBC + HMAC-SHA256)
"""

import json
import os
import time
from pathlib import Path
from typing import Optional
from cryptography.fernet import Fernet


# ─── Path Resolution ──────────────────────────────────────────────────────────
# BASE_ROOT = مجلد Dolphin (جد مجلد auth بثلاثة مستويات)
# delfin_os/auth/token_vault.py → parent×2 → delfin_os → parent → Dolphin/

BASE_ROOT  = Path(__file__).parent.parent.parent   # Dolphin/
VAULT_DIR  = BASE_ROOT / "delfin_os" / "vault"
VAULT_FILE = VAULT_DIR / "vault.enc"
KEY_FILE   = VAULT_DIR / ".vault_key"


# ─── Key Management ───────────────────────────────────────────────────────────

def _get_or_create_key() -> bytes:
    """يحضر مفتاح التشفير أو ينشئ واحداً جديداً"""
    VAULT_DIR.mkdir(parents=True, exist_ok=True)

    if KEY_FILE.exists():
        return KEY_FILE.read_bytes()

    key = Fernet.generate_key()
    KEY_FILE.write_bytes(key)

    # حماية الملف (Unix فقط — على Windows يُتجاهل)
    try:
        os.chmod(KEY_FILE, 0o600)
    except Exception:
        pass

    return key


def _get_fernet() -> Fernet:
    return Fernet(_get_or_create_key())


# ─── Vault I/O ────────────────────────────────────────────────────────────────

def _load_vault() -> dict:
    if not VAULT_FILE.exists():
        return {}
    try:
        encrypted = VAULT_FILE.read_bytes()
        raw       = _get_fernet().decrypt(encrypted)
        return json.loads(raw.decode())
    except Exception:
        return {}


def _save_vault(data: dict):
    VAULT_DIR.mkdir(parents=True, exist_ok=True)
    raw       = json.dumps(data, ensure_ascii=False).encode()
    encrypted = _get_fernet().encrypt(raw)
    VAULT_FILE.write_bytes(encrypted)


# ─── Public API ───────────────────────────────────────────────────────────────

def save_credential(service: str, key: str, value: str, metadata: dict = None):
    """يحفظ قيمة مشفرة في الـ Vault"""
    vault = _load_vault()
    if service not in vault:
        vault[service] = {}

    vault[service][key] = {
        "value":    value,
        "saved_at": time.time(),
        "meta":     metadata or {},
    }
    _save_vault(vault)


def get_credential(service: str, key: str) -> Optional[str]:
    """يسترجع قيمة من الـ Vault (أو None)"""
    vault = _load_vault()
    try:
        return vault[service][key]["value"]
    except KeyError:
        return None


def list_services() -> list[dict]:
    """يعرض كل الخدمات المحفوظة مع preview مختصر"""
    vault = _load_vault()
    result = []
    for service, keys in vault.items():
        for key, data in keys.items():
            v = data.get("value", "")
            result.append({
                "service":  service,
                "key":      key,
                "preview":  v[:8] + "***" if len(v) > 8 else "***",
                "saved_at": data.get("saved_at", 0),
            })
    return result


def delete_credential(service: str, key: str) -> bool:
    """يحذف credential محدد"""
    vault = _load_vault()
    if service in vault and key in vault[service]:
        del vault[service][key]
        if not vault[service]:
            del vault[service]
        _save_vault(vault)
        return True
    return False


def export_to_env(path: str = None, services: list[str] = None):
    """
    يصدّر المفاتيح لملف .env
    path: مسار الملف (افتراضي: BASE_ROOT/.env)
    services: قائمة الخدمات (None = كلها)
    """
    from provider_registry import PROVIDERS

    env_path = Path(path) if path else BASE_ROOT / ".env"
    vault    = _load_vault()

    lines = {}
    # اقرأ السطور الموجودة أولاً
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                lines[k.strip()] = v.strip()

    # أضف/حدّث من الـ Vault
    for service, keys in vault.items():
        if services and service not in services:
            continue
        if service == "user_permissions":
            continue

        provider = PROVIDERS.get(service)
        env_name = provider.env_var if provider else f"{service.upper()}_API_KEY"

        api_key = (
            keys.get("api_key", {}).get("value") or
            keys.get("token",   {}).get("value")
        )
        if api_key:
            lines[env_name] = f'"{api_key}"'

    # اكتب الملف
    env_path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(f"{k}={v}" for k, v in lines.items())
    env_path.write_text(content + "\n", encoding="utf-8")
    print(f"✓ تم التصدير إلى {env_path}")


def inject_to_config(config_path: str = None):
    """
    يحقن المفاتيح في config.json بشكل ديناميكي
    يستخدم env_var من provider_registry لكل مزود
    """
    from provider_registry import PROVIDERS

    cfg_path = Path(config_path) if config_path else BASE_ROOT / "config.json"
    if not cfg_path.exists():
        print(f"⚠ {cfg_path} غير موجود")
        return

    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    vault   = _load_vault()
    updated = 0

    for service, keys in vault.items():
        if service == "user_permissions":
            continue

        provider = PROVIDERS.get(service)
        if not provider:
            continue

        api_key = (
            keys.get("api_key", {}).get("value") or
            keys.get("token",   {}).get("value")
        )
        if not api_key:
            continue

        # ابحث في قائمة النماذج في config.json وحدّث المفتاح
        models = cfg.get("models", [])
        for model in models:
            if model.get("provider", "").lower() == service:
                model["api_key"] = api_key
                updated += 1

        # أضف كـ env var أيضاً
        if "env" not in cfg:
            cfg["env"] = {}
        cfg["env"][provider.env_var] = api_key

    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

    print(f"✓ تم تحديث {updated} نموذج في {cfg_path}")


# ─── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"

    if cmd == "list":
        creds = list_services()
        if not creds:
            print("الـ Vault فارغ")
        else:
            print(f"الـ Vault يحتوي {len(creds)} عنصر:\n")
            for c in creds:
                print(f"  {c['service']:15} {c['key']:15} {c['preview']}")

    elif cmd == "export":
        export_to_env()

    elif cmd == "test":
        # اختبار سريع
        print("اختبار الـ Vault...")
        save_credential("test_service", "test_key", "test_value_abc123")
        val = get_credential("test_service", "test_key")
        assert val == "test_value_abc123", "فشل الاسترجاع!"
        delete_credential("test_service", "test_key")
        assert get_credential("test_service", "test_key") is None
        print("✓ كل الاختبارات نجحت")

    else:
        print(f"أمر غير معروف: {cmd}")
        print("الأوامر: list | export | test")
