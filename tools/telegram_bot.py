"""telegram_bot.py — Marsad CyberAgent Bot (رموز هندسية مفرغة)."""
from __future__ import annotations
import os, logging
from pathlib import Path

try:
    from telegram import Update
    from telegram.ext import (Application, CommandHandler, MessageHandler,
                               filters, ContextTypes)
    _HAS_TG = True
except ImportError:
    _HAS_TG = False

logger = logging.getLogger(__name__)
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
OWNER_ID = int(os.environ.get("TELEGRAM_OWNER_ID", "0") or 0)

# ─── Marsad Symbol Set ───────────────────────────
S = {
    "start":  "◈",
    "ping":   "◯",
    "status": "◎",
    "cve":    "⌖",
    "report": "⎔",
    "merge":  "⊞",
    "run":    "⬡",
    "watch":  "◬",
    "ok":     "✓",
    "fail":   "✗",
    "next":   "»",
    "div":    "│",
}


def _is_owner(update: Update) -> bool:
    if not OWNER_ID:
        return True
    return update.effective_user and update.effective_user.id == OWNER_ID


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _is_owner(update): return
    menu = "\n".join([
        f"{S['start']} Marsad CyberAgent",
        "",
        f"{S['watch']}  /status  {S['div']}  حالة النظام",
        f"{S['cve']}  /cve     {S['div']}  ملخص ثغرة",
        f"{S['report']}  /report  {S['div']}  تقرير PDF",
        f"{S['run']}  /run     {S['div']}  تنفيذ أمر",
        f"{S['merge']}  /merge   {S['div']}  صهر نموذج",
        f"{S['ping']}  /ping    {S['div']}  فحص الاتصال",
    ])
    await update.message.reply_text(menu)


async def cmd_ping(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _is_owner(update): return
    await update.message.reply_text(f"{S['ping']} pong")


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _is_owner(update): return
    try:
        from core.account_pool import account_pool
        s = account_pool.stats()
        lines = [f"{S['status']} Marsad Status", ""]
        for k, v in s.items():
            lines.append(f"{S['div']} {k}: {v['count']} حساب ({v['active']} نشط)")
        await update.message.reply_text("\n".join(lines))
    except Exception as e:
        await update.message.reply_text(f"{S['fail']} {e}")


async def cmd_cve(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _is_owner(update): return
    args = ctx.args
    if not args:
        await update.message.reply_text(f"{S['cve']} usage: /cve CVE-2021-44228")
        return
    cve = args[0]
    await update.message.reply_text(f"{S['watch']} جلب {cve}...")
    try:
        from tools.cyber_senses import threat_summary
        v = threat_summary(cve)
        nvd = v.get("nvd", {})
        cisa = S['ok'] if v.get('cisa_exploited') else S['fail']
        edb = S['ok'] if v.get('exploit_available') else S['fail']
        msg = "\n".join([
            f"{S['cve']} {cve}",
            f"{S['div']} CVSS: {nvd.get('cvss_score', '?')}/10 ({nvd.get('cvss_severity', '?')})",
            f"{S['div']} CISA: {cisa}",
            f"{S['div']} Exploits: {edb}",
            "",
            (nvd.get('description') or '')[:400],
        ])
        await update.message.reply_text(msg)
    except Exception as e:
        await update.message.reply_text(f"{S['fail']} {e}")


async def cmd_report(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _is_owner(update): return
    args = ctx.args
    if not args:
        await update.message.reply_text(f"{S['report']} usage: /report CVE-2021-44228")
        return
    cve = args[0]
    await update.message.reply_text(f"{S['watch']} إنشاء تقرير {cve}...")
    try:
        from tools.cyber_senses import threat_summary
        from tools.report_pdf import build_vulnerability_report
        v = threat_summary(cve)
        path = build_vulnerability_report(v, client_name="الفرقدان")
        with open(path, "rb") as f:
            await update.message.reply_document(document=f,
                                                 filename=Path(path).name)
    except Exception as e:
        await update.message.reply_text(f"{S['fail']} {e}")


async def cmd_run(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _is_owner(update): return
    cmd = " ".join(ctx.args)
    if not cmd:
        await update.message.reply_text(f"{S['run']} usage: /run <command>")
        return
    try:
        from core.tool_calling import registry
        result = registry.execute("run_shell", {"cmd": cmd})
        out = result.get("stdout", "")[:3000]
        err = result.get("stderr", "")[:500]
        msg = f"{S['run']} $ {cmd}\n\n{out}"
        if err:
            msg += f"\n\n{err}"
        await update.message.reply_text(msg[:4000])
    except Exception as e:
        await update.message.reply_text(f"{S['fail']} {e}")


async def cmd_merge(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _is_owner(update): return
    await update.message.reply_text(f"{S['watch']} إطلاق الصهر...")
    try:
        import httpx
        r = httpx.post(
            "https://marsad-dashboard.onrender.com/api/gpu/merge",
            json={"base_model": "deepseek-ai/DeepSeek-R1-Distill-Llama-8B",
                  "repo_id": "AbuYahya2/deepseek-marsad-v3"},
            timeout=60)
        await update.message.reply_text(f"{S['merge']} {r.json()}")
    except Exception as e:
        await update.message.reply_text(f"{S['fail']} {e}")


async def cmd_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _is_owner(update): return
    txt = update.message.text
    await update.message.reply_text(f"{S['watch']} معالجة...")

    def _progress(msg):
        # نرسل تقدم في الخلفية
        logger.info(msg)

    try:
        from core.agent_loop import get_agent
        agent = get_agent()
        result = agent.run(txt, on_step=_progress)
        if result["status"] == "completed":
            out = result.get("final", "")[:3500]
            await update.message.reply_text(
                f"{S['ok']} {result['turns']} جولات\n\n{out}")
        else:
            await update.message.reply_text(
                f"{S['fail']} {result.get('error', 'unknown')[:500]}")
    except Exception as e:
        await update.message.reply_text(f"{S['fail']} {e}")


def run_bot():
    if not _HAS_TG:
        raise RuntimeError("pip install python-telegram-bot")
    if not TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN غير موجود")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("ping", cmd_ping))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("cve", cmd_cve))
    app.add_handler(CommandHandler("report", cmd_report))
    app.add_handler(CommandHandler("run", cmd_run))
    app.add_handler(CommandHandler("merge", cmd_merge))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, cmd_text))
    logger.info("[telegram] starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_bot()
