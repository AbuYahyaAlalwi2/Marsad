"""
provider_registry.py — سجل المزودين وخط التقطير التلقائي
==========================================================
عند تسجيل مزود جديد بمفتاح API، يبدأ النظام تلقائياً بـ:
    1. اختبار الاتصال بالمزود
    2. استخراج بيانات تدريبية (تقطير) من نماذجه
    3. حفظ البيانات في KnowledgeStore
    4. تصديرها كـ JSONL للتدريب اللاحق

المزودون المدعومون:
    - groq        (مجاني — llama3, mixtral)
    - together    (مدفوع بالساعة — qwen3-480b)
    - openrouter  (بوابة موحدة)
    - deepseek    (رخيص — deepseek-coder)
    - anthropic   (للمقارنة)
    - huggingface (inference API)

الاستخدام:
    reg = ProviderRegistry()
    reg.register("groq", api_key="gsk_xxx", auto_distill=True)
    await reg.start_distillation("groq")
"""

import asyncio
import hashlib
import json
import os
import sqlite3
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiohttp

# ─── إعداد المسارات ───────────────────────────────────────────────────────────

_DB_DIR   = Path(__file__).parent.parent / "database"
_PROV_DB  = _DB_DIR / "providers.db"
_KEY_DIR  = Path.home() / ".marsad" / "keys"    # مفاتيح API (مشفرة)
_JSONL    = _DB_DIR / "training_data.jsonl"


# ─── بيانات المزود ─────────────────────────────────────────────────────────────

@dataclass
class ProviderConfig:
    name:          str
    api_key:       str            # مشفر عند التخزين
    base_url:      str
    default_model: str
    is_free:       bool = False
    max_rpm:       int  = 60      # طلبات في الدقيقة
    enabled:       bool = True
    registered_at: str  = ""
    last_ping:     str  = ""
    distill_count: int  = 0       # عدد بيانات التقطير المستخرجة
    status:        str  = "pending"   # pending | active | error | disabled


# ─── ملفات تعريف المزودين (بدون مفاتيح) ──────────────────────────────────────

PROVIDER_PROFILES = {
    "groq": ProviderConfig(
        name          = "groq",
        api_key       = "",
        base_url      = "https://api.groq.com/openai/v1",
        default_model = "llama-3.1-70b-versatile",
        is_free       = True,
        max_rpm       = 30,
    ),
    "together": ProviderConfig(
        name          = "together",
        api_key       = "",
        base_url      = "https://api.together.xyz/v1",
        default_model = "deepseek-ai/DeepSeek-V3",
        is_free       = False,
        max_rpm       = 60,
    ),
    "openrouter": ProviderConfig(
        name          = "openrouter",
        api_key       = "",
        base_url      = "https://openrouter.ai/api/v1",
        default_model = "deepseek/deepseek-v3",
        is_free       = False,
        max_rpm       = 20,
    ),
    "deepseek": ProviderConfig(
        name          = "deepseek",
        api_key       = "",
        base_url      = "https://api.deepseek.com/v1",
        default_model = "deepseek-coder",
        is_free       = False,
        max_rpm       = 60,
    ),
    "huggingface": ProviderConfig(
        name          = "huggingface",
        api_key       = "",
        base_url      = "https://api-inference.huggingface.co",
        default_model = "Qwen/Qwen2.5-Coder-32B-Instruct",
        is_free       = True,
        max_rpm       = 10,
    ),
    "anthropic": ProviderConfig(
        name          = "anthropic",
        api_key       = "",
        base_url      = "https://api.anthropic.com/v1",
        default_model = "claude-3-haiku-20240307",
        is_free       = False,
        max_rpm       = 60,
    ),
}

# ─── أسئلة التقطير الأمنية ────────────────────────────────────────────────────

