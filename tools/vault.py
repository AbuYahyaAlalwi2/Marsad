"""vault.py — خزنة مشفرة موحدة لكل المفاتيح.
الاستخدام:
  python vault.py import ~/path/to/keys_file   ← يستورد كل المفاتيح
  python vault.py list                          ← يعرض الأسماء فقط
  python vault.py get GROQ_API_KEY              ← يعيد قيمة مفتاح
  python vault.py export ~/backup.vault         ← نسخة للنسخ الاحتياطي
  python vault.py load ~/backup.vault           ← استيراد نسخة
  python vault.py inject                        ← يصدّرها لمتغيرات البيئة
"""
import sys, json, os, base64
from pathlib import Path
from cryptography.fernet import Fernet

VAULT_DIR = Path.home() / ".marsad_secrets"
VAULT_ENC = VAULT_DIR / "vault.enc"
VAULT_KEY = VAULT_DIR / ".vault.key"

def _fernet():
    if not VAULT_KEY.exists():
        VAULT_KEY.write_bytes(Fernet.generate_key())
        VAULT_KEY.chmod(0o600)
    return Fernet(VAULT_KEY.read_bytes())

def _load():
    if not VAULT_ENC.exists():
        return {}
    try:
        return json.loads(_fernet().decrypt(VAULT_ENC.read_bytes()))
    except Exception:
        return {}

def _save(d):
    VAULT_ENC.write_bytes(_fernet().encrypt(json.dumps(d, ensure_ascii=False).encode()))
    VAULT_ENC.chmod(0o600)

def cmd_import(path):
    """يستورد من ملف .env (KEY=VALUE) أو JSON."""
    src = Path(path).expanduser()
    if not src.exists():
        print(f"❌ not found: {src}"); return
    text = src.read_text()
    data = _load()
    added, updated = 0, 0
    if src.suffix == ".json":
        new = json.loads(text)
        for k, v in new.items():
            if k in data: updated += 1
            else: added += 1
            data[k] = v
    else:
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k in data: updated += 1
            else: added += 1
            data[k] = v
    _save(data)
    print(f"✓ imported: {added} new, {updated} updated")
    print(f"  vault total: {len(data)} keys")

def cmd_add(key, value):
    data = _load()
    data[key] = value
    _save(data)
    print(f"✓ added {key}")

def cmd_list():
    data = _load()
    print(f"=== vault: {len(data)} keys ===")
    for k in sorted(data.keys()):
        v = data[k]
        preview = (v[:6] + "***") if len(v) > 6 else "***"
        print(f"  {k:35s} {preview}")

def cmd_get(key):
    v = _load().get(key)
    if v: print(v)
    else: sys.exit(1)

def cmd_export(dest):
    src = _load()
    dest = Path(dest).expanduser()
    dest.write_bytes(json.dumps(src, ensure_ascii=False).encode())
    print(f"✓ plain export: {dest} ({len(src)} keys)")
    print("⚠️  احذفه بعد الاستخدام — غير مشفّر")

def cmd_export_enc(dest):
    src = VAULT_ENC.read_bytes()
    dest = Path(dest).expanduser()
    dest.write_bytes(src)
    print(f"✓ encrypted export: {dest}")
    print(f"  يحتاج .vault.key لفتحه")

def cmd_load(src):
    src = Path(src).expanduser()
    data = json.loads(src.read_text())
    _save(data)
    print(f"✓ loaded {len(data)} keys from {src}")

def cmd_inject():
    """يطبع export statements — استخدمه: eval $(python vault.py inject)"""
    for k, v in _load().items():
        print(f'export {k}="{v}"')

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(0)
    c = sys.argv[1]
    args = sys.argv[2:]
    if c == "import":   cmd_import(args[0])
    elif c == "add":    cmd_add(args[0], args[1])
    elif c == "list":   cmd_list()
    elif c == "get":    cmd_get(args[0])
    elif c == "export": cmd_export(args[0])
    elif c == "export-enc": cmd_export_enc(args[0])
    elif c == "load":   cmd_load(args[0])
    elif c == "inject": cmd_inject()
    else: print(f"unknown: {c}")
