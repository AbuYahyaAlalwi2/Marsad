"""
VPN Configuration System - نظام تكوين VPN
- دعم لمزودي VPN متعددين
- تكوين تلقائي لمواقع مقيدة جغرافياً
- إدارة прокسيات
- تبديل تلقائي بين الدول
"""
import os
import json
import random
import requests
import subprocess
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import logging

# إعداد تسجيل الأحداث
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class VPNProvider(Enum):
    """مزودي VPN المدعومين"""
    PROTONVPN = "protonvpn"
    NORDVPN = "nordvpn"
    SURFSHARK = "surfshark"
    WINDSCRIBE = "windscribe"
    OPENVPN = "openvpn"
    WIREGUARD = "wireguard"
    PSIPHON = "psiphon"
    TOR = "tor"
    CUSTOM = "custom"


class CountryCode(Enum):
    """رموز الدول المدعومة"""
    US = "us"
    GB = "gb"
    DE = "de"
    FR = "fr"
    NL = "nl"
    SE = "se"
    CH = "ch"
    CA = "ca"
    JP = "jp"
    SG = "sg"
    AU = "au"
    IN = "in"
    BR = "br"
    RU = "ru"
    CN = "cn"
    AE = "ae"
    SA = "sa"
    EG = "eg"


@dataclass
class VPNConfig:
    """تكوين VPN"""
    provider: VPNProvider
    country: Optional[CountryCode] = None
    server: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    config_file: Optional[str] = None
    protocol: str = "udp"
    port: int = 0
    auto_connect: bool = False
    kill_switch: bool = True
    dns_leak_protection: bool = True
    ipv6_leak_protection: bool = True


@dataclass
class ProxyConfig:
    """تكوين پروكسي"""
    proxy_type: str  # http, https, socks4, socks5
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    country: Optional[str] = None
    anonymous: bool = False