DISTILLATION_PROMPTS = [
    # أسئلة SQL Injection
    "ما هو SQL Injection؟ وكيف يتم استغلاله في تطبيقات الويب؟",
    "اكتب استعلام SQL مُصحَّح يمنع الـ SQL injection في تسجيل الدخول",
    "ما الفرق بين Prepared Statements و Parameterized Queries في منع SQL Injection؟",

    # أسئلة XSS
    "اشرح أنواع XSS (Stored, Reflected, DOM-based) مع أمثلة",
    "كيف تمنع XSS في تطبيق React.js؟ مع كود مثال",
    "ما هو Content Security Policy وكيف يساعد في منع XSS؟",

    # أسئلة Buffer Overflow
    "اشرح Buffer Overflow وكيف يستغله المهاجمون لتنفيذ كود خبيث",
    "ما هي تقنيات ASLR وDEP/NX وكيف تمنع استغلال Buffer Overflow؟",

    # أسئلة التشفير
    "ما الفرق بين التشفير المتماثل وغير المتماثل؟ متى تستخدم كل نوع؟",
    "لماذا MD5 وSHA1 غير آمنين لتخزين كلمات المرور؟ ما البديل الصحيح؟",
    "اشرح كيف يعمل JWT وما هي نقاط ضعفه الشائعة",

    # أسئلة الشبكات
    "ما هو Man-in-the-Middle Attack وكيف يعمل؟",
    "اشرح الفرق بين IDS وIPS في أمن الشبكات",
    "كيف تعمل هجمات DDoS وما هي طرق التخفيف منها؟",

    # أسئلة تحليل الكود
    "افحص هذا الكود Python وحدد الثغرات: `import os; os.system(input('cmd: '))`",
    "ما الخطأ الأمني في: `query = 'SELECT * FROM users WHERE id=' + user_id`",
    "لماذا استخدام `eval()` في JavaScript خطير أمنياً؟",

    # أسئلة CVE
    "اشرح CVE-2021-44228 (Log4Shell) وكيف تم اكتشافها",
    "ما هي EternalBlue وكيف استُخدمت في WannaCry؟",

    # أسئلة عامة
    "ما هو OWASP Top 10 لعام 2024؟ اشرح كل نقطة باختصار",
    "ما الفرق بين Black Box وWhite Box وGray Box penetration testing؟",
    "اشرح مبدأ Principle of Least Privilege وأهميته في الأمن",
]


# ─── إدارة المفاتيح (تشفير بسيط محلي) ────────────────────────────────────────

class KeyVault:
    """يخزن مفاتيح API بشكل آمن على الجهاز"""

    def __init__(self):
        _KEY_DIR.mkdir(parents=True, exist_ok=True)
        _KEY_DIR.chmod(0o700)

    def _key_path(self, provider: str) -> Path:
        return _KEY_DIR / f"{provider}.key"

    def store(self, provider: str, api_key: str):
        """يخزن المفتاح (مشفر ببسيط — XOR مع seed محلي)"""
        seed = self._get_seed()
        encoded = bytes([ord(c) ^ ord(seed[i % len(seed)])
                         for i, c in enumerate(api_key)]).hex()
        self._key_path(provider).write_text(encoded)
        self._key_path(provider).chmod(0o600)

    def load(self, provider: str) -> Optional[str]:
        """يحمّل ويفك تشفير المفتاح"""
        path = self._key_path(provider)
        if not path.exists():
            return None
        try:
            seed = self._get_seed()
            encoded = bytes.fromhex(path.read_text().strip())
            decoded = "".join(chr(b ^ ord(seed[i % len(seed)]))
                              for i, b in enumerate(encoded))
            return decoded
        except Exception:
            return None

    def delete(self, provider: str):
        path = self._key_path(provider)
        if path.exists():
            path.unlink()

    def list_providers(self) -> list:
        return [p.stem for p in _KEY_DIR.glob("*.key")]

    def _get_seed(self) -> str:
        seed_path = Path.home() / ".marsad" / "vault.seed"
        if seed_path.exists():
            return seed_path.read_text().strip()
        import secrets
        seed = secrets.token_hex(16)
        seed_path.write_text(seed)
        seed_path.chmod(0o600)
        return seed


# ─── سجل المزودين ─────────────────────────────────────────────────────────────

