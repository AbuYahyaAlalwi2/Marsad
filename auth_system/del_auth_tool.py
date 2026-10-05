"""
Del Auth Tool v2 — واجهة Del الذكية لنظام المصادقة
Del يستدعي handle() بجملة طبيعية ويحصل على رد نصي جاهز
"""

import asyncio
from pathlib import Path
import sys

_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE))

from session_manager   import SessionManager, grant_permission, revoke_permission, has_permission, get_manager
from token_vault       import get_credential, list_services
from provider_registry import PROVIDERS, get_provider, list_providers, get_free_providers


# ─── Del Auth Tool ────────────────────────────────────────────────────────────

class DelAuthTool:
    """
    الواجهة الوحيدة التي يحتاجها Del

    مثال:
        tool = DelAuthTool()

        # المستخدم يقول: "سجّل في Groq وأحضر مفتاح"
        print(tool.handle("سجّل في Groq وأحضر مفتاح"))

        # بعد إعطاء الإذن
        print(tool.handle(
            "أعطِ Del إذن groq",
            user_context={"service": "groq", "email": "x@y.com", "password": "pass"}
        ))
    """

    def __init__(self, headless: bool = False):
        self.mgr = SessionManager(headless=headless)

    def handle(self, user_message: str, user_context: dict = None) -> str:
        """
        يحلل أمر المستخدم ويعيد رد نصي مناسب
        يعمل مع asyncio سواء كان هناك event loop نشط أم لا
        """
        ctx = user_context or {}
        msg = user_message.lower()

        # ── نوع الأمر ─────────────────────────────────────────────────────────
        if any(w in msg for w in ["أذن", "إذن", "امنح", "setup", "أعطِ", "أعطي", "سجّل بيانات"]):
            return self._handle_setup(ctx)

        if any(w in msg for w in ["اسحب", "ألغِ", "revoke", "احذف إذن"]):
            return self._handle_revoke(ctx)

        if any(w in msg for w in ["حالة", "status", "ما عندي", "المحفوظ", "قائمة", "list"]):
            return self._handle_status()

        if any(w in msg for w in ["مزودون", "مزودين", "providers", "ما المدعوم", "كم مزود"]):
            return self._handle_list_providers()

        if any(w in msg for w in ["صدّر", "export", ".env"]):
            return self._handle_export()

        # افتراضي: حاول الحصول على مفتاح
        return self._run_async(self._handle_get(user_message, ctx))

    # ─── Handlers ─────────────────────────────────────────────────────────────

    def _handle_setup(self, ctx: dict) -> str:
        service  = ctx.get("service", "").lower().strip()
        email    = ctx.get("email",    "").strip()
        password = ctx.get("password", "").strip()

        if not service:
            return (
                "لإعطاء Del إذن خدمة جديدة، أحتاج:\n"
                "  - اسم الخدمة\n"
                "  - البريد الإلكتروني\n"
                "  - كلمة المرور\n\n"
                f"الخدمات المتاحة:\n{self._providers_short_list()}\n\n"
                "مثال:\n"
                "  'أعطِ Del إذن groq'\n"
                "  user_context = {service:'groq', email:'x@y.com', password:'abc'}"
            )

        if not email or not password:
            return (
                f"أحتاج إيميل وكلمة مرور لـ {service}.\n"
                "أضفهما في user_context:\n"
                f"  {{'service': '{service}', 'email': 'x@y.com', 'password': '...'}}"
            )

        if service not in PROVIDERS:
            return (
                f"'{service}' غير مدعوم.\n"
                f"الخدمات المدعومة:\n{self._providers_short_list()}"
            )

        grant_permission(service, email, password)
        provider = get_provider(service)
        return (
            f"✓ تم حفظ إذن {provider.name} بنجاح!\n"
            f"  البريد: {email[:3]}***@{email.split('@')[-1] if '@' in email else '?'}\n"
            f"  Del لن يحتاج إذنك مجدداً لـ {service}.\n\n"
            f"الآن قل: 'احصل على API key من {service}'"
        )

    def _handle_revoke(self, ctx: dict) -> str:
        service = ctx.get("service", "").lower().strip()
        if not service:
            return "أي خدمة تريد سحب إذنها؟"
        revoke_permission(service)
        return f"✓ تم سحب إذن {service}.\nالمفاتيح المحفوظة لم تُحذف — فقط الإذن الآلي."

    def _handle_status(self) -> str:
        st    = self.mgr.status()
        lines = [
            f"📦 حالة نظام المصادقة",
            f"{'─'*40}",
            f"مفاتيح محفوظة: {st['total_services']}",
            "",
        ]

        ready   = []
        pending = []

        for pid, info in st["providers"].items():
            if info["has_key"]:
                ready.append(f"  ✓ {info['name']:25} {info['env_var']}")
            elif info["has_perm"]:
                pending.append(f"  ⏳ {info['name']:25} (إذن موجود — مفتاح غير مجلوب)")

        if ready:
            lines.append("✅ جاهز للاستخدام:")
            lines.extend(ready)
            lines.append("")

        if pending:
            lines.append("🔑 إذن موجود — جلب المفتاح:")
            lines.extend(pending)
            lines.append("")

        no_perm = [
            f"  ○ {info['name']}"
            for pid, info in st["providers"].items()
            if not info["has_key"] and not info["has_perm"]
            and info["free"]  # أظهر المجانيين فقط
        ]
        if no_perm:
            lines.append("💡 مجاني ومتاح (يحتاج إذن):")
            lines.extend(no_perm[:5])  # أظهر 5 فقط
            lines.append("")

        return "\n".join(lines)

    def _handle_list_providers(self) -> str:
        lines = [
            f"🌐 المزودون المدعومون ({len(PROVIDERS)})",
            f"{'─'*50}",
        ]
        for p in list_providers():
            free = "✓ مجاني" if p["free_tier"] else "  بطاقة"
            rpm  = f"rpm={p['rpm']:3}" if p["rpm"] else "      "
            lines.append(
                f"  {p['id']:15} {free}  {rpm}  {p['notes'][:40]}"
            )
        lines.append(f"\n{'─'*50}")
        lines.append("المجانيون تماماً (بدون بطاقة ائتمان):")
        for pid in get_free_providers():
            p = get_provider(pid)
            lines.append(f"  • {p.name}")
        return "\n".join(lines)

    def _handle_export(self) -> str:
        try:
            from token_vault import export_to_env
            export_to_env()
            return "✓ تم تصدير كل المفاتيح إلى .env"
        except Exception as e:
            return f"⚠ خطأ في التصدير: {e}"

    async def _handle_get(self, message: str, ctx: dict) -> str:
        result = await self.mgr.execute(message, ctx)

        if result.get("success"):
            key      = result.get("api_key", "")
            source   = result.get("source", "")
            service  = result.get("service", "")
            env_var  = result.get("env_var", "")
            preview  = key[:16] + "***" if key else ""
            provider = get_provider(service)

            src_label = "من الـ Vault (cache)" if source == "vault" else "تسجيل دخول جديد"
            inj_note  = "\n  ✓ تم حفظه في .env و config.json" if result.get("injected") else ""

            lines = [
                f"✓ مفتاح {provider.name if provider else service}",
                f"  المصدر: {src_label}",
                f"  المفتاح: {preview}",
                f"  متغير البيئة: {env_var}",
                inj_note,
            ]

            if provider and provider.models:
                lines.append(f"  النماذج: {', '.join(provider.models[:3])}")

            return "\n".join(l for l in lines if l)

        else:
            msg    = result.get("message", "خطأ غير معروف")
            action = result.get("action_required")

            if action == "grant_permission":
                service  = result.get("service", "")
                provider = get_provider(service)
                pname    = provider.name if provider else service
                return (
                    f"أحتاج إذنك لـ {pname}.\n\n"
                    f"أعطني الإذن مرة واحدة فقط:\n"
                    f"  tool.handle(\n"
                    f"    'أعطِ Del إذن {service}',\n"
                    f"    user_context={{\n"
                    f"      'service': '{service}',\n"
                    f"      'email': 'your@email.com',\n"
                    f"      'password': 'your_password'\n"
                    f"    }}\n"
                    f"  )\n\n"
                    f"بعدها Del سيتذكر للأبد ولن يطلب منك مجدداً."
                )

            ss = result.get("screenshot")
            ss_note = f"\nScreenshot: {ss}" if ss else ""
            return f"⚠ {msg}{ss_note}"

    # ─── Helpers ──────────────────────────────────────────────────────────────

    def _providers_short_list(self) -> str:
        free = get_free_providers()
        lines = []
        for pid in list(PROVIDERS.keys())[:8]:
            tag = "[مجاني]" if pid in free else ""
            lines.append(f"  • {pid} {tag}")
        return "\n".join(lines)

    def _run_async(self, coro) -> str:
        """يشغّل coroutine بأمان سواء كان هناك loop نشط أم لا"""
        try:
            loop = asyncio.get_running_loop()
            # نحن داخل loop — نستخدم thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result(timeout=120)
        except RuntimeError:
            # لا يوجد loop — آمن
            return asyncio.run(coro)


# ─── Quick Demo ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tool = DelAuthTool(headless=False)

    print("=" * 55)
    print("Del Auth Tool v2 — اختبار سريع")
    print("=" * 55)

    # عرض المزودين
    print("\n[1] قائمة المزودين:")
    print(tool.handle("ما المزودون المدعومون"))

    # حالة الـ Vault
    print("\n[2] حالة الـ Vault:")
    print(tool.handle("حالة"))

    # محاولة جلب مفتاح بدون إذن
    print("\n[3] محاولة جلب مفتاح Groq بدون إذن:")
    print(tool.handle("احصل على API key من groq"))

    print("\n" + "=" * 55)
    print("لإعطاء Del الإذن:")
    print("""
  tool.handle(
    'أعطِ Del إذن groq',
    user_context={
      'service':  'groq',
      'email':    'your@email.com',
      'password': 'yourpassword'
    }
  )
""")
