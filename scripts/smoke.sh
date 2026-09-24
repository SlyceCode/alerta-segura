#!/usr/bin/env bash
# Smoke test posterior al despliegue.
#
# Comprueba tres cosas, en este orden:
#   1. /health/ responde 200 (el servicio arranco).
#   2. el commit que reporta /health/ es el que acaba de desplegar el pipeline.
#      Sin esta comprobacion un despliegue fallido pasa inadvertido: la version
#      anterior sigue viva y respondiendo 200.
#   3. /ready/ responde 200 (base de datos y cache accesibles).
#
# Uso: scripts/smoke.sh <url-base> [commit-esperado]
#      INTENTOS=30 ESPERA=10 scripts/smoke.sh https://alerta-dev.onrender.com abc1234
set -euo pipefail

URL_BASE="${1:-${URL_BASE:-}}"
COMMIT_ESPERADO="${2:-${GITHUB_SHA:-}}"
INTENTOS="${INTENTOS:-30}"
ESPERA="${ESPERA:-10}"
TIMEOUT="${TIMEOUT:-15}"

if [ -z "$URL_BASE" ]; then
  echo "uso: $0 <url-base> [commit-esperado]" >&2
  exit 64
fi

URL_BASE="${URL_BASE%/}"

PYTHON="$(command -v python3 || command -v python || true)"
if [ -z "$PYTHON" ]; then
  echo "[smoke] se necesita python3 para leer la respuesta JSON" >&2
  exit 69
fi

log() { printf '[smoke] %s\n' "$*"; }

# Lee una clave de un JSON por stdin sin depender de jq.
campo() {
  "$PYTHON" -c 'import json,sys
try:
    print(json.load(sys.stdin).get(sys.argv[1], ""))
except Exception:
    print("")' "$1"
}

cuerpo="$(mktemp)"
cabeceras="$(mktemp)"
trap 'rm -f "$cuerpo" "$cabeceras"' EXIT

# --------------------------------------------------------------------------
# 1. Esperar a que /health/ conteste
# --------------------------------------------------------------------------
log "esperando a ${URL_BASE}/health/ (hasta $((INTENTOS * ESPERA))s)"

codigo=""
for intento in $(seq 1 "$INTENTOS"); do
  codigo="$(curl -sS -o "$cuerpo" -D "$cabeceras" -w '%{http_code}' \
    --max-time "$TIMEOUT" "${URL_BASE}/health/" 2>/dev/null || echo 000)"

  if [ "$codigo" = "200" ]; then
    log "health respondio 200 en el intento ${intento}"
    break
  fi

  log "intento ${intento}/${INTENTOS}: health devolvio ${codigo}, reintentando en ${ESPERA}s"
  sleep "$ESPERA"
done

if [ "$codigo" != "200" ]; then
  log "FALLO: /health/ nunca respondio 200 (ultimo codigo: ${codigo})"
  cat "$cuerpo" >&2 || true
  exit 1
fi

estado="$(campo estado < "$cuerpo")"
commit_desplegado="$(campo commit < "$cuerpo")"
entorno="$(campo entorno < "$cuerpo")"
version="$(campo version < "$cuerpo")"

if [ "$estado" != "ok" ]; then
  log "FALLO: /health/ reporta estado '${estado}'"
  exit 1
fi

log "servicio vivo: entorno=${entorno} version=${version} commit=${commit_desplegado}"

# --------------------------------------------------------------------------
# 2. Validar el commit desplegado
# --------------------------------------------------------------------------
if [ -z "$COMMIT_ESPERADO" ]; then
  log "AVISO: sin commit esperado, se omite la comprobacion de version"
else
  esperado_corto="$(printf '%s' "$COMMIT_ESPERADO" | cut -c1-7)"
  desplegado_corto="$(printf '%s' "$commit_desplegado" | cut -c1-7)"

  if [ "$esperado_corto" != "$desplegado_corto" ]; then
    log "FALLO: el servicio sirve el commit ${desplegado_corto} y se esperaba ${esperado_corto}"
    log "       (el despliegue no llego a reemplazar la version anterior)"
    exit 1
  fi

  log "commit correcto: ${desplegado_corto}"
fi

# --------------------------------------------------------------------------
# 3. Comprobar dependencias y cabeceras
# --------------------------------------------------------------------------
codigo_ready="$(curl -sS -o "$cuerpo" -w '%{http_code}' \
  --max-time "$TIMEOUT" "${URL_BASE}/ready/" 2>/dev/null || echo 000)"

if [ "$codigo_ready" != "200" ]; then
  log "FALLO: /ready/ devolvio ${codigo_ready}"
  cat "$cuerpo" >&2 || true
  exit 1
fi

log "dependencias listas: $(campo estado < "$cuerpo")"

if ! grep -qi '^x-content-type-options: *nosniff' "$cabeceras"; then
  log "FALLO: falta la cabecera X-Content-Type-Options: nosniff"
  exit 1
fi

log "smoke test superado"
