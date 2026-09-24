"""Rutas del proyecto.

De momento solo se publica lo que necesita la plataforma para operar.
Las rutas funcionales (analisis, consola de curacion, catalogo) se montan en
el proximo sprint.
"""

from django.conf import settings
from django.contrib import admin
from django.urls import path

from core import views as core_views

urlpatterns = [
    path("health/", core_views.health, name="health"),
    path("ready/", core_views.ready, name="ready"),
]

if settings.ADMIN_PATH:
    urlpatterns.append(path(settings.ADMIN_PATH, admin.site.urls))

# Proximo sprint:
# urlpatterns += [
#     path("api/analisis/", include("analisis.urls")),
#     path("api/catalogo/", include("catalogo.urls")),
#     path("curacion/", include("curacion.urls")),
# ]
