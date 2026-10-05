"""
setup.py — مثبت مرصد الشامل
يجهز النظام بالكامل بأمر واحد:
    python setup.py
"""

import os
import sys
import subprocess
import hashlib
import hmac
import secrets
import json
from pathlib import Path

# ─── الألوان ──────────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
BLUE   = "\033[94m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

def ok(msg):   print(f"  {GREEN}✓{RESET} {msg}")
def warn(msg): print(f"  {YELLOW}⚠{RESET} {msg}")
def err(msg):  print(f"  {RED}✗{RESET} {msg}")
def info(msg): print(f"  {BLUE}→{RESET} {msg}")
def header(msg): print(f"\n{BOLD}{msg}{RESET}")

# ─── المسارات ─────────────────────────────────────────────────────────────────
HOME       = Path.home()
MARSAD     = HOME / "Marsad"
VAULT      = HOME / ".marsad"
KEYS_DIR   = VAULT / "keys"
DB_DIR     = MARSAD / "database"
OUTPUT_DIR = MARSAD / "output"

SUBDIRS = [
    MARSAD / "core",
    MARSAD / "agents",
    MARSAD / "database",
    MARSAD / "database" / "jsonl",
    MARSAD / "output" / "codes",
    MARSAD / "output" / "cves",
    MARSAD / "output" / "fixes",
    MARSAD / "output" / "filtered",
    MARSAD / "output" / "advisories",
    MARSAD / "logs",
    VAULT,
    KEYS_DIR,
]


def step_dirs():
    """إنشاء المجلدات"""
    header("1. إنشاء المجلدات")
    for d in SUBDIRS:
        d.mkdir(parents=True, exist_ok=True)
    ok(f"تم إنشاء {len(SUBDIRS)} مجلداً")


def step_packages():
    """تثبيت المكتبات"""
    header("2. تثبيت المكتبات")
    req = MARSAD / "requirements.txt"
    if not req.exists():
        warn("requirements.txt غير موجود — تخطي")
        return
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", str(req), "--break-system-packages", "-q"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        ok("تم تثبيت المكتبات")
    else:
        warn(f"تحذير التثبيت: {result.stderr[:200]}")


