"""test_kaggle_keys.py — يتحقق من مفاتيح Kaggle."""
import subprocess, sys, os

def test_kaggle(username, key, label):
    env = os.environ.copy()
    env["KAGGLE_USERNAME"] = username
    env["KAGGLE_KEY"] = key

    code = (
        "from kaggle.api.kaggle_api_extended import KaggleApi; "
        "api = KaggleApi(); api.authenticate(); "
        "print('AUTH_OK')"
    )
    try:
        r = subprocess.run([sys.executable, "-c", code],
                           capture_output=True, text=True, env=env, timeout=30)
    except subprocess.TimeoutExpired:
        print(f"{label}: ❌ timeout")
        return False

    ok = "AUTH_OK" in r.stdout
    print(f"{label}: {'✅ يعمل' if ok else '❌ فشل'}")
    if not ok:
        err = (r.stderr or r.stdout)[-300:]
        print(f"  error: {err}")
    return ok


if __name__ == "__main__":
    # الحساب 1
    print("── الحساب 1 ──")
    u1 = input("USERNAME_1: ").strip()
    k1 = input("KEY_1: ").strip()
    ok1 = test_kaggle(u1, k1, "Account 1")

    print()
    print("── الحساب 2 ──")
    u2 = input("USERNAME_2: ").strip()
    k2 = input("KEY_2: ").strip()
    ok2 = test_kaggle(u2, k2, "Account 2")

    print()
    print("═" * 40)
    if ok1 and ok2:
        print("✅ كلا الحسابين يعملان")
    else:
        print("⚠️ على الأقل حساب واحد فشل")
