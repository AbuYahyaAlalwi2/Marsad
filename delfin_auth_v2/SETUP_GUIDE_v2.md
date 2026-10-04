# دليل نظام المصادقة الآلي — Del Auth v2

## الهيكل

```
Dolphin/
├── delfin_os/
│   ├── auth/
│   │   ├── provider_registry.py   ← سجل 15 مزود + ProviderMeta
│   │   ├── token_vault.py         ← خزنة مشفرة (AES-128)
│   │   ├── browser_login.py       ← تسجيل دخول آلي بـ Playwright
│   │   ├── session_manager.py     ← المنسق الرئيسي
│   │   └── del_auth_tool.py       ← واجهة Del
│   └── vault/
│       ├── vault.enc              ← مفاتيح مشفرة (تُنشأ آلياً)
│       └── .vault_key             ← مفتاح التشفير (chmod 600)
├── .env                           ← يُحدَّث آلياً بعد كل مفتاح
└── config.json                    ← يُحدَّث آلياً
```

## التثبيت (مرة واحدة فقط)

```powershell
# في مجلد Dolphin
pip install cryptography playwright
playwright install chromium
```

## خطوة واحدة: أعطِ Del الإذن

```python
from delfin_os.auth.del_auth_tool import DelAuthTool

tool = DelAuthTool()

# مثال: Groq
tool.handle(
    'أعطِ Del إذن groq',
    user_context={
        'service':  'groq',
        'email':    'your@email.com',
        'password': 'your_password'
    }
)
# ✓ تم حفظ إذن Groq Cloud بنجاح!
# Del لن يحتاج إذنك مجدداً لـ groq.
```

**بعدها Del يعمل بالكامل بدون تدخل.**

---

## كيف يعمل النظام

```
أنت تقول: "احصل على API key من groq"
    ↓
تحقق من الـ Vault (cache)
    ↓ موجود              ↓ غير موجود
يرجع فوراً         يفتح Chromium (مرئي)
                         ↓
                   يدخل البيانات آلياً
                         ↓
                   كشف OTP؟
                    ↓ نعم          ↓ لا
                يسألك الرمز   يكمل آلياً
                مرة واحدة
                         ↓
                   يستخرج المفتاح
                         ↓
                   يحفظ في vault.enc
                         ↓
                   يحدّث .env و config.json
                         ↓
                   يرجع المفتاح لـ Del
```

---

## الأوامر اللي يفهمها Del

```python
tool = DelAuthTool()

# جلب مفتاح (من cache أو تسجيل دخول جديد)
tool.handle("احصل على API key من groq")
tool.handle("أحضر مفتاح cerebras")

# تجديد المفتاح (تجاهل الـ cache)
tool.handle("جدد مفتاح groq")

# عرض الحالة
tool.handle("حالة")
tool.handle("ما المزودون المدعومون")

# تصدير .env
tool.handle("صدّر كل المفاتيح")
```

---

## المزودون المدعومون (15)

| المزود | مجاني | rpm | الملاحظة |
|--------|-------|-----|----------|
| **groq** | ✅ | 30 | الأسرع — لا بطاقة |
| **cerebras** | ✅ | 30 | 1M token مجاناً |
| **gemini** | ✅ | 15 | يحتاج Google account |
| **deepseek** | ✅ | 60 | $5 رصيد مجاني |
| **fireworks** | ✅ | 600 | 1M token مجاناً |
| **sambanova** | ✅ | 30 | 405B مجاناً! |
| **together** | ✅ | 60 | $1 رصيد مجاني |
| **nvidia** | ✅ | 40 | 1000 credits |
| **cohere** | ✅ | 10 | trial بدون بطاقة |
| **huggingface** | ✅ | 30 | نماذج مفتوحة |
| **moonshot** | ✅ | 3 | 15M token مجاناً |
| **qwen** | ✅ | 60 | Alibaba cloud |
| **openai** | ❌ | 500 | يحتاج بطاقة |
| **mistral** | ❌ | 5 | يحتاج بطاقة |
| **github** | ✅ | — | Personal Access Token |

---

## معالجة OTP / 2FA

عند اكتشاف شاشة التحقق الثنائي:

1. المتصفح يبقى **مرئياً** أمامك
2. Del يقول: `"🔐 تحقق ثنائي مطلوب!"`
3. لديك خياران:
   - اكتب الرمز في Terminal → Del يدخله آلياً
   - أدخله مباشرة في المتصفح

**مرة واحدة فقط** — Del يحفظ الـ session.

---

## الأمان

```
vault.enc       ← AES-128-CBC + HMAC-SHA256 (Fernet)
.vault_key      ← chmod 600 (Windows: مقيد للمستخدم الحالي)
.env            ← لا تُرفعه لـ git (أضفه لـ .gitignore)
```

كل العمليات تُسجَّل بالوقت في الـ vault. المفاتيح لا تظهر في السجلات أبداً.

---

## إضافة إلى Del

```python
# في ملف وكيل Del الرئيسي
from delfin_os.auth.del_auth_tool import DelAuthTool

auth_tool = DelAuthTool()

# Del يستدعي هذا عند الحاجة لأي API key
def get_api_key(service: str) -> str:
    result_text = auth_tool.handle(f"احصل على API key من {service}")
    # يستخرج المفتاح من الـ vault مباشرة
    from delfin_os.auth.token_vault import get_credential
    return get_credential(service, "api_key")
```

---

## استكشاف الأخطاء

| المشكلة | الحل |
|---------|------|
| `playwright غير مثبت` | `pip install playwright && playwright install chromium` |
| تسجيل الدخول يفشل | شغّل مع `headless=False` وراقب المتصفح |
| المفتاح لم يُستخرج | راجع screenshot في `delfin_os/screenshots/` |
| OTP لا يعمل | أدخله يدوياً في المتصفح المفتوح |
| مسار خاطئ | تأكد أن الملفات في `Dolphin/delfin_os/auth/` |
