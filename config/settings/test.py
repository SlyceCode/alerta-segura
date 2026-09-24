"""Entorno de pruebas (pytest).

Por defecto usa SQLite en memoria para que `pytest` funcione sin levantar
nada. Si DATABASE_URL apunta a Postgres (como en el pipeline), se respeta.
"""

import os

import dj_database_url

from .base import *  # noqa: F403

DEBUG = False

ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]

_url_bd = os.environ.get("DATABASE_URL", "").strip()
DATABASES = {
    "default": dj_database_url.parse(_url_bd)
    if _url_bd
    else {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Las tareas se ejecutan en linea: ningun test depende de un worker.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "pruebas",
    }
}

# Sin collectstatic no hay nada que servir: WhiteNoise solo estorba aqui.
MIDDLEWARE = [m for m in MIDDLEWARE if "whitenoise" not in m]  # noqa: F405

# Hashing rapido: las pruebas crean usuarios, no miden criptografia.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

# Valores fijos para que las aserciones sobre /health/ sean deterministas.
APP_ENV = "test"
APP_COMMIT = os.environ.get("APP_COMMIT", "commit-de-prueba")
