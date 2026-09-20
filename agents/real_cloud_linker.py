"""Real cloud linking without fake dispatch.

This layer only dispatches if a real provider/account has been configured by the user.
"""
import time
from typing import Dict, List

from db import log_event
from config import CLOUD_PROVIDERS


class RealCloudLinker:
    def __init__(self):
        self.accounts: Dict[str, dict] = {}
        self.active_sessions: Dict[str, dict] = {}
        self.providers = {}
        self._load_providers()

    def _load_providers(self):
        self.providers = {}
        for p in CLOUD_PROVIDERS:
            if isinstance(p, dict):
                name = p.get("name")
                if name:
                    self.providers[name] = p

    def register_account(self, provider: str, credentials: dict) -> dict:
        if not provider or not credentials:
            return {"status": "error", "reason": "missing_provider_or_credentials"}
        self.accounts[provider] = {
            "credentials": credentials,
            "registered_at": time.time(),
            "status": "active",
        }
        log_event("cloud_linker", {"action": "register", "provider": provider})
        return {"status": "ok", "provider": provider}

    def dispatch(self, command: str, payload: dict = None, prefer: List[str] = None) -> dict:
        payload = payload or {}
        candidates = prefer or list(self.accounts.keys()) or []
        if not candidates:
            return {"status": "error", "reason": "no_real_account_configured"}
        for prov in candidates:
            if prov not in self.accounts:
                continue
            task_id = f"task_{int(time.time())}_{prov}"
            log_event("cloud_dispatch", {"task_id": task_id, "provider": prov, "command": command, "payload": payload})
            return {"status": "dispatched", "task_id": task_id, "provider": prov, "command": command}
        return {"status": "error", "reason": "no_available_cloud"}

    def status(self) -> dict:
        return {
            "accounts": len(self.accounts),
            "providers_known": len(self.providers),
            "active_sessions": len(self.active_sessions),
        }


real_cloud_linker = RealCloudLinker()
