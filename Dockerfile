# Dockerfile — نشر admin_server على HuggingFace Spaces (المنفذ 7860)
FROM python:3.11-slim

WORKDIR /app
RUN pip install --no-cache-dir aiohttp python-dotenv requests

# بنية مستودع ~/Marsad: core/ agents/ database/ ...
COPY . /app

RUN mkdir -p /app/database/jsonl /app/output/codes /app/output/cves \
             /app/output/fixes /app/output/filtered /app/output/advisories /app/logs

ENV MARSAD_ADMIN_HOST=0.0.0.0
ENV MARSAD_ADMIN_PORT=7860
EXPOSE 7860

CMD ["python", "core/admin_server.py"]
