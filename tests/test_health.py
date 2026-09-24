"""Pruebas de los endpoints de salud.

Ojo: las pruebas de /health/ no llevan el marcador django_db a proposito.
pytest-django bloquea el acceso a la base de datos sin ese marcador, asi que
si /health/ tocara la base de datos, estas pruebas fallarian. Esa es
justamente la garantia que queremos: liveness sin dependencias.
"""

import pytest
from django.db import OperationalError

from core import views


def test_health_responde_ok_sin_base_de_datos(client):
    respuesta = client.get("/health/")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["estado"] == "ok"
    assert cuerpo["servicio"] == "alerta-segura"
    assert cuerpo["entorno"] == "test"


def test_health_expone_el_commit_desplegado(client):
    """scripts/smoke.sh compara este valor con el commit del pipeline."""
    cuerpo = client.get("/health/").json()

    assert cuerpo["commit"] == "commit-de-prueba"
    assert cuerpo["version"]


def test_health_no_se_cachea(client):
    respuesta = client.get("/health/")

    assert "no-store" in respuesta.headers["Cache-Control"]


def test_health_solo_acepta_get(client):
    assert client.post("/health/").status_code == 405


@pytest.mark.django_db
def test_ready_ok_cuando_las_dependencias_responden(client):
    respuesta = client.get("/ready/")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["estado"] == "listo"
    assert cuerpo["dependencias"]["base_datos"]["estado"] == "ok"
    assert cuerpo["dependencias"]["cache"]["estado"] == "ok"


@pytest.mark.django_db
def test_ready_devuelve_503_si_la_base_de_datos_falla(client, monkeypatch):
    def explotar():
        raise OperationalError("conexion rechazada en 10.0.0.5:5432")

    monkeypatch.setattr(views, "_chequeo_bd", explotar)

    respuesta = client.get("/ready/")

    assert respuesta.status_code == 503
    cuerpo = respuesta.json()
    assert cuerpo["estado"] == "degradado"
    assert cuerpo["dependencias"]["base_datos"]["estado"] == "error"
    # El detalle interno no sale a la red: solo el tipo de excepcion.
    assert cuerpo["dependencias"]["base_datos"]["detalle"] == "OperationalError"
    assert "10.0.0.5" not in respuesta.content.decode()


@pytest.mark.django_db
def test_ready_devuelve_503_si_la_cache_falla(client, monkeypatch):
    def explotar():
        raise RuntimeError("redis caido")

    monkeypatch.setattr(views, "_chequeo_cache", explotar)

    respuesta = client.get("/ready/")

    assert respuesta.status_code == 503
    assert respuesta.json()["dependencias"]["cache"]["estado"] == "error"
    assert respuesta.json()["dependencias"]["base_datos"]["estado"] == "ok"
