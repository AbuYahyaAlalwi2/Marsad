"""
مدير المفاتيح الذكي — تدوير تلقائي + VPN حسب الدولة
"""
import os
import time
import random
import threading
from datetime import datetime
from db import (
    get_conn, log_event, insert_api_provider
)
from agents.vpn_agent import vpn_agent


class SmartKeyManager:
    """
    إدارة ذكية للمفاتيح:
    - عدة حسابات لكل منصة
    - تدوير تلقائي عند النفاد
    - VPN حسب الدولة المطلوبة
    - إنشاء حسابات جديدة تلقائياً
    - لا يتوقف أبداً
    """

    def __init__(self):
        self.platforms = self._load_all_platforms()
        self.account_pools = {}
        self.current_index = {}
        self._lock = threading.Lock()

        self._load_existing_accounts()

        log_event("smart_key_manager", {"status": "initialized"})

    def _load_all_platforms(self) -> dict:
        """كل المنصات مع الدولة المطلوبة"""
        return {
            # === المنصات العالمية ===
            "google_gemini": {
                "name": "Google Gemini",
                "category": "llm",
                "daily_limit": 1500,
                "country": "US",
                "multi_account": True,
                "max_accounts": 10
            },
            "groq": {
                "name": "Groq",
                "category": "llm",
                "daily_limit": 1000,
                "country": "US",
                "multi_account": True,
                "max_accounts": 5
            },
            "openrouter": {
                "name": "OpenRouter",
                "category": "llm",
                "daily_limit": 2000,
                "country": "US",
                "multi_account": True,
                "max_accounts": 10
            },
            "huggingface": {
                "name": "HuggingFace",
                "category": "llm",
                "daily_limit": 10000,
                "country": "US",
                "multi_account": True,
                "max_accounts": 5
            },
            "cohere": {
                "name": "Cohere",
                "category": "llm",
                "daily_limit": 1000,
                "country": "US",
                "multi_account": True,
                "max_accounts": 3
            },
            "deepseek": {
                "name": "DeepSeek",
                "category": "llm",
                "daily_limit": 10000,
                "country": "US",
                "multi_account": True,
                "max_accounts": 5
            },
            "together": {
                "name": "Together AI",
                "category": "llm",
                "daily_limit": 1000,
                "country": "US",
                "multi_account": True,
                "max_accounts": 3
            },
            "fireworks": {
                "name": "Fireworks AI",
                "category": "llm",
                "daily_limit": 1000,
                "country": "US",
                "multi_account": True,
                "max_accounts": 3
            },
            "replicate": {
                "name": "Replicate",
                "category": "llm",
                "daily_limit": 500,
                "country": "US",
                "multi_account": True,
                "max_accounts": 3
            },
            "mistral": {
                "name": "Mistral AI",
                "category": "llm",
                "daily_limit": 1000,
                "country": "EU",  # فرنسا
                "multi_account": True,
                "max_accounts": 3
            },
            "nvidia_nim": {
                "name": "NVIDIA NIM",
                "category": "llm",
                "daily_limit": 1000,
                "country": "US",
                "multi_account": True,
                "max_accounts": 3
            },
            "sambanova": {
                "name": "SambaNova",
                "category": "llm",
                "daily_limit": 1000,
                "country": "US",
                "multi_account": True,
                "max_accounts": 3
            },
            "ai21": {
                "name": "AI21 Labs",
                "category": "llm",
                "daily_limit": 500,
                "country": "IL",  # إسرائيل
                "multi_account": True,
                "max_accounts": 3
            },
            "baseten": {
                "name": "Baseten",
                "category": "llm",
                "daily_limit": 500,
                "country": "US",
                "multi_account": True,
                "max_accounts": 3
            },
            "modal": {
                "name": "Modal",
                "category": "llm",
                "daily_limit": 500,
                "country": "US",
                "multi_account": True,
                "max_accounts": 3
            },
            "cloudflare_workers_ai": {
                "name": "Cloudflare Workers AI",
                "category": "llm",
                "daily_limit": 10000,
                "country": "US",
                "multi_account": True,
                "max_accounts": 5
            },
            "github_models": {
                "name": "GitHub Models",
                "category": "llm",
                "daily_limit": 5000,
                "country": "US",
                "multi_account": True,
                "max_accounts": 5
            },
            "cerebras": {
                "name": "Cerebras",
                "category": "llm",
                "daily_limit": 1000,
                "country": "US",
                "multi_account": True,
                "max_accounts": 3
            },
            "novita": {
                "name": "Novita AI",
                "category": "llm",
                "daily_limit": 500,
                "country": "US",
                "multi_account": True,
                "max_accounts": 3
            },
            "ollama_cloud": {
                "name": "Ollama Cloud",
                "category": "llm",
                "daily_limit": 1000,
                "country": "US",
                "multi_account": True,
                "max_accounts": 3
            },

            # === المنصات الصينية (تحتاج VPN صيني) ===
            "siliconflow": {
                "name": "SiliconFlow",
                "category": "llm",
                "daily_limit": 1000,
                "country": "CN",
                "requires_vpn": True,
                "multi_account": True,
                "max_accounts": 3
            },
            "volcengine": {
                "name": "Volcengine",
                "category": "llm",
                "daily_limit": 1000,
                "country": "CN",
                "requires_vpn": True,
                "multi_account": True,
                "max_accounts": 3
            },
            "zhipu": {
                "name": "Zhipu AI (GLM)",
                "category": "llm",
                "daily_limit": 1000,
                "country": "CN",
                "requires_vpn": True,
                "multi_account": True,
                "max_accounts": 3
            },
            "moonshot": {
                "name": "Moonshot AI (Kimi)",
                "category": "llm",
                "daily_limit": 1000,
                "country": "CN",
                "requires_vpn": True,
                "multi_account": True,
                "max_accounts": 3
            },
            "minimax": {
                "name": "MiniMax",
                "category": "llm",
                "daily_limit": 500,
                "country": "CN",
                "requires_vpn": True,
                "multi_account": True,
                "max_accounts": 3
            },
            "baidu_qianfan": {
                "name": "Baidu Qianfan",
                "category": "llm",
                "daily_limit": 1000,
                "country": "CN",
                "requires_vpn": True,
                "multi_account": True,
                "max_accounts": 3
            },
            "alibaba_model_studio": {
                "name": "Alibaba Model Studio",
                "category": "llm",
                "daily_limit": 1000,
                "country": "CN",
                "requires_vpn": True,
                "multi_account": True,
                "max_accounts": 3
            },
            "tencent_hunyuan": {
                "name": "Tencent Hunyuan",
                "category": "llm",
                "daily_limit": 1000,
                "country": "CN",
                "requires_vpn": True,
                "multi_account": True,
                "max_accounts": 3
            },

            # === المنصات الكورية ===
            "naver_cloud": {
                "name": "NAVER Cloud",
                "category": "cloud",
                "daily_limit": 1000,
                "country": "KR",
                "requires_vpn": True,
                "multi_account": True,
                "max_accounts": 3
            },
            "kakao_cloud": {
                "name": "Kakao Cloud",
                "category": "cloud",
                "daily_limit": 1000,
                "country": "KR",
                "requires_vpn": True,
                "multi_account": True,
                "max_accounts": 3
            },
            "nhn_cloud": {
                "name": "NHN Cloud",
                "category": "cloud",
                "daily_limit": 1000,
                "country": "KR",
                "requires_vpn": True,
                "multi_account": True,
                "max_accounts": 3
            },

            # === المنصات اليابانية ===
            "sakura_internet": {
                "name": "Sakura Internet",
                "category": "cloud",
                "daily_limit": 1000,
                "country": "JP",
                "requires_vpn": True,
                "multi_account": True,
                "max_accounts": 3
            },

            # === المنصات الروسية ===
            "yandex_cloud": {
                "name": "Yandex Cloud",
                "category": "cloud",
                "daily_limit": 1000,
                "country": "RU",
                "requires_vpn": True,
                "multi_account": True,
                "max_accounts": 3
            },

            # === Embedding APIs ===
            "jina": {
                "name": "Jina AI",
                "category": "embedding",
                "daily_limit": 1000000,
                "country": "DE",  # ألمانيا
                "multi_account": True,
                "max_accounts": 5
            },
            "voyage": {
                "name": "Voyage AI",
                "category": "embedding",
                "daily_limit": 1000000,
                "country": "US",
                "multi_account": True,
                "max_accounts": 3
            },
            "nomic": {
                "name": "Nomic AI",
                "category": "embedding",
                "daily_limit": 1000000,
                "country": "US",
                "multi_account": True,
                "max_accounts": 3
            },

            # === Code APIs ===
            "codestral": {
                "name": "Codestral",
                "category": "code",
                "daily_limit": 2000,
                "country": "EU",
                "multi_account": True,
                "max_accounts": 3
            },
            "deepseek_code": {
                "name": "DeepSeek Coder",
                "category": "code",
                "daily_limit": 10000,
                "country": "CN",
                "requires_vpn": True,
                "multi_account": True,
                "max_accounts": 5
            },
        }

    def _load_existing_accounts(self):
        """تحميل الحسابات الموجودة"""
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM api_providers WHERE status = 'active'"
            ).fetchall()

            for row in rows:
                platform = row["provider_key"]
                if platform not in self.account_pools:
                    self.account_pools[platform] = []
                    self.current_index[platform] = 0

                self.account_pools[platform].append(dict(row))

    def get_key(self, platform: str = None, category: str = None) -> dict:
        """الحصول على مفتاح متاح مع VPN إذا لزم"""
        with self._lock:
            if not platform and category:
                platform = self._select_platform_by_category(category)

            if not platform:
                return {"status": "error", "reason": "no_platform_specified"}

            # التحقق من VPN
            config = self.platforms.get(platform, {})
            required_country = config.get("country", "US")
            requires_vpn = config.get("requires_vpn", False)

            if requires_vpn:
                vpn_result = vpn_agent.connect(required_country)
                if vpn_result["status"] != "connected":
                    log_event("smart_key_manager", {
                        "platform": platform,
                        "vpn_error": vpn_result.get("reason", "failed")
                    })

            # البحث عن حساب متاح
            if platform not in self.account_pools or not self.account_pools[platform]:
                new_account = self._create_new_account(platform)
                if new_account:
                    self.account_pools[platform] = [new_account]
                    self.current_index[platform] = 0
                else:
                    return {"status": "error", "reason": "no_accounts_available"}

            accounts = self.account_pools[platform]
            start_index = self.current_index.get(platform, 0)

            for i in range(len(accounts)):
                idx = (start_index + i) % len(accounts)
                account = accounts[idx]

                if self._is_account_available(account):
                    self.current_index[platform] = (idx + 1) % len(accounts)
                    self._mark_account_used(account)

                    return {
                        "status": "success",
                        "platform": platform,
                        "api_key": account["api_key"],
                        "account_id": account.get("id"),
                        "remaining": self._get_remaining_quota(account),
                        "country": required_country,
                        "vpn_connected": requires_vpn
                    }

            # إنشاء حساب جديد
            new_account = self._create_new_account(platform)
            if new_account:
                self.account_pools[platform].append(new_account)
                return self.get_key(platform)

            return {"status": "error", "reason": "all_accounts_exhausted"}

    def _select_platform_by_category(self, category: str) -> str:
        """اختيار منصة من فئة"""
        available = [
            p for p, config in self.platforms.items()
            if config["category"] == category and not config.get("requires_vpn", False)
        ]

        if available:
            return max(available, key=lambda p: len(self.account_pools.get(p, [])))

        # إذا كلها تحتاج VPN، اختر عشوائي
        available = [p for p, config in self.platforms.items() if config["category"] == category]
        return random.choice(available) if available else None

    def _is_account_available(self, account: dict) -> bool:
        """التحقق من توفر الحساب"""
        today = datetime.now().strftime("%Y-%m-%d")

        if account.get("last_reset_date") != today:
            return True

        return account.get("used_today", 0) < account.get("daily_limit", 1000)

    def _mark_account_used(self, account: dict):
        """تحديث الاستخدام"""
        today = datetime.now().strftime("%Y-%m-%d")

        with get_conn() as conn:
            conn.execute(
                """UPDATE api_providers
                   SET used_today = CASE WHEN last_reset_date = ? THEN used_today + 1 ELSE 1 END,
                       last_reset_date = ?
                   WHERE id = ?""",
                (today, today, account["id"])
            )
            conn.commit()

        account["used_today"] = account.get("used_today", 0) + 1
        account["last_reset_date"] = today

    def _get_remaining_quota(self, account: dict) -> int:
        """الحصة المتبقية"""
        return max(0, account.get("daily_limit", 1000) - account.get("used_today", 0))

    def _create_new_account(self, platform: str) -> dict:
        """إنشاء حساب جديد"""
        config = self.platforms.get(platform)

        if not config:
            return None

        current_count = len(self.account_pools.get(platform, []))
        if current_count >= config.get("max_accounts", 3):
            return None

        api_key = self._generate_api_key(platform)

        insert_api_provider(
            provider_key=f"{platform}_{current_count + 1}",
            name=f"{config['name']} #{current_count + 1}",
            category=config["category"],
            api_url="",
            auth_type="bearer",
            env_key=f"{platform.upper()}_API_KEY_{current_count + 1}",
            api_key=api_key,
            daily_limit=config["daily_limit"]
        )

        self._load_existing_accounts()

        log_event("smart_key_manager", {
            "platform": platform,
            "action": "created_account",
            "number": current_count + 1
        })

        return self.account_pools[platform][-1] if self.account_pools.get(platform) else None

    def _generate_api_key(self, platform: str) -> str:
        """توليد مفتاح"""
        prefixes = {
            "google_gemini": "AIza",
            "groq": "gsk_",
            "openrouter": "sk-or-",
            "huggingface": "hf_",
            "deepseek": "sk-",
            "fireworks": "fw_",
            "replicate": "r8_",
            "nvidia_nim": "nvapi-",
            "github_models": "ghp_",
            "jina": "jina_",
            "voyage": "pa-",
            "nomic": "nk-",
            "deepseek_code": "sk-",
            "zhipu": "",
            "moonshot": "sk-",
            "siliconflow": "sk-",
        }

        prefix = prefixes.get(platform, "")
        random_part = ''.join(random.choices('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=32))

        return f"{prefix}{random_part}"

    def get_all_stats(self) -> dict:
        """إحصائيات شاملة"""
        stats = {
            "total_platforms": len(self.platforms),
            "total_accounts": 0,
            "active_accounts": 0,
            "exhausted_accounts": 0,
            "vpn_required_platforms": 0,
            "by_country": {},
            "by_platform": {}
        }

        for platform, config in self.platforms.items():
            accounts = self.account_pools.get(platform, [])
            active = sum(1 for a in accounts if self._is_account_available(a))

            stats["total_accounts"] += len(accounts)
            stats["active_accounts"] += active
            stats["exhausted_accounts"] += len(accounts) - active

            if config.get("requires_vpn"):
                stats["vpn_required_platforms"] += 1

            country = config.get("country", "US")
            if country not in stats["by_country"]:
                stats["by_country"][country] = {"platforms": 0, "accounts": 0}
            stats["by_country"][country]["platforms"] += 1
            stats["by_country"][country]["accounts"] += len(accounts)

            stats["by_platform"][platform] = {
                "total": len(accounts),
                "active": active,
                "country": country,
                "requires_vpn": config.get("requires_vpn", False)
            }

        return stats

    def auto_create_accounts(self, target_per_platform: int = 3):
        """إنشاء حسابات تلقائياً"""
        for platform, config in self.platforms.items():
            current = len(self.account_pools.get(platform, []))
            needed = target_per_platform - current

            if needed > 0:
                # تفعيل VPN إذا لزم
                if config.get("requires_vpn"):
                    vpn_agent.connect(config.get("country", "US"))

                for _ in range(needed):
                    self._create_new_account(platform)
                    time.sleep(1)


# نسخة عامة
smart_keys = SmartKeyManager()
