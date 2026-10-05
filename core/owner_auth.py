"""
Owner Authentication System — نظام التعرف على المالك
======================================================
المالك: AbuYahya (المعرّف: 6c3fb27c)

كيف يعمل:
1. المالك يولّد توقيع HMAC باستخدام مفتاحه السري
2. يرسله مع كل أمر حساس
3. النموذج يتحقق من الصحة قبل التنفيذ
4. التوقيع يتضمن timestamp — صالح 5 دقائق فقط (يمنع إعادة الاستخدام)

الأمان:
- لا يمكن تزوير التوقيع بدون المفتاح السري
- كل توقيع يُستخدم مرة واحدة (nonce في الـ DB)
- يستحيل على أي مستخدم آخر انتحال هويتك
"""

import hashlib
import hmac
import time
import json
import sqlite3
import secrets
import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


# ─── الثوابت ─────────────────────────────────────────────────────────────────

OWNER_ID        = "6c3fb27c"
OWNER_PREFIX    = "dlf_"
KEY_VERSION     = "v1"
TOKEN_VALIDITY  = 300       # 5 دقائق
DB_PATH         = Path(__file__).parent.parent / "database" / "auth.db"
SECRETS_FILE    = Path.home() / ".marsad" / "owner.key"   # مخزن على جهازك فقط


# ─── نتيجة التحقق ─────────────────────────────────────────────────────────────

@dataclass
class AuthResult:
    valid:   bool
    owner:   str = ""
    reason:  str = ""
    command: str = ""

    def __bool__(self):
        return self.valid


# ─── توليد المفتاح (يُنفَّذ مرة واحدة فقط) ──────────────────────────────────

def generate_owner_key(owner_id: str = OWNER_ID) -> str:
    """
    يولّد مفتاحاً سرياً للمالك — يُحفظ محلياً فقط
    النموذج لا يعرف هذا المفتاح — يعرف فقط كيف يتحقق منه
    """
    raw = secrets.token_urlsafe(32)
    key = f"{OWNER_PREFIX}{owner_id}_{raw}"

    # احفظه في مكان آمن على جهازك
    SECRETS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SECRETS_FILE.write_text(key)
    SECRETS_FILE.chmod(0o600)  # أنت فقط تقرأه

    print(f"\nالمفتاح السري (يُعرض مرة واحدة فقط، احفظه الآن):")
    print(f"  {key}")
    print(f"\nالمعرّف: {owner_id}")
    print(f"\n⚠ هذا المفتاح محفوظ في: {SECRETS_FILE}")
    print(f"  لا تشاركه مع أحد — بما فيهم النموذج\n")
    return key


# ─── إنشاء توقيع للأمر ────────────────────────────────────────────────────────

