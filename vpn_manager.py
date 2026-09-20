"""
CYBERGUARD OS - VPN Manager
Maps cloud providers to countries. Uses proxy2vpn if available.
"""
import os
import time
import logging
import subprocess
from typing import Dict, Optional

from db import log_event
from config import ENABLE_VPN

logger = logging.getLogger(__name__)


# Country requirement for regional clouds
PROVIDER_COUNTRY_MAP = {
    "alibaba_cloud": "SG", "tencent_cloud": "SG", "huawei_cloud": "SG",
    "stc_cloud": "SA", "mobily_cloud": "SA", "zain_sa": "SA",
    "etisalat_cloud": "AE", "du_cloud": "AE",
    "naver_cloud": "KR", "kakao_cloud": "KR", "kt_cloud": "KR",
    "sakura_cloud": "JP", "idcf_cloud": "JP", "conoha": "JP",
    "yandex_cloud": "RU", "sbercloud": "RU", "vk_cloud": "RU",
    "reliance_jio": "IN", "airtel_cloud": "IN", "netmagic": "IN",
    "locaweb": "BR", "uol_cloud": "BR",
    "afrihost": "ZA", "xneelo": "ZA",
    "orange_eg": "EG", "vodafone_eg": "EG",
    "turkcell_cloud": "TR", "turknet_cloud": "TR",
}


class VPNManager:
    def __init__(self):
        self.available = False
        self.active_country: Optional[str] = None
        self.active_container: Optional[str] = None
        self._check_proxy2vpn()

    def _check_proxy2vpn(self):
        try:
            result = subprocess.run(
                ["proxy2vpn", "--version"],
                capture_output=True, text=True, timeout=5,
            )
            self.available = result.returncode == 0
            if self.available:
                logger.info("[VPN] proxy2vpn ready")
        except Exception:
            self.available = False
            logger.info("[VPN] proxy2vpn not installed - VPN disabled (safe)")

    def connect(self, country_code: str) -> Dict:
        if not ENABLE_VPN or not self.available:
            return {"status": "disabled", "country": country_code,
                    "reason": "vpn_not_enabled"}

        country_code = country_code.upper()
        if self.active_country == country_code:
            return {"status": "already_connected", "country": country_code}

        self.disconnect()

        try:
            result = subprocess.run(
                ["proxy2vpn", "connect", "--country", country_code],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                self.active_country = country_code
                self.active_container = f"proxy2vpn_{country_code.lower()}"
                try:
                    log_event("vpn", {"action": "connected", "country": country_code})
                except Exception:
                    pass
                return {"status": "connected", "country": country_code}
            return {"status": "error", "error": result.stderr}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def disconnect(self) -> Dict:
        if not self.active_container:
            return {"status": "not_connected"}
        try:
            subprocess.run(
                ["proxy2vpn", "disconnect", "--container", self.active_container],
                capture_output=True, text=True, timeout=15,
            )
            try:
                log_event("vpn", {"action": "disconnected",
                                  "country": self.active_country})
            except Exception:
                pass
            self.active_country = None
            self.active_container = None
            return {"status": "disconnected"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def connect_for_provider(self, provider_name: str) -> Dict:
        country = PROVIDER_COUNTRY_MAP.get(provider_name)
        if not country:
            return {"status": "no_vpn_needed", "provider": provider_name}
        return self.connect(country)

    def status(self) -> Dict:
        return {
            "available": self.available,
            "enabled": ENABLE_VPN,
            "active_country": self.active_country,
            "active_container": self.active_container,
            "mapped_providers": len(PROVIDER_COUNTRY_MAP),
        }


vpn_manager = VPNManager()
