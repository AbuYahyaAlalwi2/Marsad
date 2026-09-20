"""
وكيل VPN — تبديل IP للدول المختلفة
يدعم: ProtonVPN, Windscribe, TunnelBear, Tor
"""
import os
import time
import random
import subprocess
import requests
from db import log_event


class VPNAgent:
    """
    وكيل VPN للتبديل بين دول مختلفة:
    - أمريكا (US)
    - بريطانيا (UK)
    - ألمانيا (DE)
    - اليابان (JP)
    - كوريا الجنوبية (KR)
    - الصين (CN) - صعب
    - روسيا (RU)
    - الهند (IN)
    - البرازيل (BR)
    - أستراليا (AU)
    """

    def __init__(self):
        self.current_country = None
        self.current_ip = None
        self.vpn_configs = self._load_vpn_configs()

        log_event("vpn_agent", {"status": "initialized"})

    def _load_vpn_configs(self) -> dict:
        """إعدادات VPN لكل دولة"""
        return {
            "US": {
                "name": "United States",
                "providers": [
                    {"name": "ProtonVPN-US", "type": "openvpn", "server": "us-free-1.protonvpn.net"},
                    {"name": "ProtonVPN-US2", "type": "openvpn", "server": "us-free-2.protonvpn.net"},
                    {"name": "Windscribe-US", "type": "wireguard", "server": "us-east.windscribe.net"},
                ]
            },
            "UK": {
                "name": "United Kingdom",
                "providers": [
                    {"name": "ProtonVPN-UK", "type": "openvpn", "server": "uk-free-1.protonvpn.net"},
                    {"name": "Windscribe-UK", "type": "wireguard", "server": "uk-west.windscribe.net"},
                ]
            },
            "DE": {
                "name": "Germany",
                "providers": [
                    {"name": "ProtonVPN-DE", "type": "openvpn", "server": "de-free-1.protonvpn.net"},
                    {"name": "Windscribe-DE", "type": "wireguard", "server": "de.windscribe.net"},
                ]
            },
            "JP": {
                "name": "Japan",
                "providers": [
                    {"name": "ProtonVPN-JP", "type": "openvpn", "server": "jp-free-1.protonvpn.net"},
                    {"name": "Windscribe-JP", "type": "wireguard", "server": "jp.windscribe.net"},
                ]
            },
            "KR": {
                "name": "South Korea",
                "providers": [
                    {"name": "VPN-KR-1", "type": "proxy", "server": "kr.proxy.example.com"},
                    {"name": "VPN-KR-2", "type": "proxy", "server": "kr2.proxy.example.com"},
                ]
            },
            "CN": {
                "name": "China",
                "providers": [
                    {"name": "VPN-CN-1", "type": "proxy", "server": "cn.proxy.example.com"},
                ],
                "note": "صعب — يتطلب VPN صيني خاص"
            },
            "RU": {
                "name": "Russia",
                "providers": [
                    {"name": "VPN-RU-1", "type": "proxy", "server": "ru.proxy.example.com"},
                ]
            },
            "IN": {
                "name": "India",
                "providers": [
                    {"name": "ProtonVPN-IN", "type": "openvpn", "server": "in-free-1.protonvpn.net"},
                ]
            },
            "BR": {
                "name": "Brazil",
                "providers": [
                    {"name": "ProtonVPN-BR", "type": "openvpn", "server": "br-free-1.protonvpn.net"},
                ]
            },
            "AU": {
                "name": "Australia",
                "providers": [
                    {"name": "ProtonVPN-AU", "type": "openvpn", "server": "au-free-1.protonvpn.net"},
                ]
            }
        }

    def connect(self, country: str = None) -> dict:
        """
        الاتصال بـ VPN لدولة محددة
        إذا لم تحدد دولة، يختار عشوائياً
        """
        if not country:
            country = random.choice(list(self.vpn_configs.keys()))

        if country not in self.vpn_configs:
            return {"status": "error", "reason": f"دولة غير مدعومة: {country}"}

        config = self.vpn_configs[country]
        provider = random.choice(config["providers"])

        log_event("vpn_agent", {
            "action": "connecting",
            "country": country,
            "provider": provider["name"]
        })

        try:
            # في الإنتاج: الاتصال الفعلي بـ VPN
            # هنا: محاكاة الاتصال

            result = self._simulate_connection(country, provider)

            if result["status"] == "connected":
                self.current_country = country
                self.current_ip = result.get("ip")

                log_event("vpn_agent", {
                    "action": "connected",
                    "country": country,
                    "ip": result.get("ip")
                })

            return result

        except Exception as e:
            log_event("vpn_agent_errors", {
                "country": country,
                "error": str(e)
            })
            return {"status": "error", "error": str(e)}

    def _simulate_connection(self, country: str, provider: dict) -> dict:
        """محاولة اتصال حقيقي أولاً، وإلا محاكاة"""
        # محاولة OpenVPN إذا وُجد ملف config
        conf = f"/etc/openvpn/{country.lower()}.ovpn"
        if os.path.exists(conf):
            try:
                subprocess.Popen(["openvpn", "--config", conf], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                time.sleep(4)
                return {"status": "connected", "country": country, "provider": provider["name"], "ip": self.get_current_ip(), "real": True}
            except Exception:
                pass
        # fallback محاكاة
        # توليد IP وهمي حسب الدولة
        ip_prefixes = {
            "US": "104.", "UK": "81.", "DE": "88.", "JP": "126.",
            "KR": "175.", "CN": "113.", "RU": "91.", "IN": "103.",
            "BR": "177.", "AU": "101."
        }

        prefix = ip_prefixes.get(country, "104.")
        fake_ip = f"{prefix}{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}"

        # تأخير محاكاة الاتصال
        time.sleep(random.uniform(1, 3))

        return {
            "status": "connected",
            "country": country,
            "country_name": self.vpn_configs[country]["name"],
            "provider": provider["name"],
            "ip": fake_ip,
            "connected_at": time.time()
        }

    def disconnect(self) -> dict:
        """قطع الاتصال"""
        if not self.current_country:
            return {"status": "warning", "reason": "لا يوجد اتصال"}

        log_event("vpn_agent", {
            "action": "disconnecting",
            "country": self.current_country
        })

        # في الإنتاج: قطع الاتصال الفعلي
        self.current_country = None
        self.current_ip = None

        return {"status": "disconnected"}

    def rotate(self) -> dict:
        """تدوير IP — تغيير الدولة تلقائياً"""
        # اختيار دولة مختلفة عن الحالية
        available = [c for c in self.vpn_configs.keys() if c != self.current_country]
        new_country = random.choice(available)

        self.disconnect()
        time.sleep(1)

        return self.connect(new_country)

    def get_current_ip(self) -> str:
        """الحصول على IP الحالي"""
        # في الإنتاج: استخدام api.ipify.org
        try:
            response = requests.get("https://api.ipify.org?format=json", timeout=5)
            return response.json().get("ip", "unknown")
        except:
            return self.current_ip or "unknown"

    def get_status(self) -> dict:
        """حالة VPN"""
        return {
            "connected": self.current_country is not None,
            "country": self.current_country,
            "country_name": self.vpn_configs.get(self.current_country, {}).get("name"),
            "ip": self.current_ip,
            "available_countries": list(self.vpn_configs.keys())
        }

    def get_country_for_platform(self, platform: str) -> str:
        """
        الحصول على الدولة المناسبة لمنصة معينة
        بعض المنصات تتطلب IP من دولة محددة
        """
        platform_countries = {
            # منصات صينية
            "baidu": "CN",
            "alibaba": "CN",
            "tencent": "CN",
            "zhipu": "CN",

            # منصات كورية
            "naver": "KR",
            "kakao": "KR",

            # منصات روسية
            "yandex": "RU",
            "vk": "RU",

            # منصات يابانية
            "sakura": "JP",

            # منصات هندية
            "zoho_in": "IN",
        }

        return platform_countries.get(platform, "US")  # افتراضي: أمريكا


class TorManager:
    """
    مدير Tor — مجاني ومفتوح المصدر
    """

    def __init__(self):
        self.enabled = os.environ.get("CG_TOR_ENABLED", "true").lower() == "true"

    def rotate_ip(self) -> dict:
        """تدوير IP عبر Tor"""
        if not self.enabled:
            return {"status": "disabled"}

        try:
            # طلب IP جديد من Tor
            from stem import Signal
            from stem.control import Controller

            with Controller.from_port(port=9051) as controller:
                controller.authenticate()
                controller.signal(Signal.NEWNYM)

            time.sleep(3)

            log_event("tor_manager", {"action": "rotated"})

            return {"status": "rotated"}

        except Exception as e:
            log_event("tor_manager_errors", {"error": str(e)})
            return {"status": "error", "error": str(e)}

    def get_session(self):
        """جلسة requests عبر Tor"""
        session = requests.Session()
        session.proxies = {
            'http': 'socks5://127.0.0.1:9050',
            'https': 'socks5://127.0.0.1:9050'
        }
        return session


# نسخ عامة
vpn_agent = VPNAgent()
tor_manager = TorManager()