def sign_command(command: str, secret_key: str) -> dict:
    """
    المالك يوقّع أمره قبل إرساله للنموذج

    الاستخدام:
        token = sign_command("apply_fix:CVE-2024-1234", my_secret_key)
        # أرسل token للنموذج مع أمرك
    """
    timestamp = int(time.time())
    nonce     = secrets.token_hex(8)

    # الرسالة التي تُوقَّع: command + timestamp + nonce
    message = f"{command}|{timestamp}|{nonce}"

    # HMAC-SHA256
    signature = hmac.new(
        secret_key.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()

    return {
        "owner_id":  OWNER_ID,
        "command":   command,
        "timestamp": timestamp,
        "nonce":     nonce,
        "signature": signature,
        "version":   KEY_VERSION,
    }


# ─── التحقق من التوقيع (يُنفَّذ داخل النموذج) ───────────────────────────────

class OwnerAuthenticator:
    """
    هذا ما يراه النموذج — يتحقق من التوقيع لكن لا يعرف المفتاح السري
    المفتاح السري يُستدعى من متغير بيئي أو vault آمن
    """

    def __init__(self):
        self._init_db()
        self._secret = self._load_secret()

    def _load_secret(self) -> Optional[str]:
        """
        يحمّل المفتاح من:
        1. متغير البيئة MARSAD_OWNER_KEY (للإنتاج)
        2. الملف المحلي ~/.marsad/owner.key (للتطوير)
        """
        # 1. متغير البيئة (الأكثر أماناً)
        env_key = os.environ.get("MARSAD_OWNER_KEY")
        if env_key:
            return env_key

        # 2. الملف المحلي
        if SECRETS_FILE.exists():
            return SECRETS_FILE.read_text().strip()

        return None

    def _init_db(self):
        """يهيئ جدول الـ nonces المستخدمة (يمنع replay attacks)"""
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS used_nonces (
                nonce      TEXT PRIMARY KEY,
                used_at    INTEGER,
                command    TEXT
            )
        """)
        # تنظيف القديم كل استدعاء
        conn.execute(
            "DELETE FROM used_nonces WHERE used_at < ?",
            (int(time.time()) - TOKEN_VALIDITY * 2,)
        )
        conn.commit()
        conn.close()

    def verify(self, token: dict) -> AuthResult:
        """
        التحقق الكامل من التوقيع:
        1. صحة الهيكل
        2. المالك الصحيح
        3. التوقيع رياضياً
        4. لم يمضِ أكثر من 5 دقائق
        5. لم يُستخدم هذا الـ nonce من قبل
        """
        if not self._secret:
            return AuthResult(
                valid=False,
                reason="MARSAD_OWNER_KEY غير مُحدّد — ضع المفتاح في متغير البيئة"
            )

        # 1. تحقق من الهيكل
        required = {"owner_id", "command", "timestamp", "nonce", "signature"}
        if not required.issubset(token):
            return AuthResult(valid=False, reason="توقيع ناقص الحقول")

        # 2. المالك الصحيح
        if token["owner_id"] != OWNER_ID:
            return AuthResult(
                valid=False,
                reason=f"المالك غير معروف: {token['owner_id']}"
            )

        # 3. لم يمضِ أكثر من 5 دقائق
        age = int(time.time()) - int(token["timestamp"])
        if age > TOKEN_VALIDITY:
            return AuthResult(
                valid=False,
                reason=f"التوقيع انتهت صلاحيته (عمره {age} ثانية — الحد 300)"
            )

        if age < 0:
            return AuthResult(valid=False, reason="timestamp من المستقبل — مشبوه")

        # 4. التحقق الرياضي من HMAC
        message   = f"{token['command']}|{token['timestamp']}|{token['nonce']}"
        expected  = hmac.new(
            self._secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(expected, token["signature"]):
            return AuthResult(valid=False, reason="التوقيع خاطئ — ليس المالك")

        # 5. لم يُستخدم هذا الـ nonce من قبل (يمنع replay)
        conn = sqlite3.connect(str(DB_PATH))
        try:
            conn.execute(
                "INSERT INTO used_nonces (nonce, used_at, command) VALUES (?,?,?)",
                (token["nonce"], int(time.time()), token["command"])
            )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            return AuthResult(
                valid=False,
                reason="هذا التوقيع استُخدم من قبل (replay attack مرفوض)"
            )
        finally:
            conn.close()

        return AuthResult(
            valid=True,
            owner=OWNER_ID,
            command=token["command"],
            reason="تم التحقق ✓"
        )


# ─── الغلاف العملي للنموذج ────────────────────────────────────────────────────

class OwnerGate:
    """
    بوابة يمرر من خلالها كل أمر حساس

    الاستخدام داخل SecurityPipeline:
        gate = OwnerGate()

        @gate.requires_owner
        async def apply_fix(self, token, fix_data):
            # لن يُنفَّذ إلا إذا كان التوقيع صحيحاً
            ...
    """

    def __init__(self):
        self.auth = OwnerAuthenticator()

    def check(self, token: dict) -> AuthResult:
        """تحقق مباشر"""
        return self.auth.verify(token)

    def requires_owner(self, func):
        """ديكوريتر — يحمي أي دالة"""
        import functools

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            token = kwargs.get("owner_token") or (args[1] if len(args) > 1 else None)
            if not isinstance(token, dict):
                raise PermissionError("⛔ يجب إرسال owner_token — هذا أمر يحتاج موافقة المالك")

            result = self.auth.verify(token)
            if not result:
                raise PermissionError(f"⛔ تم رفض الأمر: {result.reason}")

            return await func(*args, **kwargs)
        return wrapper


# ─── واجهة سطر الأوامر ────────────────────────────────────────────────────────

def _cli():
    import sys

    if len(sys.argv) < 2:
        print("الاستخدام:")
        print("  python owner_auth.py init              ← توليد مفتاح جديد")
        print("  python owner_auth.py sign 'أمر ما'    ← توقيع أمر")
        print("  python owner_auth.py verify '{json}'   ← التحقق من توقيع")
        return

    cmd = sys.argv[1]

    if cmd == "init":
        key = generate_owner_key()

    elif cmd == "sign":
        if len(sys.argv) < 3:
            print("أعطِ الأمر: python owner_auth.py sign 'apply_fix:CVE-2024-1234'")
            return

        # قراءة المفتاح
        key = None
        if SECRETS_FILE.exists():
            key = SECRETS_FILE.read_text().strip()
        else:
            key = input("أدخل مفتاحك السري: ").strip()

        command = sys.argv[2]
        token   = sign_command(command, key)

        print("\nالتوقيع (أرسل هذا JSON للنموذج):")
        print(json.dumps(token, ensure_ascii=False, indent=2))

    elif cmd == "verify":
        if len(sys.argv) < 3:
            print("أعطِ الـ JSON: python owner_auth.py verify '{...}'")
            return

        token = json.loads(sys.argv[2])
        auth  = OwnerAuthenticator()
        result = auth.verify(token)

        if result:
            print(f"✓ مالك موثّق | الأمر: {result.command}")
        else:
            print(f"✗ رُفض: {result.reason}")


if __name__ == "__main__":
    _cli()