class VPNManager:
    """
    مدير VPN الرئيسي
    - إدارة اتصالات VPN
    - تبديل بين الدول
    - إدارة پروكسيات
    - فحص حالة الاتصال
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """تهئة مدير VPN"""
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self.current_vpn: Optional[VPNConfig] = None
        self.current_proxy: Optional[ProxyConfig] = None
        self.vpn_configs: Dict[str, VPNConfig] = {}
        self.proxy_list: List[ProxyConfig] = []
        self.connected = False
        self._initialized = True
        
        # تحميل التكوينات من ملف
        self._load_configs()
        
        logger.info("VPNManager initialized")
    
    def _load_configs(self):
        """تحميل التكوينات من ملف"""
        config_file = Path("vpn_configs.json")
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    configs = json.load(f)
                    
                # تحميل تكوينات VPN
                for name, config in configs.get("vpn", {}).items():
                    try:
                        vpn_config = VPNConfig(
                            provider=VPNProvider[config.get("provider", "CUSTOM").upper()],
                            country=CountryCode[config.get("country", "US").upper()] if config.get("country") else None,
                            server=config.get("server"),
                            username=config.get("username"),
                            password=config.get("password"),
                            config_file=config.get("config_file"),
                            protocol=config.get("protocol", "udp"),
                            port=config.get("port", 0),
                            auto_connect=config.get("auto_connect", False),
                            kill_switch=config.get("kill_switch", True),
                            dns_leak_protection=config.get("dns_leak_protection", True),
                            ipv6_leak_protection=config.get("ipv6_leak_protection", True)
                        )
                        self.vpn_configs[name] = vpn_config
                    except Exception as e:
                        logger.error(f"Error loading VPN config {name}: {e}")
                
                # تحميل تكوينات پروكسي
                for proxy in configs.get("proxies", []):
                    try:
                        proxy_config = ProxyConfig(
                            proxy_type=proxy.get("type", "http"),
                            host=proxy.get("host"),
                            port=proxy.get("port"),
                            username=proxy.get("username"),
                            password=proxy.get("password"),
                            country=proxy.get("country"),
                            anonymous=proxy.get("anonymous", False)
                        )
                        self.proxy_list.append(proxy_config)
                    except Exception as e:
                        logger.error(f"Error loading proxy config: {e}")
                
                logger.info(f"Loaded {len(self.vpn_configs)} VPN configs and {len(self.proxy_list)} proxies")
            except Exception as e:
                logger.error(f"Error loading VPN configs: {e}")
    
    def save_configs(self):
        """حفظ التكوينات إلى ملف"""
        configs = {
            "vpn": {},
            "proxies": []
        }
        
        # حفظ تكوينات VPN
        for name, config in self.vpn_configs.items():
            configs["vpn"][name] = {
                "provider": config.provider.value,
                "country": config.country.value if config.country else None,
                "server": config.server,
                "username": config.username,
                "password": config.password,
                "config_file": config.config_file,
                "protocol": config.protocol,
                "port": config.port,
                "auto_connect": config.auto_connect,
                "kill_switch": config.kill_switch,
                "dns_leak_protection": config.dns_leak_protection,
                "ipv6_leak_protection": config.ipv6_leak_protection
            }
        
        # حفظ تكوينات پروكسي
        for proxy in self.proxy_list:
            configs["proxies"].append({
                "type": proxy.proxy_type,
                "host": proxy.host,
                "port": proxy.port,
                "username": proxy.username,
                "password": proxy.password,
                "country": proxy.country,
                "anonymous": proxy.anonymous
            })
        
        try:
            with open("vpn_configs.json", 'w') as f:
                json.dump(configs, f, indent=2, ensure_ascii=False)
            logger.info("VPN configs saved")
        except Exception as e:
            logger.error(f"Error saving VPN configs: {e}")
    
    def add_vpn_config(self, name: str, config: VPNConfig):
        """إضافة تكوين VPN جديد"""
        self.vpn_configs[name] = config
        self.save_configs()
        logger.info(f"Added VPN config: {name}")
    
    def add_proxy(self, proxy: ProxyConfig):
        """إضافة پروكسي جديد"""
        self.proxy_list.append(proxy)
        self.save_configs()
        logger.info(f"Added proxy: {proxy.host}:{proxy.port}")
    
    def remove_vpn_config(self, name: str):
        """حذف تكوين VPN"""
        if name in self.vpn_configs:
            del self.vpn_configs[name]
            self.save_configs()
            logger.info(f"Removed VPN config: {name}")
    
    def remove_proxy(self, index: int):
        """حذف پروكسي"""
        if 0 <= index < len(self.proxy_list):
            proxy = self.proxy_list.pop(index)
            self.save_configs()
            logger.info(f"Removed proxy: {proxy.host}:{proxy.port}")
    
    def connect_vpn(self, config_name: str = None) -> bool:
        """الاتصال ب VPN"""
        if config_name:
            if config_name not in self.vpn_configs:
                logger.error(f"VPN config not found: {config_name}")
                return False
            config = self.vpn_configs[config_name]
        elif self.vpn_configs:
            # استخدام أول تكوين متوفر
            config_name = list(self.vpn_configs.keys())[0]
            config = self.vpn_configs[config_name]
        else:
            logger.error("No VPN configs available")
            return False
        
        try:
            self.current_vpn = config
            
            if config.provider == VPNProvider.PROTONVPN:
                return self._connect_protonvpn(config)
            elif config.provider == VPNProvider.NORDVPN:
                return self._connect_nordvpn(config)
            elif config.provider == VPNProvider.OPENVPN:
                return self._connect_openvpn(config)
            elif config.provider == VPNProvider.WIREGUARD:
                return self._connect_wireguard(config)
            elif config.provider == VPNProvider.TOR:
                return self._connect_tor(config)
            else:
                return self._connect_custom(config)
                
        except Exception as e:
            logger.error(f"Error connecting to VPN: {e}")
            self.current_vpn = None
            self.connected = False
            return False
    
    def disconnect_vpn(self) -> bool:
        """فصل VPN"""
        try:
            if self.current_vpn:
                if self.current_vpn.provider == VPNProvider.PROTONVPN:
                    subprocess.run(["pkill", "-f", "protonvpn"], check=False)
                elif self.current_vpn.provider == VPNProvider.NORDVPN:
                    subprocess.run(["nordvpn", "disconnect"], check=False)
                elif self.current_vpn.provider == VPNProvider.OPENVPN:
                    subprocess.run(["pkill", "-f", "openvpn"], check=False)
                elif self.current_vpn.provider == VPNProvider.WIREGUARD:
                    subprocess.run(["wg-quick", "down", self.current_vpn.config_file], check=False)
                elif self.current_vpn.provider == VPNProvider.TOR:
                    subprocess.run(["pkill", "-f", "tor"], check=False)
                
            self.current_vpn = None
            self.connected = False
            logger.info("VPN disconnected")
            return True
        except Exception as e:
            logger.error(f"Error disconnecting VPN: {e}")
            return False
    
    def _connect_protonvpn(self, config: VPNConfig) -> bool:
        """الاتصال ب ProtonVPN"""
        try:
            country = config.country.value if config.country else None
            protocol = config.protocol
            
            cmd = ["protonvpn", "connect"]
            if country:
                cmd.extend(["--country", country])
            if protocol:
                cmd.extend(["--protocol", protocol])
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                self.connected = True
                logger.info(f"Connected to ProtonVPN ({country or 'fastest'})")
                return True
            else:
                logger.error(f"ProtonVPN error: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"Error connecting to ProtonVPN: {e}")
            return False
    
    def _connect_nordvpn(self, config: VPNConfig) -> bool:
        """الاتصال ب NordVPN"""
        try:
            country = config.country.value if config.country else None
            protocol = config.protocol
            
            cmd = ["nordvpn", "connect"]
            if country:
                cmd.append(country)
            if protocol:
                cmd.extend(["--protocol", protocol])
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                self.connected = True
                logger.info(f"Connected to NordVPN ({country or 'fastest'})")
                return True
            else:
                logger.error(f"NordVPN error: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"Error connecting to NordVPN: {e}")
            return False
    
    def _connect_openvpn(self, config: VPNConfig) -> bool:
        """الاتصال ب OpenVPN"""
        try:
            if not config.config_file:
                logger.error("OpenVPN config file not specified")
                return False
            
            cmd = ["sudo", "openvpn", "--config", config.config_file]
            if config.username and config.password:
                # إنشاء ملف credentials
                cred_file = "/tmp/openvpn_cred.txt"
                with open(cred_file, 'w') as f:
                    f.write(f"{config.username}\n{config.password}\n")
                cmd.extend(["--auth-user-pass", cred_file])
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                self.connected = True
                logger.info(f"Connected to OpenVPN ({config.config_file})")
                return True
            else:
                logger.error(f"OpenVPN error: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"Error connecting to OpenVPN: {e}")
            return False
    
    def _connect_wireguard(self, config: VPNConfig) -> bool:
        """الاتصال ب WireGuard"""
        try:
            if not config.config_file:
                logger.error("WireGuard config file not specified")
                return False
            
            result = subprocess.run(
                ["sudo", "wg-quick", "up", config.config_file],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                self.connected = True
                logger.info(f"Connected to WireGuard ({config.config_file})")
                return True
            else:
                logger.error(f"WireGuard error: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"Error connecting to WireGuard: {e}")
            return False
    
    def _connect_tor(self, config: VPNConfig) -> bool:
        """الاتصال ب Tor"""
        try:
            result = subprocess.run(
                ["tor"],
                capture_output=True,
                text=True
            )
            
            # انتظار حتى يتم الاتصال
            time.sleep(5)
            
            # فحص إذا كان Tor يعمل
            try:
                response = requests.get(
                    "https://check.torproject.org/api/ip",
                    proxies={"http": "socks5h://127.0.0.1:9050", "https": "socks5h://127.0.0.1:9050"},
                    timeout=10
                )
                if response.status_code == 200:
                    self.connected = True
                    logger.info("Connected to Tor network")
                    return True
            except:
                pass
            
            logger.error("Failed to connect to Tor")
            return False
        except Exception as e:
            logger.error(f"Error connecting to Tor: {e}")
            return False
    
    def _connect_custom(self, config: VPNConfig) -> bool:
        """الاتصال ب VPN مخصص"""
        logger.warning("Custom VPN connection not implemented")
        return False
    
    def set_proxy(self, proxy: ProxyConfig = None, proxy_index: int = None) -> bool:
        """تعيين پروكسي"""
        if proxy:
            self.current_proxy = proxy
            return True
        elif proxy_index is not None and 0 <= proxy_index < len(self.proxy_list):
            self.current_proxy = self.proxy_list[proxy_index]
            return True
        else:
            logger.error("No proxy specified or invalid index")
            return False
    
    def clear_proxy(self):
        """مسح پروكسي"""
        self.current_proxy = None
        logger.info("Proxy cleared")
    
    def get_proxy_dict(self) -> Optional[Dict[str, str]]:
        """الحصول على پروكسي كقاموس"""
        if self.current_proxy:
            proxy_dict = {}
            proxy_url = f"{self.current_proxy.proxy_type}://{self.current_proxy.host}:{self.current_proxy.port}"
            proxy_dict["http"] = proxy_url
            proxy_dict["https"] = proxy_url
            
            if self.current_proxy.proxy_type in ["socks4", "socks5"]:
                proxy_dict["http"] = f"socks5h://{self.current_proxy.host}:{self.current_proxy.port}"
                proxy_dict["https"] = f"socks5h://{self.current_proxy.host}:{self.current_proxy.port}"
            
            return proxy_dict
        return None
    
    def get_public_ip(self) -> Optional[str]:
        """الحصول على IP عام"""
        try:
            proxies = self.get_proxy_dict() if self.current_proxy else None
            response = requests.get(
                "https://api.ipify.org?format=json",
                proxies=proxies,
                timeout=10
            )
            if response.status_code == 200:
                return response.json().get("ip")
        except Exception as e:
            logger.error(f"Error getting public IP: {e}")
        return None
    
    def get_geo_location(self) -> Optional[Dict[str, Any]]:
        """الحصول على موقع جغرافي"""
        try:
            proxies = self.get_proxy_dict() if self.current_proxy else None
            response = requests.get(
                "https://ipapi.co/json/",
                proxies=proxies,
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.error(f"Error getting geo location: {e}")
        return None
    
    def switch_country(self, country: CountryCode) -> bool:
        """التبديل إلى دولة معينة"""
        # البحث عن تكوين VPN لهذه الدولة
        for name, config in self.vpn_configs.items():
            if config.country == country:
                self.disconnect_vpn()
                return self.connect_vpn(name)
        
        logger.error(f"No VPN config found for country: {country.value}")
        return False
    
    def get_random_country_proxy(self) -> Optional[ProxyConfig]:
        """الحصول على پروكسي لدولة عشوائية"""
        if not self.proxy_list:
            return None
        
        # تصفية پروكسيات الدول المختلفة
        country_proxies = [p for p in self.proxy_list if p.country]
        if country_proxies:
            return random.choice(country_proxies)
        return random.choice(self.proxy_list)
    
    def rotate_proxy(self) -> bool:
        """تدوير پروكسي"""
        if not self.proxy_list:
            logger.error("No proxies available")
            return False
        
        current_index = 0
        if self.current_proxy:
            try:
                current_index = self.proxy_list.index(self.current_proxy)
            except ValueError:
                current_index = 0
        
        next_index = (current_index + 1) % len(self.proxy_list)
        return self.set_proxy(proxy_index=next_index)
    
    def is_connected(self) -> bool:
        """فحص إذا كان متصلاً ب VPN"""
        return self.connected
    
    def get_status(self) -> Dict[str, Any]:
        """الحصول على حالة النظام"""
        return {
            "vpn_connected": self.connected,
            "current_vpn": self.current_vpn.provider.value if self.current_vpn else None,
            "current_country": self.current_vpn.country.value if self.current_vpn and self.current_vpn.country else None,
            "current_proxy": f"{self.current_proxy.host}:{self.current_proxy.port}" if self.current_proxy else None,
            "public_ip": self.get_public_ip(),
            "vpn_configs_count": len(self.vpn_configs),
            "proxies_count": len(self.proxy_list)
        }


# كائن عالمي
vpn_manager = VPNManager()


def connect_to_country(country: str) -> bool:
    """دالة مختصرة للاتصال بدولة معينة"""
    try:
        country_code = CountryCode[country.upper()]
        return vpn_manager.switch_country(country_code)
    except KeyError:
        logger.error(f"Unsupported country: {country}")
        return False


def get_current_ip() -> Optional[str]:
    """دالة مختصرة للحصول على IP الحالي"""
    return vpn_manager.get_public_ip()


def get_proxy_for_request() -> Optional[Dict[str, str]]:
    """دالة مختصرة للحصول على پروكسي للطلب"""
    return vpn_manager.get_proxy_dict()


# تهيئة تلقائية عند استيراد الملف
if __name__ == "__main__":
    print("VPN Manager initialized")
    print(f"Status: {vpn_manager.get_status()}")
