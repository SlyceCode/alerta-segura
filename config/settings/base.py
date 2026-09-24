"""Configuracion comun a todos los entornos.

Regla del proyecto: aqui no se escribe ningun valor concreto de un entorno.
Todo lo que cambia entre local, Render Dev y Render Prod llega por variables
de entorno (ver .env.example).
"""

import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parents[2]

_VERDADEROS = {"1", "true", "yes", "on", "si"}


def env(nombre: str, defecto: str | None = None, *, obligatorio: bool = False) -> str | None:
    """Lee una variable de entorno tratando la cadena vacia como ausente."""
    valor = os.environ.get(nombre, "").strip() or None
    if valor is None:
        valor = defecto
    if obligatorio and not valor:
        from django.core.exceptions import ImproperlyConfigured

        raise ImproperlyConfigured(f"Falta la variable de entorno obligatoria {nombre}.")
    return valor


def env_bool(nombre: str, defecto: bool = False) -> bool:
    valor = env(nombre)
    if valor is None:
        return defecto
    return valor.lower() in _VERDADEROS


def env_int(nombre: str, defecto: int) -> int:
    valor = env(nombre)
    try:
        return int(valor) if valor is not None else defecto
    except ValueError:
        return defecto


def env_list(nombre: str, defecto: str = "") -> list[str]:
    valor = env(nombre, defecto) or ""
    return [item.strip() for item in valor.split(",") if item.strip()]


# ---------------------------------------------------------------------------
# Identidad del despliegue
# ---------------------------------------------------------------------------
# APP_COMMIT lo expone /health/ para que el smoke test confirme que Render
# esta sirviendo exactamente el commit que acaba de construir el pipeline.
APP_ENV = env("APP_ENV", "local")
APP_NOMBRE = env("APP_NOMBRE", "alerta-segura")
APP_VERSION = env("APP_VERSION", "0.1.0")
APP_COMMIT = env("APP_COMMIT") or env("RENDER_GIT_COMMIT", "desconocido")

# ---------------------------------------------------------------------------
# Seguridad basica
# ---------------------------------------------------------------------------
SECRET_KEY = env("DJANGO_SECRET_KEY", "clave-insegura-solo-para-local")
DEBUG = env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

# Render termina TLS en su proxy: sin esta cabecera Django cree que todo es HTTP.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
DATA_UPLOAD_MAX_MEMORY_SIZE = env_int("DJANGO_MAX_UPLOAD_BYTES", 5 * 1024 * 1024)

# Ruta del admin configurable: en produccion no se publica en /admin/.
ADMIN_PATH = (env("DJANGO_ADMIN_PATH", "admin/") or "").lstrip("/")
if ADMIN_PATH and not ADMIN_PATH.endswith("/"):
    ADMIN_PATH += "/"

# ---------------------------------------------------------------------------
# Aplicaciones
# ---------------------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

APPS_PROPIAS = [
    "core",  # salud del sistema y utilidades de seguridad
    "analisis",  # RF-01 a RF-05
    "inteligencia",  # proveedores de Threat Intelligence (RNF-03)
    "motor",  # motor de riesgo y explicacion
    "catalogo",  # marcas y dominios oficiales (RF-10)
    "curacion",  # consola, reportes y campanas (RF-06, RF-08, RF-09)
]

INSTALLED_APPS = DJANGO_APPS + APPS_PROPIAS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ---------------------------------------------------------------------------
# Base de datos
# ---------------------------------------------------------------------------
DATABASES = {
    "default": dj_database_url.parse(
        env("DATABASE_URL", f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
        conn_max_age=env_int("DB_CONN_MAX_AGE", 600),
        conn_health_checks=True,
    )
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# Cache y Celery (Redis)
# ---------------------------------------------------------------------------
REDIS_URL = env("REDIS_URL")

if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "alerta-segura",
        }
    }

CELERY_BROKER_URL = env("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", REDIS_URL)
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_EAGER", False)
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = env("TZ", "America/Lima")
CELERY_TASK_TIME_LIMIT = env_int("CELERY_TASK_TIME_LIMIT", 120)
CELERY_TASK_SOFT_TIME_LIMIT = env_int("CELERY_TASK_SOFT_TIME_LIMIT", 90)
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# ---------------------------------------------------------------------------
# Correo
# ---------------------------------------------------------------------------
# Django 6.1 sustituye EMAIL_BACKEND por MAILERS. Todavia no se envia correo
# real: cuando toque, basta apuntar el backend a SMTP por variable de entorno.
MAILERS = {
    "default": {
        "BACKEND": env("DJANGO_EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"),
    }
}

# ---------------------------------------------------------------------------
# Internacionalizacion
# ---------------------------------------------------------------------------
LANGUAGE_CODE = env("DJANGO_LANGUAGE_CODE", "es-pe")
TIME_ZONE = env("TZ", "America/Lima")
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Archivos estaticos
# ---------------------------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# ---------------------------------------------------------------------------
# Politica de salida a internet (RNF-04)
# ---------------------------------------------------------------------------
# El analisis visita URLs que reporta cualquiera. Sin estas reglas el servicio
# se convierte en un proxy hacia la red interna del proveedor (SSRF).
DESTINOS_ESQUEMAS_PERMITIDOS = env_list("DESTINOS_ESQUEMAS", "http,https")
DESTINOS_PUERTOS_PERMITIDOS = [
    int(puerto) for puerto in env_list("DESTINOS_PUERTOS", "80,443") if puerto.isdigit()
]
DESTINOS_PERMITIR_PRIVADOS = env_bool("DESTINOS_PERMITIR_PRIVADOS", False)
DESTINOS_TIMEOUT = env_int("DESTINOS_TIMEOUT", 10)
DESTINOS_MAX_REDIRECCIONES = env_int("DESTINOS_MAX_REDIRECCIONES", 3)
DESTINOS_MAX_BYTES = env_int("DESTINOS_MAX_BYTES", 2 * 1024 * 1024)

# ---------------------------------------------------------------------------
# Logs: siempre a stdout, que es lo que recoge Render.
# ---------------------------------------------------------------------------
LOG_LEVEL = (env("LOG_LEVEL", "INFO") or "INFO").upper()

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "plano": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
    },
    "handlers": {
        "consola": {"class": "logging.StreamHandler", "formatter": "plano"},
    },
    "root": {"handlers": ["consola"], "level": LOG_LEVEL},
    "loggers": {
        "django.request": {"handlers": ["consola"], "level": "WARNING", "propagate": False},
        "alerta": {"handlers": ["consola"], "level": LOG_LEVEL, "propagate": False},
    },
}
