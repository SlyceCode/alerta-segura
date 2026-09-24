"""Pruebas de la politica de salida a internet (RNF-04).

Ninguna prueba usa DNS real: el resolver se inyecta. Asi el pipeline no
depende de la red y podemos simular el caso interesante, que es el nombre
publico que resuelve a una direccion interna.
"""

import pytest

from core.net import DestinoInvalido, es_direccion_publica, validar_destino

IP_PUBLICA = "93.184.216.34"


def resolver_fijo(*direcciones):
    """Resolver falso que siempre devuelve las direcciones indicadas."""

    def resolver(host, puerto):
        return list(direcciones)

    return resolver


def resolver_prohibido(host, puerto):
    raise AssertionError(f"no se debia resolver {host}: el filtro tenia que cortar antes")


def codigo_de(excinfo) -> str:
    return excinfo.value.codigo


# ---------------------------------------------------------------------------
# Casos validos
# ---------------------------------------------------------------------------
def test_url_publica_valida():
    destino = validar_destino(
        "https://www.ejemplo.pe/aviso?id=7", resolver=resolver_fijo(IP_PUBLICA)
    )

    assert destino.esquema == "https"
    assert destino.host == "www.ejemplo.pe"
    assert destino.puerto == 443
    assert destino.direcciones == (IP_PUBLICA,)
    assert destino.origen == "https://www.ejemplo.pe:443"


def test_http_usa_el_puerto_80_por_defecto():
    destino = validar_destino("http://ejemplo.pe/", resolver=resolver_fijo(IP_PUBLICA))

    assert destino.puerto == 80


def test_ip_publica_literal_no_necesita_dns():
    destino = validar_destino(f"https://{IP_PUBLICA}/", resolver=resolver_prohibido)

    assert destino.direcciones == (IP_PUBLICA,)


def test_host_se_normaliza_a_minusculas_y_sin_punto_final():
    destino = validar_destino("https://EJEMPLO.PE./", resolver=resolver_fijo(IP_PUBLICA))

    assert destino.host == "ejemplo.pe"


def test_host_unicode_se_convierte_a_idna():
    vistos = []

    def resolver(host, puerto):
        vistos.append(host)
        return [IP_PUBLICA]

    destino = validar_destino("https://münich.ejemplo.pe/", resolver=resolver)

    assert destino.host == "xn--mnich-kva.ejemplo.pe"
    assert vistos == ["xn--mnich-kva.ejemplo.pe"]


# ---------------------------------------------------------------------------
# Esquemas y puertos
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "url",
    [
        "ftp://ejemplo.pe/archivo",
        "file:///etc/passwd",
        "gopher://ejemplo.pe/",
        "javascript:alert(1)",
        "data:text/html,<script>1</script>",
        "ejemplo.pe/sin-esquema",
    ],
)
def test_rechaza_esquemas_no_permitidos(url):
    with pytest.raises(DestinoInvalido) as excinfo:
        validar_destino(url, resolver=resolver_prohibido)

    assert codigo_de(excinfo) == "esquema_no_permitido"


@pytest.mark.parametrize("url", ["http://ejemplo.pe:8080/", "https://ejemplo.pe:22/"])
def test_rechaza_puertos_no_permitidos(url):
    with pytest.raises(DestinoInvalido) as excinfo:
        validar_destino(url, resolver=resolver_prohibido)

    assert codigo_de(excinfo) == "puerto_no_permitido"


@pytest.mark.parametrize("url", ["http://ejemplo.pe:abc/", "http://ejemplo.pe:99999/"])
def test_rechaza_puertos_malformados(url):
    with pytest.raises(DestinoInvalido) as excinfo:
        validar_destino(url, resolver=resolver_prohibido)

    assert codigo_de(excinfo) == "puerto_invalido"


def test_puede_ampliarse_la_lista_de_puertos():
    destino = validar_destino(
        "https://ejemplo.pe:8443/", puertos=(8443,), resolver=resolver_fijo(IP_PUBLICA)
    )

    assert destino.puerto == 8443


# ---------------------------------------------------------------------------
# SSRF: direcciones internas
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://10.0.0.5/admin",
        "http://192.168.1.10/",
        "http://172.16.0.9/",
        "http://169.254.169.254/latest/meta-data/",  # metadatos de la instancia
        "http://0.0.0.0/",
        "https://[::1]/",
        "https://[::ffff:127.0.0.1]/",  # IPv4 disfrazada de IPv6
        "https://[fd00::1]/",
    ],
)
def test_rechaza_direcciones_internas_literales(url):
    with pytest.raises(DestinoInvalido) as excinfo:
        validar_destino(url, resolver=resolver_prohibido)

    assert codigo_de(excinfo) == "direccion_no_publica"


