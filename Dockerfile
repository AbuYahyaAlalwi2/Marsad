# هذا Dockerfile لتطبيق مرصد نفسه (الداشبورد + المشرف)، وليس صورة
# الـ sandbox التي تُنفَّذ فيها العينات — تلك منفصلة تماماً (انظر app/sandbox.py)
# ويجب أن يكون Docker متاحاً كخدمة (docker-in-docker أو socket مرفق)
# في منصة الاستضافة حتى تعمل ميزة الـ sandbox فعلياً.

FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN apt-get update && apt-get install -y --no-install-recommends graphviz \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

ENV MARSAD_DB_PATH=/app/data/marsad.db
RUN mkdir -p /app/data

EXPOSE 8501

CMD ["streamlit", "run", "app/main.py", "--server.port=8501", "--server.address=0.0.0.0"]