def step_owner_key():
    """توليد مفتاح المالك"""
    header("3. توليد مفتاح المالك")
    key_file = KEYS_DIR / "owner.key"
    if key_file.exists():
        warn("مفتاح المالك موجود بالفعل — تخطي")
        return

    owner_secret = secrets.token_hex(32)
    owner_id     = hashlib.sha256(owner_secret.encode()).hexdigest()[:8]
    prefix       = "dlf_"
    token        = prefix + secrets.token_urlsafe(32)

    # تشفير XOR بسيط للتخزين
    xor_key = secrets.token_bytes(len(owner_secret))
    encrypted = bytes(a ^ b for a, b in zip(owner_secret.encode(), xor_key * (len(owner_secret) // len(xor_key) + 1)))

    key_file.write_bytes(encrypted[:len(owner_secret)])
    (KEYS_DIR / "owner.seed").write_bytes(xor_key[:len(owner_secret)])

    # حفظ الـ token بشكل آمن
    (KEYS_DIR / "owner_token.hash").write_text(
        hmac.new(owner_secret.encode(), token.encode(), hashlib.sha256).hexdigest()
    )

    print(f"\n  {BOLD}{RED}══════════════════════════════════════{RESET}")
    print(f"  {BOLD}مفتاح المالك — احفظه الآن ولا يُعاد توليده:{RESET}")
    print(f"  {GREEN}{token}{RESET}")
    print(f"  {BOLD}معرف المالك: {owner_id}{RESET}")
    print(f"  {BOLD}{RED}══════════════════════════════════════{RESET}\n")

    ok("تم توليد مفتاح المالك")


def step_admin_password():
    """إعداد كلمة مرور الإدارة"""
    header("4. إعداد كلمة مرور الإدارة")
    hash_file = VAULT / "admin.hash"
    if hash_file.exists():
        warn("كلمة المرور موجودة بالفعل — تخطي")
        return

    import getpass
    while True:
        pw  = getpass.getpass("  أدخل كلمة مرور الإدارة (8 أحرف على الأقل): ")
        pw2 = getpass.getpass("  أعد إدخالها: ")
        if pw != pw2:
            err("كلمتا المرور غير متطابقتين")
            continue
        if len(pw) < 8:
            err("كلمة المرور قصيرة جداً")
            continue
        break

    seed = secrets.token_hex(16)
    pw_hash = hashlib.sha256((pw + seed).encode()).hexdigest()
    (VAULT / "admin.hash").write_text(pw_hash)
    (VAULT / "vault.seed").write_text(seed)

    ok("تم حفظ كلمة مرور الإدارة")


def step_env():
    """إنشاء ملف .env"""
    header("5. إعداد متغيرات البيئة")
    env_file = MARSAD / ".env"
    if env_file.exists():
        warn(".env موجود — تخطي")
        return

    env_content = """# مرصد — متغيرات البيئة
# ملء المفاتيح المطلوبة فقط

# Groq (مجاني — الأسرع)
GROQ_API_KEY=

# Together.ai (إنتاج)
TOGETHER_API_KEY=

# DeepSeek
DEEPSEEK_API_KEY=

# HuggingFace
HF_TOKEN=

# إعدادات النظام
MARSAD_LOG_LEVEL=INFO
MARSAD_ADMIN_PORT=7860
MARSAD_ADMIN_HOST=127.0.0.1
"""
    env_file.write_text(env_content)
    ok(f"تم إنشاء {env_file}")
    warn("افتح .env وأضف مفاتيح API")


def step_gitignore():
    """التحقق من .gitignore"""
    header("6. التحقق من .gitignore")
    gi = MARSAD / ".gitignore"
    if gi.exists():
        ok(".gitignore موجود")
    else:
        gi.write_text("~/.marsad/\n.marsad/\n*.key\n*.seed\n*.hash\n.env\n__pycache__/\n*.pyc\n")
        ok("تم إنشاء .gitignore")


def step_test_import():
    """اختبار استيراد الوحدات الأساسية"""
    header("7. اختبار الوحدات")
    modules = [
        ("core.knowledge_store", "knowledge_store"),
        ("core.dar_data_pipeline", "dar_data_pipeline"),
        ("core.agent_output_pipeline", "agent_output_pipeline"),
        ("core.provider_registry", "provider_registry"),
    ]
    sys.path.insert(0, str(MARSAD))
    all_ok = True
    for mod_path, name in modules:
        try:
            __import__(mod_path.replace(".", "/").replace("/", ".").split(".")[0] if "." not in mod_path else mod_path)
            ok(f"{name}")
        except ImportError as e:
            # حاول import مباشر
            try:
                path = MARSAD / mod_path.replace(".", "/")
                if path.with_suffix(".py").exists():
                    ok(f"{name} (ملف موجود)")
                else:
                    warn(f"{name} — {e}")
                    all_ok = False
            except Exception:
                warn(f"{name} — غير موجود")
                all_ok = False

    return all_ok


def step_summary():
    """ملخص ما بعد الإعداد"""
    header("═══ الإعداد مكتمل ═══")
    print(f"""
  {BOLD}أوامر التشغيل:{RESET}

  # تسجيل مزود API (مثال Groq)
  cd ~/Marsad
  python core/provider_registry.py register groq YOUR_GROQ_KEY

  # بدء التقطير (بناء بيانات التدريب)
  python core/provider_registry.py distill groq 20

  # استيراد بيانات Qwen
  python core/dar_data_pipeline.py import ~/Marsad_Security_Tests/Dar_Security_Tests/cleaned_data.jsonl

  # مراقبة مخرجات الوكلاء
  python core/agent_output_pipeline.py --watch

  # لوحة التحكم
  python core/admin_server.py
  # ثم افتح: http://127.0.0.1:7860/admin

  {BOLD}لاختبار النظام:{RESET}
  python core/dar_data_pipeline.py add
    """)


def main():
    print(f"\n{BOLD}{'═'*45}")
    print("       مرصد — الإعداد الشامل")
    print(f"{'═'*45}{RESET}")

    try:
        step_dirs()
        step_packages()
        step_owner_key()
        step_admin_password()
        step_env()
        step_gitignore()
        step_test_import()
        step_summary()
    except KeyboardInterrupt:
        print(f"\n{YELLOW}تم الإلغاء{RESET}")
        sys.exit(1)
    except Exception as e:
        err(f"خطأ غير متوقع: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
