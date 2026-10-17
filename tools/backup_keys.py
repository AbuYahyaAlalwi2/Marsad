"""backup_keys.py — نسخة احتياطية مشفرة من all.env إلى HF خاص."""
import re, os, json, base64, urllib.request, urllib.error, tarfile, io
from pathlib import Path
from datetime import datetime
from cryptography.fernet import Fernet

SRC = Path.home() / ".marsad_secrets" / "all.env"
BACKUP_DIR = Path.home() / ".marsad_secrets" / "backups"
BACKUP_DIR.mkdir(exist_ok=True)
KEY_FILE = Path.home() / ".marsad_secrets" / ".backup.key"

# 1. مفتاح التشفير
if not KEY_FILE.exists():
    KEY_FILE.write_bytes(Fernet.generate_key())
    KEY_FILE.chmod(0o600)
    print(f"🔑 مفتاح تشفير جديد: {KEY_FILE}")
    print("   ⚠️  احفظ هذا الملف في مكان آخر — بدونه لا يمكن فك التشفير")
else:
    print(f"🔑 مفتاح تشفير موجود: {KEY_FILE}")

fernet = Fernet(KEY_FILE.read_bytes())

# 2. نسخة محلية مشفرة
data = SRC.read_bytes()
encrypted = fernet.encrypt(data)
stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
local_backup = BACKUP_DIR / f"all.env.{stamp}.enc"
local_backup.write_bytes(encrypted)
local_backup.chmod(0o600)
print(f"✓ نسخة محلية: {local_backup} ({len(encrypted)} bytes)")

# 3. ابحث عن مفتاح HF
env = {}
for line in data.decode().splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")

hf_token = env.get("HF_TOKEN_1")
if not hf_token:
    print("❌ HF_TOKEN_1 غير موجود — تخطي الرفع")
    exit(1)

# 4. ارفع كنسخة سرية على HF
REPO = "AbuYahya2/marsad-secrets"
try:
    from huggingface_hub import HfApi, create_repo
    api = HfApi(token=hf_token)
    try:
        create_repo(repo_id=REPO, repo_type="dataset", token=hf_token, private=True, exist_ok=True)
    except Exception as e:
        print(f"  (create_repo: {e})")

    # ارفع الـ enc
    api.upload_file(
        path_or_fileobj=str(local_backup),
        path_in_repo=f"backups/{local_backup.name}",
        repo_id=REPO, repo_type="dataset"
    )
    print(f"✓ رُفع إلى HF: {REPO}/backups/{local_backup.name}")

    # ارفع الـ key أيضاً (نسخة احتياطية داخل HF)
    # ⚠️ خطر: لو حساب HF مكشوف، كل شيء يُفك
    # البديل: احفظ المفتاح يدوياً
    print()
    print("⚠️  مفتاح التشفير:")
    print(f"   {KEY_FILE}")
    print("   احفظ نسخة يدوياً في:")
    print("   - بريدك الإلكتروني")
    print("   - مدير كلمات مرور")
    print("   - ورقة مكتوبة في مكان آمن")
    print("   ❌ لا ترفعه إلى HF")

except ImportError:
    print("❌ huggingface_hub غير مثبت")
    print("   shغّل: pip install huggingface_hub")
except Exception as e:
    print(f"❌ فشل الرفع: {e}")

# 5. عرض
print(f"\n=== الملفات الناتجة ===")
print(f"  المصدر:     {SRC}")
print(f"  النسخة:     {local_backup}")
print(f"  المفتاح:    {KEY_FILE}")
print(f"\n=== للاستعادة ===")
print(f"  cp {local_backup} /tmp/restore.enc")
print(f"  python3 -c \"from cryptography.fernet import Fernet; from pathlib import Path; k=Fernet(Path('{KEY_FILE}').read_bytes()); open('{SRC}', 'wb').write(k.decrypt(Path('/tmp/restore.enc').read_bytes()))\"")
