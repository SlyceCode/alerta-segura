#!/usr/bin/env bash
# Arranque del contenedor (Render y docker-compose).
#
# MODO controla que proceso se levanta con la misma imagen:
#   web    -> gunicorn (por defecto)
#   worker -> worker de Celery
#   beat   -> planificador de Celery
set -euo pipefail

MODO="${MODO:-web}"
PORT="${PORT:-8000}"
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings.prod}"

log() { printf '[entrypoint] %s\n' "$*" >&2; }

case "$MODO" in
  web)
    if [ "${EJECUTAR_MIGRACIONES:-1}" = "1" ]; then
      log "aplicando migraciones"
      python manage.py migrate --noinput
    fi

    if [ "${RECOLECTAR_ESTATICOS:-1}" = "1" ]; then
      log "recolectando archivos estaticos"
      python manage.py collectstatic --noinput
    fi

    log "arrancando gunicorn en 0.0.0.0:${PORT} (commit ${APP_COMMIT:-desconocido})"
    exec gunicorn config.wsgi:application \
      --bind "0.0.0.0:${PORT}" \
      --workers "${WEB_CONCURRENCY:-2}" \
      --threads "${GUNICORN_THREADS:-4}" \
      --timeout "${GUNICORN_TIMEOUT:-30}" \
      --graceful-timeout 30 \
      --max-requests 1000 \
      --max-requests-jitter 100 \
      --forwarded-allow-ips '*' \
      --access-logfile - \
      --error-logfile -
    ;;

  worker)
    log "arrancando worker de Celery"
    exec celery -A config worker \
      --loglevel "${CELERY_LOG_LEVEL:-info}" \
      --concurrency "${CELERY_CONCURRENCY:-2}"
    ;;

  beat)
    log "arrancando beat de Celery"
    exec celery -A config beat --loglevel "${CELERY_LOG_LEVEL:-info}"
    ;;

  *)
    log "MODO desconocido: '${MODO}' (usa web, worker o beat)"
    exit 64
    ;;
esac
