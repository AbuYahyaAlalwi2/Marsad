"""Hooks — أحداث تستدعي الإشعارات تلقائياً."""
from __future__ import annotations
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)


class Hooks:
    """يربط الأحداث بالإشعارات."""

    def __init__(self):
        self._last_scores = []
        self._notified_cves = set()
        self._kaggle_last_ok = None

    # ─── Self-Play ────────────────────────────────
    def on_round_complete(self, round_num: int, tier: int,
                           cve: str, score: int, avg: float):
        """يُستدعى بعد كل جولة."""
        self._last_scores.append(score)
        self._last_scores = self._last_scores[-20:]

        # إشعار عند الترقية
        if avg >= 70 and self._should_promote_hint(tier):
            try:
                from tools.notifier import notify_promotion
                notify_promotion(tier, tier + 1, avg)
                logger.info(f"[hooks] promotion notification sent")
            except Exception as e:
                logger.warning(f"[hooks] promotion notify failed: {e}")

    def _should_promote_hint(self, tier: int) -> bool:
        """يمنع الإشعار المتكرر."""
        key = f"promote_{tier}_{int(time.time() // 3600)}"
        if not hasattr(self, "_promote_sent"):
            self._promote_sent = set()
        if key in self._promote_sent:
            return False
        self._promote_sent.add(key)
        return True

    def on_self_play_start(self):
        try:
            from tools.notifier import send, S
            send(f"{S['watch']} <b>Self-Play بدأ</b>")
        except Exception:
            pass

    def on_self_play_stop(self, rounds: int, final_tier: int):
        try:
            from tools.notifier import send, S
            send(f"{S['ok']} <b>Self-Play انتهى</b>\n"
                 f"{S['div']} جولات: {rounds}\n"
                 f"{S['div']} آخر صف: Tier-{final_tier}")
        except Exception:
            pass

    # ─── CVE Discovery ────────────────────────────
    def on_new_cve(self, cve: str, cvss: float):
        """إشعار عند CVE حرج."""
        if cve in self._notified_cves:
            return
        if cvss < 9.0:
            return
        self._notified_cves.add(cve)
        try:
            from tools.notifier import notify_cve_high
            notify_cve_high(cve, cvss)
        except Exception:
            pass

    # ─── Kaggle ───────────────────────────────────
    def on_kaggle_restart(self):
        try:
            from tools.notifier import notify_kaggle_restart
            notify_kaggle_restart()
        except Exception:
            pass

    def on_kaggle_alive(self):
        """يلاحظ عودة Kaggle بعد انقطاع."""
        if self._kaggle_last_ok is False:
            try:
                from tools.notifier import send, S
                send(f"{S['ok']} Kaggle عاد للعمل")
            except Exception:
                pass
        self._kaggle_last_ok = True

    def on_kaggle_dead(self):
        self._kaggle_last_ok = False

    # ─── Cloudflare ───────────────────────────────
    def on_cf_fail(self, account: str, reason: str):
        try:
            from tools.notifier import send, S
            send(f"{S['fail']} <b>CF {account} فشل</b>\n"
                 f"{S['div']} {reason[:200]}")
        except Exception:
            pass

    # ─── Generic ──────────────────────────────────
    def on_error(self, source: str, error: str):
        try:
            from tools.notifier import send, S
            send(f"{S['fail']} <b>{source}</b>\n"
                 f"{S['div']} {error[:300]}")
        except Exception:
            pass


# Singleton
hooks = Hooks()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    hooks.on_round_complete(1, 0, "CVE-2021-44228", 75, 72)
    hooks.on_new_cve("CVE-2024-9999", 9.8)
    print("✓ hooks loaded")
