"""
Provider Registry — سجل كل مزودي AI
يحمل: selectors, key_pattern, env_var, rpm, rpd, base_url, models, free_tier
"""

from dataclasses import dataclass, field
from typing import Optional


# ─── Provider Metadata ────────────────────────────────────────────────────────

@dataclass
class ProviderMeta:
    id:           str
    name:         str
    login_url:    str
    api_key_url:  str
    success_url:  str            # جزء من URL يدل على نجاح تسجيل الدخول
    env_var:      str            # اسم متغير البيئة في .env
    key_pattern:  str            # regex لاستخراج المفتاح من الصفحة
    email_sel:    str            # CSS selectors (مفصولة بـ ", ")
    pass_sel:     str
    submit_sel:   str
    create_btn:   str            # زر إنشاء مفتاح جديد
    # بيانات تشغيلية
    base_url:     str            = ""
    models:       list[str]     = field(default_factory=list)
    rpm:          int            = 0    # requests per minute (free tier)
    rpd:          int            = 0    # requests per day
    free_tokens:  int            = 0    # tokens مجانية شهرياً
    free_tier:    bool           = True
    otp_required: bool           = False   # يحتاج OTP/2FA
    notes:        str            = ""


# ─── Registry ─────────────────────────────────────────────────────────────────

