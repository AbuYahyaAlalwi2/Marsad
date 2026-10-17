#!/usr/bin/env python3
import os, requests

ENV_PATH = os.path.expanduser("~/.marsad_secrets/all.env")

def load_env(path):
    env = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env

env = load_env(ENV_PATH)
print("=" * 50)

kaggle_user = env.get("KAGGLE_USERNAME") or env.get("KAGGLE_USERNAME_1")
kernel_slug = "kaggle-debug-kernel"
if kaggle_user:
    url = f"https://www.kaggle.com/code/{kaggle_user}/{kernel_slug}"
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"}, allow_redirects=True)
        if r.status_code == 200 and "login" not in r.url.lower():
            print(f"خطر: {url} يبدو PUBLIC (وصلنا له بدون تسجيل دخول).")
        else:
            print(f"تمام: {url} غير مرئي بدون تسجيل دخول (status={r.status_code}).")
    except Exception as e:
        print(f"تعذر الفحص: {e}")
else:
    print("لم أجد KAGGLE_USERNAME في الملف.")

print("-" * 50)

u4 = env.get("KAGGLE_USERNAME_4")
if u4:
    r = requests.get(f"https://www.kaggle.com/{u4}", timeout=15, headers={"User-Agent": "Mozilla/5.0"})
    print(f"KAGGLE_USERNAME_4 = '{u4}' -> {'موجود' if r.status_code == 200 else f'غير صالح status={r.status_code}'}")
else:
    print("KAGGLE_USERNAME_4 غير موجود بالملف.")

print("-" * 50)

tg = env.get("TELEGRAM_BOT_TOKEN")
if tg:
    try:
        r = requests.get(f"https://api.telegram.org/bot{tg}/getMe", timeout=15)
        data = r.json()
        if data.get("ok"):
            bot = data["result"]
            print(f"TELEGRAM_BOT_TOKEN صالح، اسم البوت: @{bot.get('username')}")
            print("تحذير: إذا ما تتذكر إنشاء هذا البوت، دوّر التوكن من BotFather فوراً.")
        else:
            print(f"TELEGRAM_BOT_TOKEN غير صالح: {data}")
    except Exception as e:
        print(f"تعذر فحص التوكن: {e}")
else:
    print("لا يوجد TELEGRAM_BOT_TOKEN بالملف.")

print("=" * 50)
