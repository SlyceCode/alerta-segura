"""Proyecto Django alerta-segura.

Importar la aplicacion de Celery aqui garantiza que el decorador @shared_task
encuentre el broker configurado en cuanto Django arranca.
"""

from .celery import app as celery_app

__all__ = ("celery_app",)
