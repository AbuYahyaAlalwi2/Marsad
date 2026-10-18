FROM python:3.12-slim-bookworm
ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends git curl ca-certificates gnupg build-essential pkg-config \
      libffi-dev libssl-dev libxml2-dev libxslt1-dev libpq-dev libyaml-dev libjpeg-dev zlib1g-dev libsqlite3-dev \
 && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg -o /usr/share/keyrings/githubcli-archive-keyring.gpg \
 && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" > /etc/apt/sources.list.d/github-cli.list \
 && apt-get update && apt-get install -y --no-install-recommends gh \
 && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv huggingface_hub
RUN useradd -m -u 1000 marsad && mkdir -p /work /app && chown -R marsad /work /app
WORKDIR /app
COPY --chown=marsad . /app
USER marsad
ENV WORK_DIR=/work PORT=8080
CMD ["python", "marsad_factory_daemon_v2.py"]
