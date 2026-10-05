"""
Session Manager v2 — المنسق الرئيسي
- BASE_ROOT موحد عبر كل الملفات
- inject_to_project ديناميكي (من provider_registry)
- يدعم كل 15 مزود
- OTP handling مدمج
"""

import asyncio
import re
from pathlib import Path
from typing import Optional
import sys

# ─── Path Setup ───────────────────────────────────────────────────────────────
_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE))

from token_vault      import save_credential, get_credential, list_services, export_to_env
from browser_login    import BrowserLoginAgent, LoginResult
from provider_registry import PROVIDERS, get_provider

# BASE_ROOT موحد — Dolphin/
BASE_ROOT = Path(__file__).parent.parent.parent


# ─── Permission System ────────────────────────────────────────────────────────

PERM_SERVICE = "user_permissions"


def has_permission(service: str) -> bool:
    return get_credential(PERM_SERVICE, service) == "granted"


def grant_permission(service: str, email: str, password: str):
    """المستخدم يوافق مرة واحدة — Del يتذكر للأبد"""
    save_credential(PERM_SERVICE, service, "granted")
    save_credential(service, "email",    email)
    save_credential(service, "password", password)
    print(f"✓ إذن '{service}' محفوظ بأمان")
    print(f"  Del لن يحتاج إذنك مجدداً لهذه الخدمة")


def revoke_permission(service: str):
    """سحب الإذن (يُبقي المفاتيح المحفوظة)"""
    save_credential(PERM_SERVICE, service, "revoked")
    print(f"✓ إذن '{service}' تم سحبه")


def list_permissions() -> dict[str, bool]:
    """يعرض حالة الإذن لكل خدمة"""
    return {sid: has_permission(sid) for sid in PROVIDERS}


# ─── Session Manager ──────────────────────────────────────────────────────────

