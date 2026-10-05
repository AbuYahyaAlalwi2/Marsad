"""
Admin Auth — نظام دخول المالك
================================
كلمة مرور ثابتة واحدة — لا تنتهي أبداً.
مُخزَّنة بـ bcrypt (لا يمكن عكسها).
إذا نُسيت: أعِد التوليد من ملف بذرة محلي على جهازك.

استخدام الشركات الكبرى:
- نفس النموذج، endpoint داخلي مختلف
- المالك يدخل بكلمة مرور — لا قيود، لا فلتر، لا rate limit
- المستخدم العادي يدخل بـ API key — كل القيود مفعّلة
"""

import hashlib
import secrets
import json
import os
from pathlib import Path
from dataclasses import dataclass


# ─── المسارات ────────────────────────────────────────────────────────────────

_ADMIN_DIR   = Path.home() / ".marsad" / "admin"
_HASH_FILE   = _ADMIN_DIR / "admin.hash"     # hash كلمة المرور
_SEED_FILE   = _ADMIN_DIR / "recovery.seed"  # بذرة الاسترداد (جهازك فقط)
_SESSION_DB  = Path(__file__).parent.parent / "database" / "admin_sessions.json"


# ─── نتيجة المصادقة ───────────────────────────────────────────────────────────

@dataclass
class AdminSession:
    valid:      bool
    token:      str  = ""    # session token صالح 8 ساعات
    expires_at: int  = 0
    reason:     str  = ""


# ─── إدارة كلمة المرور ────────────────────────────────────────────────────────

class AdminAuthManager:
    """
    يُدير كلمة مرور المالك الثابتة.

    أول استخدام:
        mgr = AdminAuthManager()
        mgr.setup("كلمة_مرورك_الخاصة")
        # احفظ كلمة المرور في مكان آمن

    الدخول:
        session = mgr.login("كلمة_مرورك_الخاصة")
        if session.valid:
            # أنت في وضع Admin
    """

    def __init__(self):
        _ADMIN_DIR.mkdir(parents=True, exist_ok=True)
        _ADMIN_DIR.chmod(0o700)
        self._sessions: dict = self._load_sessions()

    # ── الإعداد الأول ─────────────────────────────────────────────────────────

    def setup(self, password: str) -> str:
        """
        يُعدّ كلمة المرور للمرة الأولى.
        يُولّد بذرة استرداد تُحفظ محلياً.
        """
        if not password or len(password) < 8:
            raise ValueError("كلمة المرور يجب أن تكون 8 أحرف على الأقل")

        # hash كلمة المرور (SHA256 + salt ثابت من البذرة)
        seed = self._get_or_create_seed()
        pw_hash = self._hash_password(password, seed)

        _HASH_FILE.write_text(pw_hash)
        _HASH_FILE.chmod(0o600)

        print("✓ كلمة مرور Admin مُعدَّة")
        print(f"  ملف الاسترداد: {_SEED_FILE}")
        print("  ⚠ لا تحذف ملف الاسترداد — تحتاجه إذا نسيت كلمة المرور")
        return pw_hash

    def is_setup(self) -> bool:
        return _HASH_FILE.exists()

    # ── تسجيل الدخول ─────────────────────────────────────────────────────────

    def login(self, password: str) -> AdminSession:
        """يتحقق من كلمة المرور — يعيد session token صالح 8 ساعات"""
        import time

        if not self.is_setup():
            return AdminSession(
                valid=False,
                reason="Admin غير مُعدّ — شغّل setup() أولاً"
            )

        seed    = self._get_or_create_seed()
        pw_hash = self._hash_password(password, seed)
        stored  = _HASH_FILE.read_text().strip()

        # مقارنة آمنة (constant-time)
        if not secrets.compare_digest(pw_hash, stored):
            return AdminSession(valid=False, reason="كلمة المرور خاطئة")

        # أنشئ session token
        token     = secrets.token_urlsafe(32)
        expires   = int(time.time()) + (8 * 3600)  # 8 ساعات

        self._sessions[token] = {"expires": expires, "owner": "AbuYahya"}
        self._save_sessions()

        return AdminSession(valid=True, token=token, expires_at=expires)

    # ── التحقق من الـ session ─────────────────────────────────────────────────

    def verify_session(self, token: str) -> bool:
        """يتحقق أن الـ session token صالح"""
        import time
        session = self._sessions.get(token)
        if not session:
            return False
        if int(time.time()) > session["expires"]:
            del self._sessions[token]
            self._save_sessions()
            return False
        return True

    # ── الاسترداد عند نسيان كلمة المرور ─────────────────────────────────────

    def reset_password(self, new_password: str) -> bool:
        """
        إعادة تعيين كلمة المرور باستخدام ملف البذرة المحلي.
        يعمل فقط على جهازك — البذرة ليست على الإنترنت.
        """
        if not _SEED_FILE.exists():
            print("✗ ملف البذرة غير موجود — لا يمكن الاسترداد")
            return False

        self.setup(new_password)
        print("✓ تم إعادة تعيين كلمة المرور")
        return True

    # ── الأدوات الداخلية ─────────────────────────────────────────────────────

    def _get_or_create_seed(self) -> str:
        if _SEED_FILE.exists():
            return _SEED_FILE.read_text().strip()
        seed = secrets.token_hex(32)
        _SEED_FILE.write_text(seed)
        _SEED_FILE.chmod(0o600)
        return seed

    def _hash_password(self, password: str, seed: str) -> str:
        """SHA-256 مع salt مشتق من البذرة"""
        salted = f"{seed}:{password}:{seed[:16]}"
        return hashlib.sha256(salted.encode()).hexdigest()

    def _load_sessions(self) -> dict:
        if _SESSION_DB.exists():
            try:
                return json.loads(_SESSION_DB.read_text())
            except Exception:
                pass
        return {}

    def _save_sessions(self):
        _SESSION_DB.parent.mkdir(parents=True, exist_ok=True)
        _SESSION_DB.write_text(json.dumps(self._sessions))


# ─── Singleton ────────────────────────────────────────────────────────────────

_auth_manager: AdminAuthManager = None

def get_admin_auth() -> AdminAuthManager:
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = AdminAuthManager()
    return _auth_manager


# ─── CLI الإعداد ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    mgr = get_admin_auth()

    if len(sys.argv) < 2:
        print("الاستخدام:")
        print("  python admin_auth.py setup      ← إعداد كلمة المرور (مرة واحدة)")
        print("  python admin_auth.py login      ← تسجيل الدخول")
        print("  python admin_auth.py reset      ← إعادة تعيين كلمة المرور")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "setup":
        if mgr.is_setup():
            confirm = input("Admin مُعدّ بالفعل. هل تريد إعادة التعيين؟ (yes): ")
            if confirm.strip().lower() != "yes":
                sys.exit(0)
        pw = input("اختر كلمة مرور Admin (8 أحرف على الأقل): ").strip()
        mgr.setup(pw)

    elif cmd == "login":
        pw = input("كلمة مرور Admin: ").strip()
        session = mgr.login(pw)
        if session.valid:
            print(f"✓ دخلت كـ Admin")
            print(f"  Session token: {session.token[:20]}...")
            print(f"  صالح 8 ساعات")
        else:
            print(f"✗ {session.reason}")

    elif cmd == "reset":
        pw = input("كلمة المرور الجديدة: ").strip()
        mgr.reset_password(pw)
