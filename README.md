# 🛡️ CYBERGUARD OS

نظام سيبراني ذاتي — جمع، تنظيف، توليد، صهر، تنفيذ

## الميزات

- **النواة الذاتية**: بدون Gemini، لا رفض، لا تغيير مسار
- **الذاكرة المتطايرة**: تدريب ورفع تلقائي عند الحد
- **مليون وكيل**: تسلسل هرمي + سحابات متعددة
- **الصهر البرمجي**: Qwen Coder + DeepSeek + CodeLlama + Kimi K3
- **مزودو API**: 18+ مزود LLM و Code و Embeddings
- **Datasets**: 15+ منصة بيانات جاهزة
- **واجهة مرنة**: أوامر معقدة، اختصارات، سياق محادثة

## البنية

```
cyberguard-os/
├── core/                 # النواة الذاتية
│   ├── brain.py          # العقل
│   ├── memory.py         # الذاكرة المتطايرة
│   ├── learner.py        # التعلم الآلي
│   └── executor.py       # المنفذ (لا رفض)
├── merge/                # الصهر
│   ├── omni_merger.py    # الصهر الشامل
│   ├── lora_delta.py     # LoRA deltas
│   └── conditional_merge.py
├── agents/               # الوكلاء
│   ├── hierarchy.py      # مليون وكيل
│   └── parasite.py       # الوكلاء المتطفلون
├── collect/              # الجمع
│   ├── multi_platform.py # جمع الأكواد
│   ├── datasets.py       # جمع datasets
│   ├── cleaner.py        # التنظيف
│   └── regenerator.py    # إعادة التوليد
├── providers/            # مزودو API
│   ├── llm_providers.py  # LLM APIs
│   ├── code_providers.py # Code APIs
│   └── embedding_providers.py
├── plugins/              # الإضافات
│   ├── hooks.py          # نظام الخطافات
│   └── loader.py         # محمل الإضافات
└── chat/                 # الشات
    ├── interface.py      # الواجهة الرئيسية
    ├── advanced_parser.py # المحلل المتقدم
    ├── context.py        # سياق المحادثة
    └── commands.py       # سجل الأوامر
```

## النشر على Google Cloud

### 1. إنشاء مشروع

```bash
gcloud projects create cyberguard-os
gcloud config set project cyberguard-os
```

### 2. تفعيل الخدمات

```bash
gcloud services enable appengine.googleapis.com
gcloud services enable cloudbuild.googleapis.com
```

### 3. إعداد GitHub Actions

في GitHub → Settings → Secrets → Actions، أضف:
- `GCP_SA_KEY`: مفتاح حساب الخدمة (Service Account Key)

### 4. النشر التلقائي

كل push إلى `main` ينشر تلقائياً على Google Cloud.

## التشغيل المحلي

```bash
pip install -r requirements.txt
streamlit run main.py
```

## متغيرات البيئة

| المتغير | الوصف |
|---------|-------|
| `GOOGLE_API_KEY` | مفتاح Gemini (اختياري) |
| `GROQ_API_KEY` | مفتاح Groq |
| `HF_TOKEN` | مفتاح HuggingFace |
| `CG_MEMORY_MAX_GB` | حد الذاكرة (افتراضي: 10) |
| `CG_MAX_AGENTS` | عدد الوكلاء (افتراضي: 1000000) |

## الرخصة

Apache-2.0 — استخدم بمسؤولية.