class SessionManager:
    """
    الواجهة الرئيسية التي يستدعيها Del

    مثال:
        sm = SessionManager()
        result = await sm.execute("احصل على API key من groq")
    """

    def __init__(self, headless: bool = False):
        # headless=False: المتصفح مرئي (مناسب لـ Windows و OTP)
        self.agent = BrowserLoginAgent(headless=headless)

    # ── الحصول على API key ────────────────────────────────────────────────────

    async def get_api_key(
        self,
        service:       str,
        email:         Optional[str] = None,
        password:      Optional[str] = None,
        force_refresh: bool          = False,
    ) -> dict:
        """
        1. تحقق من الـ Vault (cache)
        2. إذا لم يوجد أو force_refresh → سجّل دخول آلياً
        3. احفظ في الـ Vault وحقن في .env و config.json
        """
        service = service.lower().strip()
        provider = get_provider(service)

        if not provider:
            return {
                "success": False,
                "service": service,
                "message": f"'{service}' غير مدعوم. الخدمات المتاحة: {list(PROVIDERS.keys())}",
            }

        # ── Cache hit ─────────────────────────────────────────────────────────
        if not force_refresh:
            cached_key = (
                get_credential(service, "api_key") or
                get_credential(service, "token")
            )
            if cached_key:
                print(f"[{service}] ✓ مفتاح موجود في الـ Vault")
                return {
                    "success": True,
                    "service": service,
                    "api_key": cached_key,
                    "source":  "vault",
                    "env_var": provider.env_var,
                }

        # ── جلب credentials من الـ Vault أو من المعطيات ──────────────────────
        _email    = email    or get_credential(service, "email")
        _password = password or get_credential(service, "password")

        if not _email or not _password:
            return {
                "success":         False,
                "service":         service,
                "message":         f"أحتاج إيميل وكلمة مرور لـ {service}.",
                "action_required": "grant_permission",
            }

        # ── تسجيل دخول آلي ───────────────────────────────────────────────────
        print(f"[{service}] بدء تسجيل الدخول الآلي...")
        result: LoginResult = await self.agent.login_and_get_key(
            service, _email, _password, save=True
        )

        if result.success and result.api_key:
            self._inject_to_project(service, result.api_key)
            return {
                "success":  True,
                "service":  service,
                "api_key":  result.api_key,
                "source":   "browser_auto",
                "injected": True,
                "env_var":  provider.env_var,
            }

        return {
            "success":    False,
            "service":    service,
            "message":    result.message,
            "screenshot": result.screenshot,
        }

    # ── حقن المفتاح في المشروع ────────────────────────────────────────────────

    def _inject_to_project(self, service: str, api_key: str):
        """
        يضيف المفتاح في:
        1. BASE_ROOT/.env
        2. BASE_ROOT/config.json (إذا وُجد)
        يستخدم env_var من provider_registry — ديناميكي تماماً
        """
        provider = get_provider(service)
        env_name = provider.env_var if provider else f"{service.upper()}_API_KEY"

        # ── 1. تحديث .env ─────────────────────────────────────────────────────
        env_path = BASE_ROOT / ".env"
        env_path.parent.mkdir(parents=True, exist_ok=True)

        current = env_path.read_text(encoding="utf-8") if env_path.exists() else ""

        if env_name in current:
            current = re.sub(
                rf'({env_name}\s*=\s*).*',
                rf'\g<1>"{api_key}"',
                current,
            )
        else:
            current = current.rstrip() + f'\n{env_name}="{api_key}"\n'

        env_path.write_text(current, encoding="utf-8")
        print(f"[{service}] ✓ {env_name} → {env_path}")

        # ── 2. تحديث config.json ──────────────────────────────────────────────
        import json
        cfg_path = BASE_ROOT / "config.json"
        if cfg_path.exists():
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)

                updated = 0
                for model in cfg.get("models", []):
                    if model.get("provider", "").lower() == service:
                        model["api_key"] = api_key
                        updated += 1

                if "env" not in cfg:
                    cfg["env"] = {}
                cfg["env"][env_name] = api_key

                with open(cfg_path, "w", encoding="utf-8") as f:
                    json.dump(cfg, f, ensure_ascii=False, indent=2)

                if updated:
                    print(f"[{service}] ✓ حدّثت {updated} نموذج في config.json")
            except Exception as e:
                print(f"[{service}] ⚠ config.json: {e}")

    # ── تنفيذ أمر بلغة طبيعية ─────────────────────────────────────────────────

    async def execute(self, command: str, context: dict = None) -> dict:
        """
        Del يستدعي هذا بأمر طبيعي:
        "احصل على API key من Groq"
        "سجّل في cerebras وأحضر مفتاح"
        "جدد مفتاح mistral"
        """
        cmd  = command.lower()
        ctx  = context or {}

        # ── كشف الخدمة ────────────────────────────────────────────────────────
        service = ctx.get("service")
        if not service:
            for sid in PROVIDERS:
                if sid in cmd:
                    service = sid
                    break
            # أسماء بديلة
            aliases = {
                "openai":   ["gpt", "chatgpt"],
                "gemini":   ["google", "bard"],
                "cerebras": ["cerebras"],
                "deepseek": ["deep seek", "deepseek"],
                "together": ["together ai"],
                "fireworks":["firework"],
                "sambanova":["samba"],
                "qwen":     ["alibaba", "dashscope"],
                "moonshot": ["kimi"],
                "nvidia":   ["nim", "nvidia"],
            }
            if not service:
                for sid, alts in aliases.items():
                    if any(a in cmd for a in alts):
                        service = sid
                        break

        if not service:
            return {
                "success": False,
                "message": (
                    "لم أفهم الخدمة المطلوبة.\n"
                    f"الخدمات المدعومة: {', '.join(PROVIDERS.keys())}"
                ),
            }

        # ── كشف force_refresh ─────────────────────────────────────────────────
        force = any(w in command for w in ["جدد", "جديد", "refresh", "renew", "new"])

        return await self.get_api_key(
            service       = service,
            email         = ctx.get("email"),
            password      = ctx.get("password"),
            force_refresh = force,
        )

    # ── حالة كل الخدمات ───────────────────────────────────────────────────────

    def status(self) -> dict:
        creds    = list_services()
        services = {}
        for c in creds:
            s = c["service"]
            if s == PERM_SERVICE:
                continue
            if s not in services:
                services[s] = {}
            services[s][c["key"]] = c["preview"]

        provider_status = {}
        for pid, provider in PROVIDERS.items():
            has_key  = bool(
                get_credential(pid, "api_key") or
                get_credential(pid, "token")
            )
            has_perm = has_permission(pid)
            provider_status[pid] = {
                "name":     provider.name,
                "has_key":  has_key,
                "has_perm": has_perm,
                "env_var":  provider.env_var,
                "rpm":      provider.rpm,
                "free":     provider.free_tier,
            }

        return {
            "total_services": len(services),
            "vault_entries":  services,
            "providers":      provider_status,
        }


