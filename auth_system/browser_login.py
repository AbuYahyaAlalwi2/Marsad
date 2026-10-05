"""
Browser Login Agent v2 — تسجيل دخول آلي لكل المزودين
- 15 مزود مدعوم (4 قديم + 11 جديد)
- OTP/2FA handling صحيح (مرئي + انتظار المستخدم)
- headless=False افتراضياً للتشغيل الأول
- PATH موحد عبر BASE_ROOT
"""

import asyncio
import re
import time
from typing import Optional
from dataclasses import dataclass
from pathlib import Path
import sys

# ─── Path Setup ───────────────────────────────────────────────────────────────
_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE))
from token_vault import save_credential, get_credential
from provider_registry import PROVIDERS, get_provider, ProviderMeta


# ─── Result Dataclass ─────────────────────────────────────────────────────────

@dataclass
class LoginResult:
    success:    bool
    service:    str
    message:    str
    api_key:    Optional[str] = None
    screenshot: Optional[str] = None


# ─── OTP Detector ─────────────────────────────────────────────────────────────

OTP_URL_PATTERNS = [
    "verify", "otp", "2fa", "mfa", "two-factor", "authenticate",
    "confirm", "code", "challenge", "totp", "phone",
]

OTP_PAGE_SELECTORS = [
    "input[name='otp']",
    "input[name='code']",
    "input[name='token']",
    "input[placeholder*='code']",
    "input[placeholder*='OTP']",
    "input[placeholder*='verification']",
    "input[maxlength='6']",
    "input[maxlength='8']",
]

async def _detect_otp_page(page) -> bool:
    """يكشف إذا كانت الصفحة تطلب OTP/2FA"""
    url = page.url.lower()
    if any(p in url for p in OTP_URL_PATTERNS):
        return True

    for sel in OTP_PAGE_SELECTORS:
        try:
            el = page.locator(sel).first
            if await el.count() > 0:
                return True
        except Exception:
            pass

    return False


async def _handle_otp(page, service: str) -> bool:
    """
    يطلب من المستخدم إدخال رمز OTP مرة واحدة فقط
    يعيد True إذا تم بنجاح
    """
    print(f"\n{'='*50}")
    print(f"[{service}] 🔐 تحقق ثنائي مطلوب!")
    print(f"{'='*50}")
    print(f"الصفحة: {page.url}")
    print(f"\nالمتصفح مفتوح أمامك — أدخل رمز OTP هناك أو:")

    # انتظر المستخدم يدخل الرمز يدوياً
    otp_code = input(f"\nأدخل رمز OTP (أو اضغط Enter إذا أدخلته في المتصفح): ").strip()

    if otp_code:
        # جرّب إدخاله آلياً
        for sel in OTP_PAGE_SELECTORS:
            try:
                el = page.locator(sel).first
                if await el.count() > 0:
                    await el.fill(otp_code)
                    await asyncio.sleep(0.5)
                    await page.keyboard.press("Enter")
                    await asyncio.sleep(2)
                    return True
            except Exception:
                continue

    # انتظر المستخدم يكمل يدوياً (30 ثانية)
    print(f"\nانتظر اكتمال تسجيل الدخول في المتصفح... (30 ثانية)")
    for i in range(6):
        await asyncio.sleep(5)
        if not await _detect_otp_page(page):
            print(f"[{service}] ✓ تجاوز شاشة OTP")
            return True
        print(f"  لا يزال ينتظر... ({(i+1)*5}/30 ث)")

    return False


# ─── Core Agent ───────────────────────────────────────────────────────────────

