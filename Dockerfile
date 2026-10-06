FROM python:3.12-slim

WORKDIR /app

# تثبيت المكتبات الأساسية فقط (بدون بناء محلي)
RUN pip install --no-cache-dir \
    fastapi uvicorn requests huggingface_hub==0.26.5 \
    --only-binary=:all: || \
    pip install --no-cache-dir fastapi uvicorn requests huggingface_hub==0.26.5

# نسخ الكود والبوابات
COPY . .

# تشغيل المنسق المركزي (المنقّب يُشغل لاحقاً عبر Cron أو API)
CMD ["python3", "adversarial_orchestrator.py"]
