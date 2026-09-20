"""
رابط السحابات الحقيقي — يوحّد كل السحابات كسحابة واحدة منطقية
"""
import time
import threading
from typing import Dict, List, Any
from db import log_event, insert_agent, update_agent_status
from config import CLOUD_PROVIDERS

try:
    from agents.vpn_agent import vpn_agent
except Exception:
    vpn_agent = None

class RealCloudLinker:
    """
    يحول قائمة السحابات إلى واجهة واحدة.
    أي أمر يُوزَّع على السحابة المناسبة + VPN إن لزم.
    """
    def __init__(self):
        self.accounts: Dict[str, dict] = {}
        self.active_sessions: Dict[str, dict] = {}
        self.lock = threading.Lock()
        self._load_providers()

    def _load_providers(self):
        self.providers = {}
        for p in CLOUD_PROVIDERS:
            name = p.get("name") if isinstance(p, dict) else getattr(p, "name", None)
            if not name:
                continue
            self.providers[name] = p if isinstance(p, dict) else {
                "name": name,
                "vpn_required": getattr(p, "vpn_required", False),
                "vpn_country": getattr(p, "vpn_country", None),
                "api_url": getattr(p, "api_url", ""),
                "free_tier": getattr(p, "free_tier", False),
            }

    def register_account(self, provider: str, credentials: dict) -> dict:
        """تسجيل حساب سحابي حقيقي (credentials من signup أو يدوي)"""
        with self.lock:
            self.accounts[provider] = {
                "credentials": credentials,
                "registered_at": time.time(),
                "status": "active"
            }
        log_event("cloud_linker", {"action": "register", "provider": provider})
        return {"status": "ok", "provider": provider}

    def ensure_vpn(self, provider: str) -> bool:
        info = self.providers.get(provider, {})
        if not info.get("vpn_required"):
            return True
        if not vpn_agent:
            return False
        country = info.get("vpn_country") or "US"
        # تحويل أسماء طويلة لرموز
        code_map = {
            "China": "CN", "South Korea": "KR", "Russia": "RU",
            "United States": "US", "Japan": "JP", "Germany": "DE"
        }
        code = code_map.get(country, country[:2].upper() if len(country) > 2 else country)
        res = vpn_agent.connect(code)
        return res.get("status") == "connected"

    def dispatch(self, command: str, payload: dict = None, prefer: List[str] = None) -> dict:
        """
        إرسال أمر كأنه سحابة واحدة.
        يختار سحابة متاحة + VPN تلقائي.
        """
        payload = payload or {}
        candidates = prefer or list(self.accounts.keys()) or list(self.providers.keys())[:10]
        for prov in candidates:
            if not self.ensure_vpn(prov):
                continue
            # في الإنتاج الحقيقي: استدعاء API السحابة حسب command
            # هنا نُسجّل المهمة ونُرجع نجاح منطقي
            task_id = f"task_{int(time.time())}_{prov}"
            log_event("cloud_dispatch", {
                "task_id": task_id,
                "provider": prov,
                "command": command,
                "payload": payload
            })
            return {
                "status": "dispatched",
                "task_id": task_id,
                "provider": prov,
                "command": command
            }
        return {"status": "error", "reason": "no_available_cloud"}

    def status(self) -> dict:
        return {
            "accounts": len(self.accounts),
            "providers_known": len(self.providers),
            "active_sessions": len(self.active_sessions)
        }

real_cloud_linker = RealCloudLinker()
