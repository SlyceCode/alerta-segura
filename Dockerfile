# Imagen unica para web, worker y beat: lo que cambia es la variable MODO.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# curl lo usan el HEALTHCHECK y scripts/smoke.sh.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Las dependencias primero: asi la cache de capas sobrevive a cambios de codigo.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# El commit se hornea en la imagen para que /health/ lo pueda reportar.
ARG APP_COMMIT=desconocido
ENV APP_COMMIT=${APP_COMMIT}

# Nada corre como root.
RUN useradd --system --create-home --shell /usr/sbin/nologin alerta \
    && chmod +x scripts/*.sh \
    && mkdir -p staticfiles \
    && chown -R alerta:alerta /app
USER alerta

ENV DJANGO_SETTINGS_MODULE=config.settings.prod \
    PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT}/health/" || exit 1

# Se invoca con bash explicito: en Windows el bit de ejecucion no viaja
# en el repositorio, y asi la imagen arranca igual.
ENTRYPOINT ["bash", "/app/scripts/entrypoint.sh"]