# ─── Singleton ────────────────────────────────────────────────────────────────

_manager: Optional[SessionManager] = None

def get_manager(headless: bool = False) -> SessionManager:
    global _manager
    if _manager is None:
        _manager = SessionManager(headless=headless)
    return _manager


# ─── CLI ──────────────────────────────────────────────────────────────────────

def _cli_setup(service: str, email: str, password: str):
    grant_permission(service, email, password)
    print(f"\n{'='*50}")
    print(f"✓ إذن {service} محفوظ بنجاح!")
    print(f"{'='*50}")
    print(f"\nالآن Del سيسجل دخول تلقائياً بدون تدخلك.")
    print(f"\nجرّب مباشرة:")
    print(f"  python session_manager.py get {service}")


async def _cli_get(service: str, headless: bool = False):
    mgr    = SessionManager(headless=headless)
    result = await mgr.get_api_key(service)
    print(f"\n{'='*50}")
    if result.get("success"):
        key = result.get("api_key", "")
        print(f"✓ مفتاح {service}: {key[:16]}***")
        print(f"  المصدر: {result.get('source')}")
        print(f"  متغير البيئة: {result.get('env_var')}")
        if result.get("injected"):
            print(f"  ✓ تم حفظه في .env و config.json")
    else:
        print(f"✗ فشل: {result.get('message')}")
        if result.get("action_required") == "grant_permission":
            print(f"\nأعطِ الإذن أولاً:")
            print(f"  python session_manager.py setup {service} email@x.com password")


def _cli_status():
    mgr = SessionManager()
    st  = mgr.status()
    print(f"\n{'='*50}")
    print(f"حالة الـ Vault")
    print(f"{'='*50}")
    print(f"إجمالي المفاتيح المحفوظة: {st['total_services']}\n")

    for pid, info in st["providers"].items():
        key_icon  = "✓" if info["has_key"]  else "○"
        perm_icon = "🔑" if info["has_perm"] else "  "
        free_tag  = "[مجاني]" if info["free"] else ""
        print(
            f"  {key_icon} {perm_icon} {info['name']:25} "
            f"{info['env_var']:25} rpm={info['rpm']:4} {free_tag}"
        )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("الاستخدام:")
        print("  setup:  python session_manager.py setup <service> <email> <password>")
        print("  get:    python session_manager.py get <service> [--visible]")
        print("  status: python session_manager.py status")
        print("  export: python session_manager.py export")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "setup" and len(sys.argv) == 5:
        _cli_setup(sys.argv[2], sys.argv[3], sys.argv[4])

    elif cmd == "get" and len(sys.argv) >= 3:
        headless = "--headless" in sys.argv
        asyncio.run(_cli_get(sys.argv[2], headless=headless))

    elif cmd == "status":
        _cli_status()

    elif cmd == "export":
        export_to_env()

    else:
        print(f"أمر غير معروف: {cmd}")