def test_rechaza_nombre_publico_que_resuelve_a_ip_interna():
    """El caso clasico: un dominio propio con un registro A hacia 10.x."""
    with pytest.raises(DestinoInvalido) as excinfo:
        validar_destino("https://parece-normal.pe/", resolver=resolver_fijo("10.1.2.3"))

    assert codigo_de(excinfo) == "direccion_no_publica"


def test_basta_una_direccion_interna_para_rechazar():
    """Un round-robin mixto acabaria golpeando la red interna tarde o temprano."""
    with pytest.raises(DestinoInvalido) as excinfo:
        validar_destino("https://ejemplo.pe/", resolver=resolver_fijo(IP_PUBLICA, "192.168.0.4"))

    assert codigo_de(excinfo) == "direccion_no_publica"


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/",
        "http://localhost:80/",
        "http://api.internal/",
        "http://db.local/",
        "http://servidor.localdomain/",
    ],
)
def test_rechaza_nombres_de_red_local_sin_resolver(url):
    with pytest.raises(DestinoInvalido) as excinfo:
        validar_destino(url, resolver=resolver_prohibido)

    assert codigo_de(excinfo) == "host_bloqueado"


def test_rechaza_credenciales_embebidas():
    """https://ejemplo.pe@127.0.0.1/ enganaria a un filtro que mire el texto."""
    with pytest.raises(DestinoInvalido) as excinfo:
        validar_destino("https://ejemplo.pe@127.0.0.1/", resolver=resolver_prohibido)

    assert codigo_de(excinfo) == "credenciales_en_url"


def test_rechaza_usuario_y_clave_en_la_url():
    with pytest.raises(DestinoInvalido) as excinfo:
        validar_destino("https://usuario:clave@ejemplo.pe/", resolver=resolver_prohibido)

    assert codigo_de(excinfo) == "credenciales_en_url"


def test_rechaza_host_que_no_resuelve():
    with pytest.raises(DestinoInvalido) as excinfo:
        validar_destino("https://ejemplo.pe/", resolver=resolver_fijo())

    assert codigo_de(excinfo) == "resolucion_fallida"


# ---------------------------------------------------------------------------
# Entradas malformadas
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("url", ["", "   ", None, 42, b"https://ejemplo.pe/"])
def test_rechaza_entradas_que_no_son_una_url(url):
    with pytest.raises(DestinoInvalido) as excinfo:
        validar_destino(url, resolver=resolver_prohibido)

    assert codigo_de(excinfo) == "url_invalida"


def test_rechaza_url_demasiado_larga():
    url = "https://ejemplo.pe/" + "a" * 2100

    with pytest.raises(DestinoInvalido) as excinfo:
        validar_destino(url, resolver=resolver_prohibido)

    assert codigo_de(excinfo) == "url_demasiado_larga"


def test_rechaza_url_sin_host():
    with pytest.raises(DestinoInvalido) as excinfo:
        validar_destino("https:///solo-ruta", resolver=resolver_prohibido)

    assert codigo_de(excinfo) == "host_ausente"


# ---------------------------------------------------------------------------
# Escape para desarrollo
# ---------------------------------------------------------------------------
def test_permitir_privados_habilita_localhost():
    """En local se analiza contra un servidor de pruebas en 127.0.0.1."""
    destino = validar_destino(
        "http://127.0.0.1/", permitir_privados=True, resolver=resolver_prohibido
    )

    assert destino.host == "127.0.0.1"


# ---------------------------------------------------------------------------
# es_direccion_publica
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("direccion", [IP_PUBLICA, "8.8.8.8", "2606:4700:4700::1111"])
def test_direcciones_publicas(direccion):
    assert es_direccion_publica(direccion) is True


@pytest.mark.parametrize(
    "direccion",
    [
        "127.0.0.1",
        "10.0.0.1",
        "172.20.1.1",
        "192.168.0.1",
        "169.254.169.254",
        "0.0.0.0",
        "224.0.0.1",
        "::1",
        "fe80::1",
        "::ffff:10.0.0.1",
        "no-es-una-ip",
    ],
)
def test_direcciones_no_publicas(direccion):
    assert es_direccion_publica(direccion) is False
