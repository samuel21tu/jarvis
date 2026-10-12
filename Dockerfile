# Imagem do Jarvis Hub (servidor central + interface HUD)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OBSIDIAN_VAULT_PATH=/data/obsidian_vault

WORKDIR /app

COPY requirements.txt .
RUN pip install --default-timeout=100 --retries=5 --no-cache-dir -r requirements.txt

# Apenas o código do Hub e o frontend (o nó roda no PC do usuário)
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/sh -m appuser && \
    mkdir -p /data/obsidian_vault /data/memory && \
    chown -R appuser:appgroup /data

COPY --chown=appuser:appgroup src/__init__.py* src/
COPY --chown=appuser:appgroup src/hub ./src/hub
COPY --chown=appuser:appgroup src/mobile ./src/mobile

USER appuser

EXPOSE 8080

# Healthcheck simples na página do HUD
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/')" || exit 1

CMD ["uvicorn", "src.hub.jarvis_hub:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers"]
