"""Configuracion de Celery.

Las tareas de analisis (consultas a proveedores de Threat Intelligence,
capturas, reprocesos) se ejecutan fuera del ciclo de la peticion HTTP.
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("alerta_segura")

# Todas las claves CELERY_* de settings pasan a ser configuracion del worker.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Busca tasks.py en cada app instalada.
app.autodiscover_tasks()


@app.task(name="core.ping")
def ping() -> str:
    """Tarea trivial para comprobar que el worker responde."""
    return "pong"
