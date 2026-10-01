"""Notifier — يرسل رسائل للمالك عبر Telegram (بدون polling)."""
from __future__ import annotations
import os, logging
from typing import Optional
import httpx

logger = logging.getLogger(__name__)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_OWNER_ID", "")

S = {"start":"◈","ping":"◯","status":"◎","cve":"⌖","report":"⎔",
     "merge":"⊞","run":"⬡","watch":"◬","ok":"✓","fail":"✗",
     "next":"»","div":"│","bell":"◬"}


def send(text: str, silent: bool = False) -> bool:
    """يرسل رسالة للمالك."""
    if not TOKEN or not CHAT_ID:
        logger.warning("[notifier] TELEGRAM_BOT_TOKEN/OWNER_ID missing")
        return False
    try:
        r = httpx.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={
                "chat_id": CHAT_ID,
                "text": text[:4000],
                "parse_mode": "HTML",
                "disable_notification": silent,
            },
            timeout=15,
        )
        return r.status_code == 200
    except Exception as e:
        logger.warning(f"[notifier] send failed: {e}")
        return False


def notify_start():
    send(f"{S['start']} <b>Marsad بدأ</b>", silent=True)


def notify_stop():
    send(f"{S['fail']} <b>Marsad توقف</b>")


def notify_promotion(from_tier: int, to_tier: int, avg_score: float):
    send(f"{S['ok']} <b>ترقية Curriculum</b>\n"
         f"{S['div']} من Tier-{from_tier} → Tier-{to_tier}\n"
         f"{S['div']} متوسط: {avg_score:.1f}/100")


def notify_cve_high(cve: str, cvss: float):
    send(f"{S['cve']} <b>CVE جديد حرج</b>\n"
         f"{S['div']} {cve}\n"
         f"{S['div']} CVSS: {cvss}/10")


def notify_kaggle_restart():
    send(f"{S['watch']} Kaggle أُعيد تشغيله")


def notify_hourly(status: dict):
    send(f"{S['status']} <b>تقرير كل ساعة</b>\n"
         f"{S['div']} round: {status.get('round', '?')}\n"
         f"{S['div']} tier: {status.get('tier', '?')}\n"
         f"{S['div']} last: {status.get('last_score', '?')}/100\n"
         f"{S['div']} avg: {status.get('avg_recent', 0):.1f}/100",
         silent=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("test:", send("◈ <b>اختبار Notifier</b>"))