class BrowserLoginAgent:
    """
    وكيل تسجيل الدخول الآلي
    headless=False: المتصفح مرئي (مهم للـ OTP والـ captcha)
    headless=True:  صامت تماماً (بعد التحقق من النجاح)
    """

    def __init__(self, headless: bool = False):
        # Windows: False افتراضياً لأن المستخدم يحتاج يرى المتصفح
        self.headless = headless

    async def login_and_get_key(
        self,
        service:  str,
        email:    str,
        password: str,
        save:     bool = True,
    ) -> LoginResult:
        """
        المهمة الكاملة: دخول → مفاتيح → استخراج → حفظ
        """
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return LoginResult(
                False, service,
                "playwright غير مثبت.\n"
                "شغّل في مجلد Dolphin:\n"
                "  pip install playwright\n"
                "  playwright install chromium"
            )

        provider = get_provider(service)
        if not provider:
            supported = list(PROVIDERS.keys())
            return LoginResult(
                False, service,
                f"'{service}' غير مدعوم.\nالمدعومون: {supported}"
            )

        print(f"\n[{service}] ═══ بدء التسجيل الآلي ═══")
        print(f"[{service}] المتصفح: {'خفي' if self.headless else 'مرئي'}")

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless = self.headless,
                args     = [
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-infobars",
                ]
            )
            ctx  = await browser.new_context(
                user_agent = (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport = {"width": 1280, "height": 800},
            )
            page = await ctx.new_page()

            try:
                result = await self._do_login_flow(page, provider, email, password, save)
                return result
            except Exception as e:
                ss = await self._screenshot(page, f"{service}_error")
                return LoginResult(False, service, f"خطأ غير متوقع: {e}", screenshot=ss)
            finally:
                await browser.close()

    # ─────────────────────────────────────────────────────────────────────────

    async def _do_login_flow(
        self,
        page,
        provider: ProviderMeta,
        email:    str,
        password: str,
        save:     bool,
    ) -> LoginResult:
        service = provider.id

        # ── 1. صفحة تسجيل الدخول ────────────────────────────────────────────
        print(f"[{service}] فتح {provider.login_url}")
        await page.goto(provider.login_url, wait_until="domcontentloaded", timeout=30_000)
        await asyncio.sleep(2)

        # ── 2. إدخال البريد الإلكتروني ──────────────────────────────────────
        email_el = await self._find(page, provider.email_sel)
        if not email_el:
            ss = await self._screenshot(page, f"{service}_no_email_field")
            return LoginResult(False, service,
                               "لم أجد حقل البريد الإلكتروني", screenshot=ss)

        await email_el.click()
        await email_el.fill(email)
        await asyncio.sleep(0.8)

        # بعض المواقع تحتاج Enter/Tab أولاً لإظهار حقل كلمة المرور
        await page.keyboard.press("Tab")
        await asyncio.sleep(1)

        # ── 3. إدخال كلمة المرور ─────────────────────────────────────────────
        pass_el = await self._find(page, provider.pass_sel)
        if pass_el:
            await pass_el.click()
            await pass_el.fill(password)
            await asyncio.sleep(0.5)
        else:
            # بعض المواقع (Google) تستخدم Next ثم تظهر كلمة المرور
            submit_el = await self._find(page, provider.submit_sel)
            if submit_el:
                await submit_el.click()
                await asyncio.sleep(2)
            pass_el = await self._find(page, provider.pass_sel)
            if pass_el:
                await pass_el.fill(password)

        # ── 4. زر تسجيل الدخول ──────────────────────────────────────────────
        submit_el = await self._find(page, provider.submit_sel)
        if submit_el:
            await submit_el.click()
        else:
            await page.keyboard.press("Enter")

        print(f"[{service}] ضغطت على تسجيل الدخول...")
        await asyncio.sleep(3)

        try:
            await page.wait_for_load_state("networkidle", timeout=15_000)
        except Exception:
            pass  # timeout مقبول

        # ── 5. كشف OTP/2FA ──────────────────────────────────────────────────
        if await _detect_otp_page(page):
            print(f"[{service}] تم اكتشاف شاشة OTP")
            otp_ok = await _handle_otp(page, service)
            if not otp_ok:
                ss = await self._screenshot(page, f"{service}_otp_stuck")
                return LoginResult(False, service,
                                   "توقف عند شاشة OTP — حاول مجدداً مع headless=False",
                                   screenshot=ss)

        # ── 6. التحقق من نجاح تسجيل الدخول ─────────────────────────────────
        current_url = page.url
        if provider.success_url not in current_url:
            # انتظر قليلاً ثم تحقق مجدداً
            await asyncio.sleep(5)
            current_url = page.url
            if provider.success_url not in current_url:
                ss = await self._screenshot(page, f"{service}_login_failed")
                return LoginResult(
                    False, service,
                    f"تسجيل الدخول ربما فشل.\n"
                    f"URL الحالي: {current_url}\n"
                    f"Screenshot: {ss}",
                    screenshot=ss,
                )

        print(f"[{service}] ✓ تسجيل دخول ناجح")

        # ── 7. صفحة API Keys ────────────────────────────────────────────────
        print(f"[{service}] الانتقال لصفحة المفاتيح: {provider.api_key_url}")
        await page.goto(provider.api_key_url, wait_until="domcontentloaded", timeout=20_000)
        await asyncio.sleep(2)

        # ── 8. ضغط زر إنشاء مفتاح جديد ─────────────────────────────────────
        create_el = await self._find(page, provider.create_btn)
        if create_el:
            await create_el.click()
            print(f"[{service}] ضغطت على إنشاء مفتاح")
            await asyncio.sleep(3)
        else:
            print(f"[{service}] ⚠ لم أجد زر الإنشاء — أحاول استخراج مفتاح موجود")

        # ── 9. استخراج المفتاح ───────────────────────────────────────────────
        api_key = await self._extract_key(page, provider.key_pattern)

        if api_key:
            print(f"[{service}] ✓ مفتاح: {api_key[:12]}***")
            if save:
                save_credential(service, "api_key", api_key, {
                    "email":    email,
                    "obtained": time.time(),
                    "method":   "browser_auto_v2",
                })
                save_credential(service, "email",    email)
                save_credential(service, "password", password)
                print(f"[{service}] ✓ محفوظ في الـ Vault")

            return LoginResult(True, service, "✓ نجح الحصول على المفتاح", api_key=api_key)

        # لم نجد مفتاحاً — خذ screenshot
        ss = await self._screenshot(page, f"{service}_keys_page")
        return LoginResult(
            True, service,
            f"تسجيل الدخول نجح لكن لم أستطع استخراج المفتاح تلقائياً.\n"
            f"Screenshot: {ss}\n"
            f"افتح المتصفح يدوياً وانسخ المفتاح.",
            screenshot=ss,
        )

    # ─── Helpers ──────────────────────────────────────────────────────────────

    async def _find(self, page, selectors: str):
        """يجرب كل selector حتى يجد عنصراً"""
        for sel in selectors.split(", "):
            sel = sel.strip()
            if not sel:
                continue
            try:
                el = page.locator(sel).first
                if await el.count() > 0:
                    return el
            except Exception:
                continue
        return None

    async def _extract_key(self, page, pattern: str) -> Optional[str]:
        """يبحث عن API key في الصفحة بعدة طرق"""

        # 1. HTML كامل
        content = await page.content()
        matches = re.findall(pattern, content)
        if matches:
            return matches[0]

        # 2. input fields
        inputs = await page.locator(
            "input[type='text'], input[readonly], input.api-key, "
            "input[name*='key'], input[name*='token']"
        ).all()
        for inp in inputs:
            try:
                val = (await inp.get_attribute("value") or "").strip()
                m   = re.search(pattern, val)
                if m:
                    return m.group()
            except Exception:
                continue

        # 3. data-clipboard-text / data-copy
        for attr in ["data-clipboard-text", "data-copy", "data-value"]:
            els = await page.locator(f"[{attr}]").all()
            for el in els:
                try:
                    val = (await el.get_attribute(attr) or "").strip()
                    m   = re.search(pattern, val)
                    if m:
                        return m.group()
                except Exception:
                    continue

        # 4. code/pre elements
        code_els = await page.locator("code, pre, .api-key, .key-value, [class*='key']").all()
        for el in code_els:
            try:
                txt = (await el.inner_text() or "").strip()
                m   = re.search(pattern, txt)
                if m:
                    return m.group()
            except Exception:
                continue

        return None

    async def _screenshot(self, page, name: str) -> str:
        """يأخذ screenshot للمراجعة"""
        from pathlib import Path
        BASE_ROOT = Path(__file__).parent.parent.parent
        ss_dir    = BASE_ROOT / "delfin_os" / "screenshots"
        ss_dir.mkdir(parents=True, exist_ok=True)
        ss_path = str(ss_dir / f"{name}_{int(time.time())}.png")
        try:
            await page.screenshot(path=ss_path, full_page=True)
        except Exception:
            pass
        return ss_path


# ─── Simple API ───────────────────────────────────────────────────────────────

async def auto_get_api_key(
    service:  str,
    email:    str,
    password: str,
    headless: bool = False,
) -> dict:
    """الدالة الرئيسية لـ Del"""
    agent  = BrowserLoginAgent(headless=headless)
    result = await agent.login_and_get_key(service, email, password)
    return {
        "success":     result.success,
        "service":     result.service,
        "message":     result.message,
        "api_key":     result.api_key,
        "key_preview": (result.api_key[:12] + "***") if result.api_key else None,
        "screenshot":  result.screenshot,
    }


def get_key_sync(service: str, email: str, password: str, headless: bool = False) -> dict:
    """نسخة synchronous"""
    return asyncio.run(auto_get_api_key(service, email, password, headless))


# ─── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from provider_registry import list_providers

    if len(sys.argv) >= 4:
        svc, em, pw = sys.argv[1], sys.argv[2], sys.argv[3]
        print(f"\nتسجيل دخول لـ {svc}...")
        result = get_key_sync(svc, em, pw, headless=False)
        print(f"\n{'='*40}")
        print(f"النتيجة: {'✓ نجاح' if result['success'] else '✗ فشل'}")
        print(f"الرسالة: {result['message']}")
        if result["api_key"]:
            print(f"المفتاح: {result['key_preview']}")
    else:
        print("الاستخدام: python browser_login.py <service> <email> <password>")
        print(f"\nالمزودون المدعومون ({len(PROVIDERS)}):")
        for p in list_providers():
            free = "مجاني" if p["free_tier"] else "يحتاج بطاقة"
            print(f"  {p['id']:15} {p['name']:25} {free}")
