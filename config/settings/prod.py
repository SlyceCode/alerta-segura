"""Entorno desplegado: Render Dev y Render Prod.

Los dos servicios usan este modulo; lo que los distingue son sus variables de
entorno (APP_ENV, DATABASE_URL, REDIS_URL, dominios). Aqui solo se exige que
nada quede con un valor por defecto inseguro.
"""

import dj_database_url

from .base import *  # noqa: F403
from .base import env, env_bool, env_int, env_list

DEBUG = False

# Sin estas tres variables el servicio no arranca: preferimos fallar en el
# despliegue antes que servir con una clave de ejemplo.
SECRET_KEY = env("DJANGO_SECRET_KEY", obligatorio=True)
DATABASES = {
    "default": dj_database_url.parse(
        env("DATABASE_URL", obligatorio=True),
        conn_max_age=env_int("DB_CONN_MAX_AGE", 600),
        conn_health_checks=True,
        ssl_require=env_bool("DB_SSL_REQUIRED", False),
    )
}

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")
_host_render = env("RENDER_EXTERNAL_HOSTNAME")
if _host_render and _host_render not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(_host_render)
if not ALLOWED_HOSTS:
    from django.core.exceptions import ImproperlyConfigured

    raise ImproperlyConfigured(
        "DJANGO_ALLOWED_HOSTS es obligatorio en produccion (o RENDER_EXTERNAL_HOSTNAME)."
    )

CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS") or [
    f"https://{host}" for host in ALLOWED_HOSTS if not host.startswith(".")
]

# ---------------------------------------------------------------------------
# Correo
# ---------------------------------------------------------------------------
# El backend de consola que se usa en local no vale desplegado (mail.E001):
# aqui se envia por SMTP con las credenciales que ponga el entorno.
MAILERS = {
    "default": {
        "BACKEND": "django.core.mail.backends.smtp.EmailBackend",
        "OPTIONS": {
            "host": env("EMAIL_HOST", "localhost"),
            "port": env_int("EMAIL_PORT", 587),
            "username": env("EMAIL_HOST_USER", ""),
            "password": env("EMAIL_HOST_PASSWORD", ""),
            "use_tls": env_bool("EMAIL_USE_TLS", True),
            "timeout": env_int("EMAIL_TIMEOUT", 10),
        },
    }
}

# ---------------------------------------------------------------------------
# Transporte y cookies
# ---------------------------------------------------------------------------
SECURE_SSL_REDIRECT = env_bool("DJANGO_SSL_REDIRECT", True)
SECURE_HSTS_SECONDS = env_int("DJANGO_HSTS_SECONDS", 31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_HSTS_SUBDOMINIOS", True)
SECURE_HSTS_PRELOAD = env_bool("DJANGO_HSTS_PRELOAD", False)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# /health/ y /ready/ los consulta Render por HTTP interno: si se redirigen a
# HTTPS, el health check falla y el despliegue nunca pasa a "live".
SECURE_REDIRECT_EXEMPT = [r"^health/$", r"^ready/$"]
