"""Entorno local: docker-compose o runserver."""

from .base import *  # noqa: F403
from .base import env_bool, env_list

DEBUG = env_bool("DJANGO_DEBUG", True)

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,0.0.0.0,web")
CSRF_TRUSTED_ORIGINS = env_list(
    "DJANGO_CSRF_TRUSTED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000"
)

# En local no se ejecuta collectstatic, asi que el manifiesto de WhiteNoise
# sobra y solo estorba.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

# Sin Redis levantado, las tareas se ejecutan en el mismo proceso.
if not CELERY_BROKER_URL:  # noqa: F405
    CELERY_TASK_ALWAYS_EAGER = True