PROVIDERS: dict[str, ProviderMeta] = {

    # ── Groq ──────────────────────────────────────────────────────────────────
    "groq": ProviderMeta(
        id          = "groq",
        name        = "Groq Cloud",
        login_url   = "https://console.groq.com",
        api_key_url = "https://console.groq.com/keys",
        success_url = "console.groq.com",
        env_var     = "GROQ_API_KEY",
        key_pattern = r"gsk_[A-Za-z0-9]{48,}",
        email_sel   = "input[type='email'], input[name='email'], #email",
        pass_sel    = "input[type='password']",
        submit_sel  = "button[type='submit'], button:has-text('Sign in'), button:has-text('Continue')",
        create_btn  = "button:has-text('Create API key'), button:has-text('Create Key'), .create-key-btn",
        base_url    = "https://api.groq.com/openai/v1",
        models      = ["llama3-70b-8192", "llama3-8b-8192", "mixtral-8x7b-32768", "gemma2-9b-it"],
        rpm         = 30,
        rpd         = 14400,
        free_tokens = 500_000,
        notes       = "لا يحتاج بطاقة ائتمان — مجاني تماماً",
    ),

    # ── Cerebras ──────────────────────────────────────────────────────────────
    "cerebras": ProviderMeta(
        id          = "cerebras",
        name        = "Cerebras Inference",
        login_url   = "https://cloud.cerebras.ai",
        api_key_url = "https://cloud.cerebras.ai/platform/api-keys",
        success_url = "cloud.cerebras.ai/platform",
        env_var     = "CEREBRAS_API_KEY",
        key_pattern = r"csk-[A-Za-z0-9]{48,}",
        email_sel   = "input[type='email'], input[name='email']",
        pass_sel    = "input[type='password']",
        submit_sel  = "button[type='submit'], button:has-text('Sign in')",
        create_btn  = "button:has-text('Create'), button:has-text('New API Key'), button:has-text('Generate')",
        base_url    = "https://api.cerebras.ai/v1",
        models      = ["llama3.1-70b", "llama3.1-8b"],
        rpm         = 30,
        rpd         = 0,
        free_tokens = 1_000_000,
        notes       = "أسرع inference — Wafer Scale Engine",
    ),

    # ── Google Gemini ──────────────────────────────────────────────────────────
    "gemini": ProviderMeta(
        id          = "gemini",
        name        = "Google Gemini",
        login_url   = "https://aistudio.google.com",
        api_key_url = "https://aistudio.google.com/app/apikey",
        success_url = "aistudio.google.com",
        env_var     = "GEMINI_API_KEY",
        key_pattern = r"AIza[A-Za-z0-9_\-]{35,}",
        email_sel   = "input[type='email'], input[name='identifier']",
        pass_sel    = "input[type='password'], input[name='Passwd']",
        submit_sel  = "button:has-text('Next'), div[id='identifierNext'], div[id='passwordNext']",
        create_btn  = "button:has-text('Create API key'), button:has-text('Get API key')",
        base_url    = "https://generativelanguage.googleapis.com/v1beta",
        models      = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash-exp"],
        rpm         = 15,
        rpd         = 1500,
        free_tokens = 1_000_000,
        otp_required= True,
        notes       = "يحتاج Google account — OTP عبر الجوال",
    ),

    # ── DeepSeek ──────────────────────────────────────────────────────────────
    "deepseek": ProviderMeta(
        id          = "deepseek",
        name        = "DeepSeek Platform",
        login_url   = "https://platform.deepseek.com",
        api_key_url = "https://platform.deepseek.com/api_keys",
        success_url = "platform.deepseek.com",
        env_var     = "DEEPSEEK_API_KEY",
        key_pattern = r"sk-[A-Za-z0-9]{48,}",
        email_sel   = "input[type='email'], input[placeholder*='email'], input[placeholder*='Email']",
        pass_sel    = "input[type='password']",
        submit_sel  = "button[type='submit'], button:has-text('Login'), button:has-text('Sign in')",
        create_btn  = "button:has-text('Create'), button:has-text('New key'), button:has-text('+ Create')",
        base_url    = "https://api.deepseek.com/v1",
        models      = ["deepseek-chat", "deepseek-reasoner"],
        rpm         = 60,
        rpd         = 0,
        free_tokens = 10_000_000,
        notes       = "يعطي $5 رصيد مجاني عند التسجيل",
    ),

    # ── Together AI ───────────────────────────────────────────────────────────
    "together": ProviderMeta(
        id          = "together",
        name        = "Together AI",
        login_url   = "https://api.together.xyz",
        api_key_url = "https://api.together.xyz/settings/api-keys",
        success_url = "api.together.xyz",
        env_var     = "TOGETHER_API_KEY",
        key_pattern = r"[A-Za-z0-9]{64,}",
        email_sel   = "input[type='email'], input[name='email']",
        pass_sel    = "input[type='password']",
        submit_sel  = "button[type='submit'], button:has-text('Sign in'), button:has-text('Log in')",
        create_btn  = "button:has-text('Create'), button:has-text('New API Key')",
        base_url    = "https://api.together.xyz/v1",
        models      = ["meta-llama/Llama-3-70b-chat-hf", "mistralai/Mixtral-8x22B-Instruct-v0.1"],
        rpm         = 60,
        rpd         = 0,
        free_tokens = 0,
        notes       = "يعطي $1 رصيد مجاني",
    ),

    # ── Fireworks ─────────────────────────────────────────────────────────────
    "fireworks": ProviderMeta(
        id          = "fireworks",
        name        = "Fireworks AI",
        login_url   = "https://fireworks.ai",
        api_key_url = "https://fireworks.ai/account/api-keys",
        success_url = "fireworks.ai/account",
        env_var     = "FIREWORKS_API_KEY",
        key_pattern = r"fw_[A-Za-z0-9]{48,}",
        email_sel   = "input[type='email'], input[name='email']",
        pass_sel    = "input[type='password']",
        submit_sel  = "button[type='submit'], button:has-text('Sign in')",
        create_btn  = "button:has-text('Create'), button:has-text('Generate'), button:has-text('New Key')",
        base_url    = "https://api.fireworks.ai/inference/v1",
        models      = ["accounts/fireworks/models/llama-v3p1-70b-instruct"],
        rpm         = 600,
        rpd         = 0,
        free_tokens = 1_000_000,
        notes       = "مليون token مجاني للمستخدمين الجدد",
    ),

    # ── SambaNova ─────────────────────────────────────────────────────────────
    "sambanova": ProviderMeta(
        id          = "sambanova",
        name        = "SambaNova Cloud",
        login_url   = "https://cloud.sambanova.ai",
        api_key_url = "https://cloud.sambanova.ai/apis",
        success_url = "cloud.sambanova.ai",
        env_var     = "SAMBANOVA_API_KEY",
        key_pattern = r"[A-Za-z0-9\-]{36,}",
        email_sel   = "input[type='email'], input[name='email']",
        pass_sel    = "input[type='password']",
        submit_sel  = "button[type='submit'], button:has-text('Sign in')",
        create_btn  = "button:has-text('Get API Key'), button:has-text('Create'), button:has-text('Generate')",
        base_url    = "https://api.sambanova.ai/v1",
        models      = ["Meta-Llama-3.1-405B-Instruct", "Meta-Llama-3.1-70B-Instruct"],
        rpm         = 30,
        rpd         = 1000,
        free_tokens = 0,
        notes       = "405B مجاني — الأكبر مجاناً",
    ),

    # ── Mistral ───────────────────────────────────────────────────────────────
    "mistral": ProviderMeta(
        id          = "mistral",
        name        = "Mistral AI",
        login_url   = "https://console.mistral.ai",
        api_key_url = "https://console.mistral.ai/api-keys/",
        success_url = "console.mistral.ai",
        env_var     = "MISTRAL_API_KEY",
        key_pattern = r"[A-Za-z0-9]{32,}",
        email_sel   = "input[type='email'], input[name='email']",
        pass_sel    = "input[type='password']",
        submit_sel  = "button[type='submit'], button:has-text('Sign in'), button:has-text('Continue')",
        create_btn  = "button:has-text('Create new key'), button:has-text('+ New key')",
        base_url    = "https://api.mistral.ai/v1",
        models      = ["mistral-large-latest", "mistral-small-latest", "open-mistral-7b"],
        rpm         = 5,
        rpd         = 0,
        free_tokens = 0,
        notes       = "يحتاج بطاقة ائتمان للـ free tier",
    ),

    # ── NVIDIA NIM ────────────────────────────────────────────────────────────
    "nvidia": ProviderMeta(
        id          = "nvidia",
        name        = "NVIDIA NIM",
        login_url   = "https://build.nvidia.com",
        api_key_url = "https://build.nvidia.com/settings/api-keys",
        success_url = "build.nvidia.com",
        env_var     = "NVIDIA_API_KEY",
        key_pattern = r"nvapi-[A-Za-z0-9_\-]{60,}",
        email_sel   = "input[type='email'], input[name='email']",
        pass_sel    = "input[type='password']",
        submit_sel  = "button[type='submit'], button:has-text('Sign In'), button:has-text('Login')",
        create_btn  = "button:has-text('Generate Key'), button:has-text('Create Key')",
        base_url    = "https://integrate.api.nvidia.com/v1",
        models      = ["meta/llama-3.1-70b-instruct", "nvidia/llama-3.1-nemotron-70b-instruct"],
        rpm         = 40,
        rpd         = 0,
        free_tokens = 1_000,  # credits
        notes       = "1000 credits مجاناً",
    ),

    # ── Cohere ────────────────────────────────────────────────────────────────
    "cohere": ProviderMeta(
        id          = "cohere",
        name        = "Cohere",
        login_url   = "https://dashboard.cohere.com",
        api_key_url = "https://dashboard.cohere.com/api-keys",
        success_url = "dashboard.cohere.com",
        env_var     = "COHERE_API_KEY",
        key_pattern = r"[A-Za-z0-9]{40,}",
        email_sel   = "input[type='email'], input[name='email']",
        pass_sel    = "input[type='password']",
        submit_sel  = "button[type='submit'], button:has-text('Log in'), button:has-text('Sign in')",
        create_btn  = "button:has-text('Add key'), button:has-text('New key'), button:has-text('Create')",
        base_url    = "https://api.cohere.ai/v1",
        models      = ["command-r-plus", "command-r", "command-light"],
        rpm         = 10,
        rpd         = 1000,
        free_tokens = 0,
        notes       = "trial key مجاني بدون بطاقة",
    ),

    # ── OpenAI ────────────────────────────────────────────────────────────────
    "openai": ProviderMeta(
        id          = "openai",
        name        = "OpenAI",
        login_url   = "https://platform.openai.com/login",
        api_key_url = "https://platform.openai.com/api-keys",
        success_url = "platform.openai.com",
        env_var     = "OPENAI_API_KEY",
        key_pattern = r"sk-[A-Za-z0-9]{48,}",
        email_sel   = "input[name='username'], input[type='email']",
        pass_sel    = "input[type='password']",
        submit_sel  = "button[type='submit'], button:has-text('Continue')",
        create_btn  = "button:has-text('Create new secret key'), button:has-text('+ Create')",
        base_url    = "https://api.openai.com/v1",
        models      = ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"],
        rpm         = 500,
        rpd         = 0,
        free_tokens = 0,
        notes       = "يحتاج بطاقة ائتمان",
    ),

    # ── GitHub ────────────────────────────────────────────────────────────────
    "github": ProviderMeta(
        id          = "github",
        name        = "GitHub",
        login_url   = "https://github.com/login",
        api_key_url = "https://github.com/settings/tokens/new",
        success_url = "github.com",
        env_var     = "GITHUB_TOKEN",
        key_pattern = r"ghp_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{82,}",
        email_sel   = "#login_field",
        pass_sel    = "#password",
        submit_sel  = "input[type='submit'], [value='Sign in']",
        create_btn  = "button:has-text('Generate token')",
        base_url    = "https://api.github.com",
        models      = [],
        rpm         = 0,
        rpd         = 0,
        free_tokens = 0,
        notes       = "Personal Access Token",
    ),

    # ── HuggingFace ───────────────────────────────────────────────────────────
    "huggingface": ProviderMeta(
        id          = "huggingface",
        name        = "HuggingFace",
        login_url   = "https://huggingface.co/login",
        api_key_url = "https://huggingface.co/settings/tokens",
        success_url = "huggingface.co",
        env_var     = "HF_TOKEN",
        key_pattern = r"hf_[A-Za-z0-9]{36,}",
        email_sel   = "input[name='username'], input[type='email']",
        pass_sel    = "input[type='password']",
        submit_sel  = "button[type='submit']",
        create_btn  = "button:has-text('New token'), button:has-text('Create a token')",
        base_url    = "https://api-inference.huggingface.co",
        models      = ["meta-llama/Llama-3.1-70B-Instruct", "mistralai/Mixtral-8x7B"],
        rpm         = 30,
        rpd         = 0,
        free_tokens = 0,
        notes       = "Inference API مجاني للنماذج المفتوحة",
    ),

    # ── Moonshot (Kimi) ───────────────────────────────────────────────────────
    "moonshot": ProviderMeta(
        id          = "moonshot",
        name        = "Moonshot AI (Kimi)",
        login_url   = "https://platform.moonshot.cn",
        api_key_url = "https://platform.moonshot.cn/console/api-keys",
        success_url = "platform.moonshot.cn/console",
        env_var     = "MOONSHOT_API_KEY",
        key_pattern = r"sk-[A-Za-z0-9]{48,}",
        email_sel   = "input[type='email'], input[type='tel']",
        pass_sel    = "input[type='password']",
        submit_sel  = "button[type='submit'], button:has-text('登录'), button:has-text('Sign in')",
        create_btn  = "button:has-text('创建'), button:has-text('Create'), button:has-text('新建')",
        base_url    = "https://api.moonshot.cn/v1",
        models      = ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
        rpm         = 3,
        rpd         = 0,
        free_tokens = 15_000_000,
        notes       = "15M tokens مجاناً — واجهة صينية/إنجليزية",
    ),

    # ── Qwen (Alibaba) ────────────────────────────────────────────────────────
    "qwen": ProviderMeta(
        id          = "qwen",
        name        = "Alibaba Qwen",
        login_url   = "https://dashscope.aliyuncs.com",
        api_key_url = "https://dashscope.console.aliyun.com/apiKey",
        success_url = "aliyuncs.com",
        env_var     = "DASHSCOPE_API_KEY",
        key_pattern = r"sk-[A-Za-z0-9]{32,}",
        email_sel   = "input[type='email'], input[name='loginId']",
        pass_sel    = "input[type='password']",
        submit_sel  = "button[type='submit'], button:has-text('Login'), button:has-text('Sign in')",
        create_btn  = "button:has-text('Create'), button:has-text('新建')",
        base_url    = "https://dashscope.aliyuncs.com/compatible-mode/v1",
        models      = ["qwen-turbo", "qwen-plus", "qwen-max"],
        rpm         = 60,
        rpd         = 0,
        free_tokens = 1_000_000,
        notes       = "يحتاج Aliyun account",
    ),
}


# ─── Helper Functions ─────────────────────────────────────────────────────────

def get_provider(name: str) -> Optional[ProviderMeta]:
    return PROVIDERS.get(name.lower())

def list_providers() -> list[dict]:
    return [
        {
            "id":          p.id,
            "name":        p.name,
            "env_var":     p.env_var,
            "rpm":         p.rpm,
            "rpd":         p.rpd,
            "free_tokens": p.free_tokens,
            "free_tier":   p.free_tier,
            "models":      p.models[:2],
            "notes":       p.notes,
        }
        for p in PROVIDERS.values()
    ]

def get_free_providers() -> list[str]:
    """المزودون الذين لا يحتاجون بطاقة ائتمان"""
    return [p.id for p in PROVIDERS.values() if p.free_tier and not p.otp_required]


if __name__ == "__main__":
    print(f"إجمالي المزودين: {len(PROVIDERS)}\n")
    print("المزودون المجانيون (بدون بطاقة):")
    for pid in get_free_providers():
        p = PROVIDERS[pid]
        print(f"  {p.name:25} rpm={p.rpm:4}  {p.notes[:50]}")
