"""Endpoints de salud del sistema.

Hay dos, y no son lo mismo:

* /health/  liveness. Responde siempre 200 mientras el proceso este vivo y no
            toca ninguna dependencia. Incluye el commit desplegado, que es lo
            que compara scripts/smoke.sh despues de cada despliegue.
* /ready/   readiness. Comprueba base de datos y cache. Si algo falla devuelve
            503 para que el balanceador deje de enviarle trafico.
"""

import time

from django.conf import settings
from django.core.cache import cache
from django.db import connections
from django.http import HttpRequest, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

CLAVE_CACHE = "core:ready"


def _identidad() -> dict[str, str]:
    return {
        "servicio": settings.APP_NOMBRE,
        "entorno": settings.APP_ENV,
        "version": settings.APP_VERSION,
        "commit": settings.APP_COMMIT,
    }


def _chequeo_bd() -> None:
    """Lanza excepcion si la base de datos no responde."""
    with connections["default"].cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()


def _chequeo_cache() -> None:
    """Lanza excepcion si la cache no guarda y devuelve lo escrito."""
    testigo = str(time.time())
    cache.set(CLAVE_CACHE, testigo, 10)
    if cache.get(CLAVE_CACHE) != testigo:
        raise RuntimeError("la cache no devolvio el valor escrito")


@require_GET
@never_cache
def health(request: HttpRequest) -> JsonResponse:
    """Liveness: el proceso responde. Sin dependencias, sin base de datos."""
    return JsonResponse({"estado": "ok", **_identidad()})


@require_GET
@never_cache
def ready(request: HttpRequest) -> JsonResponse:
    """Readiness: el servicio puede atender trafico real."""
    chequeos = {
        "base_datos": _chequeo_bd,
        "cache": _chequeo_cache,
    }

    dependencias: dict[str, dict[str, str]] = {}
    todo_ok = True

    for nombre, chequeo in chequeos.items():
        inicio = time.monotonic()
        try:
            chequeo()
        except Exception as exc:  # noqa: BLE001 - cualquier fallo degrada el servicio
            todo_ok = False
            dependencias[nombre] = {
                "estado": "error",
                # Solo el tipo de excepcion: el detalle va al log, no a la red.
                "detalle": type(exc).__name__,
            }
        else:
            dependencias[nombre] = {"estado": "ok"}
        dependencias[nombre]["ms"] = f"{(time.monotonic() - inicio) * 1000:.1f}"

    cuerpo = {
        "estado": "listo" if todo_ok else "degradado",
        **_identidad(),
        "dependencias": dependencias,
    }
    return JsonResponse(cuerpo, status=200 if todo_ok else 503)