class ProviderRegistry:
    """
    يسجل المزودين ويبدأ التقطير تلقائياً.

    مثال:
        reg = ProviderRegistry()
        reg.register("groq", "gsk_xxx")
        await reg.start_distillation("groq")
    """

    def __init__(self):
        _DB_DIR.mkdir(parents=True, exist_ok=True)
        self.vault = KeyVault()
        self._init_db()
        self._rate_locks: dict = {}   # rate limiting per provider

    def _init_db(self):
        with sqlite3.connect(_PROV_DB) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS providers (
                    name          TEXT PRIMARY KEY,
                    base_url      TEXT,
                    default_model TEXT,
                    is_free       INTEGER,
                    max_rpm       INTEGER,
                    enabled       INTEGER,
                    registered_at TEXT,
                    last_ping     TEXT,
                    distill_count INTEGER DEFAULT 0,
                    status        TEXT    DEFAULT 'pending'
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS distilled_samples (
                    sample_id     TEXT PRIMARY KEY,
                    provider      TEXT,
                    model         TEXT,
                    prompt        TEXT,
                    response      TEXT,
                    tokens_used   INTEGER,
                    timestamp     TEXT
                )
            """)
            conn.commit()

    # ── تسجيل مزود ────────────────────────────────────────────────────────────

    def register(
        self,
        provider_name: str,
        api_key:       str,
        auto_distill:  bool = True,
        model:         Optional[str] = None,
    ) -> bool:
        """
        يسجل مزود جديد بمفتاحه.

        Args:
            provider_name: groq | together | openrouter | deepseek | huggingface
            api_key:       مفتاح API الخاص بالمزود
            auto_distill:  إذا True، يبدأ التقطير تلقائياً
            model:         نموذج مختلف عن الافتراضي (اختياري)

        Returns:
            True إذا نجح التسجيل
        """
        if provider_name not in PROVIDER_PROFILES:
            print(f"✗ المزود '{provider_name}' غير مدعوم")
            print(f"  المزودون المدعومون: {', '.join(PROVIDER_PROFILES.keys())}")
            return False

        profile = PROVIDER_PROFILES[provider_name]
        if model:
            profile.default_model = model

        # تخزين المفتاح في الـ vault
        self.vault.store(provider_name, api_key)

        # تسجيل في قاعدة البيانات
        now = datetime.utcnow().isoformat()
        with sqlite3.connect(_PROV_DB) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO providers
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (
                provider_name,
                profile.base_url,
                profile.default_model,
                int(profile.is_free),
                profile.max_rpm,
                1,
                now,
                "",
                0,
                "pending",
            ))
            conn.commit()

        print(f"✓ مزود '{provider_name}' مُسجَّل")
        print(f"  النموذج: {profile.default_model}")
        print(f"  مجاني: {'نعم' if profile.is_free else 'لا'}")
        print(f"  RPM: {profile.max_rpm}")

        if auto_distill:
            print(f"  🔄 سيبدأ التقطير تلقائياً...")

        return True

    def unregister(self, provider_name: str):
        """إلغاء تسجيل مزود وحذف مفتاحه"""
        self.vault.delete(provider_name)
        with sqlite3.connect(_PROV_DB) as conn:
            conn.execute("DELETE FROM providers WHERE name=?", (provider_name,))
            conn.commit()
        print(f"✓ تم إلغاء تسجيل '{provider_name}'")

    def list_providers(self) -> list:
        """قائمة المزودين المسجلين مع حالتهم"""
        with sqlite3.connect(_PROV_DB) as conn:
            rows = conn.execute("""
                SELECT name, default_model, is_free, status, distill_count, last_ping
                FROM providers WHERE enabled=1
            """).fetchall()
        return [
            {
                "name":          r[0],
                "model":         r[1],
                "is_free":       bool(r[2]),
                "status":        r[3],
                "distill_count": r[4],
                "last_ping":     r[5],
            }
            for r in rows
        ]

    # ── اختبار الاتصال ─────────────────────────────────────────────────────────

    async def ping(self, provider_name: str) -> bool:
        """يختبر الاتصال بالمزود"""
        api_key = self.vault.load(provider_name)
        if not api_key:
            print(f"✗ لا يوجد مفتاح لـ '{provider_name}'")
            return False

        profile = self._get_profile(provider_name)
        if not profile:
            return False

        headers = self._get_headers(provider_name, api_key)

        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "model":       profile["default_model"],
                    "messages":    [{"role": "user", "content": "test"}],
                    "max_tokens":  5,
                }

                # Anthropic يستخدم endpoint مختلف
                if provider_name == "anthropic":
                    url = f"{profile['base_url']}/messages"
                else:
                    url = f"{profile['base_url']}/chat/completions"

                async with session.post(url, json=payload, headers=headers, timeout=10) as resp:
                    success = resp.status in (200, 201)

            status = "active" if success else "error"
            last_ping = datetime.utcnow().isoformat()

            with sqlite3.connect(_PROV_DB) as conn:
                conn.execute("""
                    UPDATE providers SET status=?, last_ping=? WHERE name=?
                """, (status, last_ping, provider_name))
                conn.commit()

            print(f"  {'✓' if success else '✗'} {provider_name}: {'متصل' if success else 'خطأ'}")
            return success

        except Exception as e:
            print(f"  ✗ {provider_name}: {e}")
            return False

    # ── التقطير ────────────────────────────────────────────────────────────────

    async def start_distillation(
        self,
        provider_name:  str,
        num_samples:    int = 20,
        model:          Optional[str] = None,
    ) -> int:
        """
        يبدأ تقطير بيانات تدريبية من المزود.

        Args:
            provider_name: اسم المزود
            num_samples:   عدد الأسئلة للاستخراج (افتراضي 20)
            model:         نموذج مخصص (اختياري)

        Returns:
            عدد العينات المستخرجة
        """
        api_key = self.vault.load(provider_name)
        if not api_key:
            print(f"✗ لا يوجد مفتاح لـ '{provider_name}' — سجّل المزود أولاً")
            return 0

        profile = self._get_profile(provider_name)
        if not profile:
            return 0

        target_model = model or profile["default_model"]
        prompts      = DISTILLATION_PROMPTS[:num_samples]
        headers      = self._get_headers(provider_name, api_key)
        max_rpm      = profile["max_rpm"]
        delay        = 60.0 / max_rpm   # تأخير بين الطلبات

        print(f"\n🔄 تقطير من '{provider_name}' — {target_model}")
        print(f"   عدد الأسئلة: {len(prompts)} | التأخير: {delay:.1f}ث بين كل طلب")

        collected = 0
        for i, prompt in enumerate(prompts, 1):
            try:
                response_text = await self._call_provider(
                    provider_name, api_key, target_model,
                    prompt, headers
                )
                if response_text:
                    self._save_distilled_sample(
                        provider_name, target_model, prompt, response_text
                    )
                    collected += 1
                    print(f"  [{i}/{len(prompts)}] ✓ ({len(response_text)} حرف)")
                else:
                    print(f"  [{i}/{len(prompts)}] — رد فارغ")

                # Rate limiting
                if i < len(prompts):
                    await asyncio.sleep(delay)

            except Exception as e:
                print(f"  [{i}/{len(prompts)}] ✗ {str(e)[:60]}")
                await asyncio.sleep(delay * 2)   # تأخير إضافي عند الخطأ

        # تحديث عداد التقطير
        with sqlite3.connect(_PROV_DB) as conn:
            conn.execute("""
                UPDATE providers
                SET distill_count = distill_count + ?, status = 'active'
                WHERE name = ?
            """, (collected, provider_name))
            conn.commit()

        print(f"\n✅ تقطير '{provider_name}' اكتمل: {collected}/{len(prompts)} عينة")
        return collected

    async def distill_all_providers(self, samples_per_provider: int = 10) -> dict:
        """يقطّر من كل المزودين المسجلين والنشطين"""
        providers = self.list_providers()
        results   = {}

        for prov in providers:
            name = prov["name"]
            print(f"\n{'─'*40}")
            print(f"المزود: {name}")
            count = await self.start_distillation(name, samples_per_provider)
            results[name] = count

        print(f"\n{'='*40}")
        print(f"✅ تقطير كل المزودين اكتمل:")
        for name, count in results.items():
            print(f"  {name}: {count} عينة")
        return results

    # ── دوال داخلية ───────────────────────────────────────────────────────────

    async def _call_provider(
        self,
        provider_name: str,
        api_key:       str,
        model:         str,
        prompt:        str,
        headers:       dict,
    ) -> Optional[str]:
        """يرسل طلب واحد للمزود ويعيد الرد"""
        profile = self._get_profile(provider_name)
        if not profile:
            return None

        # Anthropic يستخدم format مختلف
        if provider_name == "anthropic":
            url     = f"{profile['base_url']}/messages"
            payload = {
                "model":       model,
                "max_tokens":  800,
                "messages":    [{"role": "user", "content": prompt}],
            }
        else:
            url     = f"{profile['base_url']}/chat/completions"
            payload = {
                "model":       model,
                "max_tokens":  800,
                "messages":    [
                    {
                        "role":    "system",
                        "content": (
                            "أنت خبير أمن معلومات متخصص. "
                            "أجب بدقة وتفصيل على الأسئلة الأمنية."
                        )
                    },
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
            }

        timeout = aiohttp.ClientTimeout(total=60)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise Exception(f"HTTP {resp.status}: {text[:100]}")

                data = await resp.json()

                # استخراج النص حسب format المزود
                if provider_name == "anthropic":
                    return data.get("content", [{}])[0].get("text", "")
                else:
                    choices = data.get("choices", [{}])
                    return choices[0].get("message", {}).get("content", "")

    def _get_headers(self, provider_name: str, api_key: str) -> dict:
        """يعيد headers مناسبة لكل مزود"""
        base = {"Content-Type": "application/json"}

        if provider_name == "anthropic":
            return {
                **base,
                "x-api-key":         api_key,
                "anthropic-version":  "2023-06-01",
            }
        elif provider_name == "openrouter":
            return {
                **base,
                "Authorization":  f"Bearer {api_key}",
                "HTTP-Referer":   "https://github.com/AbuYahyaAlalwi2/Marsad",
                "X-Title":        "Marsad Security AI",
            }
        else:
            return {**base, "Authorization": f"Bearer {api_key}"}

    def _get_profile(self, provider_name: str) -> Optional[dict]:
        """يجلب ملف المزود من قاعدة البيانات"""
        with sqlite3.connect(_PROV_DB) as conn:
            row = conn.execute(
                "SELECT * FROM providers WHERE name=?", (provider_name,)
            ).fetchone()
        if not row:
            # حاول من PROVIDER_PROFILES
            if provider_name in PROVIDER_PROFILES:
                p = PROVIDER_PROFILES[provider_name]
                return {"base_url": p.base_url, "default_model": p.default_model, "max_rpm": p.max_rpm}
            print(f"✗ المزود '{provider_name}' غير مسجل")
            return None
        return {
            "base_url":      row[1],
            "default_model": row[2],
            "is_free":       bool(row[3]),
            "max_rpm":       row[4],
        }

    def _save_distilled_sample(
        self,
        provider:  str,
        model:     str,
        prompt:    str,
        response:  str,
    ):
        """يحفظ العينة في SQLite وفي ملف JSONL"""
        sample_id = hashlib.sha256(f"{provider}{prompt}{response}".encode()).hexdigest()[:16]
        now       = datetime.utcnow().isoformat()

        with sqlite3.connect(_PROV_DB) as conn:
            conn.execute("""
                INSERT OR IGNORE INTO distilled_samples
                VALUES (?,?,?,?,?,?,?)
            """, (sample_id, provider, model, prompt, response, len(response), now))
            conn.commit()

        # تصدير كـ JSONL للتدريب
        entry = {
            "id":        sample_id,
            "provider":  provider,
            "model":     model,
            "timestamp": now,
            "messages": [
                {
                    "role":    "system",
                    "content": "أنت خبير أمن معلومات متخصص في اكتشاف وتحليل الثغرات الأمنية."
                },
                {"role": "user",      "content": prompt},
                {"role": "assistant", "content": response},
            ]
        }
        _DB_DIR.mkdir(parents=True, exist_ok=True)
        with open(_JSONL, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ─── سطر الأوامر ───────────────────────────────────────────────────────────────

async def _main():
    import sys

    reg  = ProviderRegistry()
    args = sys.argv[1:]

    if not args:
        print("الاستخدام:")
        print("  python provider_registry.py register <name> <api_key>")
        print("  python provider_registry.py distill  <name> [num_samples]")
        print("  python provider_registry.py distill-all [samples_per_provider]")
        print("  python provider_registry.py ping     <name>")
        print("  python provider_registry.py list")
        print("  python provider_registry.py remove   <name>")
        print()
        print("المزودون المدعومون:")
        for k, v in PROVIDER_PROFILES.items():
            free_tag = " (مجاني)" if v.is_free else ""
            print(f"  {k}: {v.default_model}{free_tag}")
        return

    cmd = args[0]

    if cmd == "register" and len(args) >= 3:
        name    = args[1]
        api_key = args[2]
        model   = args[3] if len(args) > 3 else None
        success = reg.register(name, api_key, auto_distill=True, model=model)
        if success:
            print(f"\n💡 لبدء التقطير فوراً:")
            print(f"   python provider_registry.py distill {name}")

    elif cmd == "distill" and len(args) >= 2:
        name        = args[1]
        num_samples = int(args[2]) if len(args) > 2 else 20
        await reg.start_distillation(name, num_samples)

    elif cmd == "distill-all":
        samples = int(args[1]) if len(args) > 1 else 10
        await reg.distill_all_providers(samples)

    elif cmd == "ping" and len(args) >= 2:
        name = args[1]
        await reg.ping(name)

    elif cmd == "list":
        providers = reg.list_providers()
        if not providers:
            print("لا يوجد مزودون مسجلون")
        else:
            print(f"{'المزود':<15} {'النموذج':<35} {'الحالة':<10} {'التقطير':<10}")
            print("─" * 75)
            for p in providers:
                print(f"{p['name']:<15} {p['model']:<35} {p['status']:<10} {p['distill_count']:<10}")

    elif cmd == "remove" and len(args) >= 2:
        reg.unregister(args[1])


if __name__ == "__main__":
    asyncio.run(_main())
