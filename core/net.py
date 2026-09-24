"""Validacion de destinos de red (RNF-04).

El analisis visita URLs que reporta cualquier usuario. Si se permite salir a
cualquier direccion, el servicio se convierte en un proxy hacia la red interna
del proveedor: metadatos de la instancia (169.254.169.254), la base de datos,
el panel del worker. Eso es un SSRF.

Este modulo responde una sola pregunta antes de abrir cualquier conexion:
este destino, con el nombre ya resuelto, esta permitido?

Uso previsto::

    destino = validar_destino(url_reportada)
    # destino.direcciones ya esta validado: conviene conectar contra esas IPs
    # en lugar de volver a resolver el nombre (evita el DNS rebinding).

El modulo no hace peticiones HTTP: solo decide. Asi se puede probar sin red.
"""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlsplit

__all__ = [
    "DestinoInvalido",
    "DestinoValidado",
    "es_direccion_publica",
    "validar_destino",
]

# Valores por defecto. Los settings (DESTINOS_*) mandan sobre estos.
ESQUEMAS_PERMITIDOS = ("http", "https")
PUERTOS_PERMITIDOS = (80, 443)
PUERTOS_POR_ESQUEMA = {"http": 80, "https": 443}

# Nombres que nunca salen a internet, aunque el DNS los resuelva.
SUFIJOS_BLOQUEADOS = (
    "localhost",
    ".localhost",
    ".local",
    ".localdomain",
    ".internal",
    ".home.arpa",
)

LONGITUD_MAXIMA_URL = 2048

Resolver = Callable[[str, int], list[str]]
DireccionIP = ipaddress.IPv4Address | ipaddress.IPv6Address


class DestinoInvalido(ValueError):
    """El destino no cumple la politica de salida.

    `codigo` permite registrar el motivo sin depender del texto del mensaje.
    """

    def __init__(self, codigo: str, mensaje: str) -> None:
        super().__init__(mensaje)
        self.codigo = codigo
        self.mensaje = mensaje


@dataclass(frozen=True)
class DestinoValidado:
    """Resultado de una validacion correcta."""

    url: str
    esquema: str
    host: str
    puerto: int
    direcciones: tuple[str, ...]

    @property
    def origen(self) -> str:
        return f"{self.esquema}://{self.host}:{self.puerto}"


def _desde_settings(nombre: str, defecto):
    """Lee un setting si Django esta configurado; si no, usa el defecto."""
    try:
        from django.conf import settings
        from django.core.exceptions import ImproperlyConfigured

        try:
            return getattr(settings, nombre, defecto)
        except ImproperlyConfigured:
            return defecto
    except ImportError:  # pragma: no cover - uso del modulo sin Django
        return defecto


def _resolver_dns(host: str, puerto: int) -> list[str]:
    """Resuelve un nombre a todas sus direcciones IPv4 e IPv6."""
    try:
        info = socket.getaddrinfo(host, puerto, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise DestinoInvalido(
            "resolucion_fallida", f"No se pudo resolver el host '{host}'."
        ) from exc
    return list(dict.fromkeys(dato[4][0] for dato in info))


def _direcciones_efectivas(ip: DireccionIP) -> list[DireccionIP]:
    """Desenvuelve direcciones IPv6 que en realidad transportan una IPv4.

    ::ffff:127.0.0.1, 2002::/16 (6to4) y Teredo son rutas conocidas para
    colar una IP privada disfrazada de IPv6 publica.
    """
    efectivas = [ip]
    if isinstance(ip, ipaddress.IPv6Address):
        for envuelta in (ip.ipv4_mapped, ip.sixtofour, ip.teredo[1] if ip.teredo else None):
            if envuelta is not None:
                efectivas.append(envuelta)
    return efectivas


def es_direccion_publica(direccion: str) -> bool:
    """True si la IP es enrutable en internet y no apunta a la red interna."""
    try:
        ip = ipaddress.ip_address(direccion)
    except ValueError:
        return False

    for efectiva in _direcciones_efectivas(ip):
        if (
            efectiva.is_private
            or efectiva.is_loopback
            or efectiva.is_link_local
            or efectiva.is_multicast
            or efectiva.is_reserved
            or efectiva.is_unspecified
        ):
            return False
    return True


def _normalizar_host(host: str) -> str:
    """Pasa el host a minusculas y a su forma ASCII (IDNA)."""
    host = host.strip().rstrip(".").lower()
    if not host:
        raise DestinoInvalido("host_ausente", "La URL no tiene host.")
    if host.isascii():
        return host
    try:
        return host.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise DestinoInvalido("host_invalido", f"El host '{host}' no es un nombre valido.") from exc


def _host_bloqueado(host: str, sufijos: tuple[str, ...]) -> bool:
    return any(host == sufijo.lstrip(".") or host.endswith(sufijo) for sufijo in sufijos)


def validar_destino(
    url: str,
    *,
    resolver: Resolver | None = None,
    esquemas: tuple[str, ...] | None = None,
    puertos: tuple[int, ...] | None = None,
    permitir_privados: bool | None = None,
) -> DestinoValidado:
    """Valida una URL de destino y devuelve sus datos ya resueltos.

    Lanza :class:`DestinoInvalido` en cuanto algo no encaja. Los parametros
    por palabra clave existen para las pruebas y para casos puntuales; en
    produccion mandan los settings DESTINOS_*.
    """
    if not isinstance(url, str):
        raise DestinoInvalido("url_invalida", "La URL debe ser una cadena de texto.")

    url = url.strip()
    if not url:
        raise DestinoInvalido("url_invalida", "La URL esta vacia.")
    if len(url) > LONGITUD_MAXIMA_URL:
        raise DestinoInvalido(
            "url_demasiado_larga",
            f"La URL supera {LONGITUD_MAXIMA_URL} caracteres.",
        )

    esquemas_ok = tuple(
        esquemas
        if esquemas is not None
        else _desde_settings("DESTINOS_ESQUEMAS_PERMITIDOS", ESQUEMAS_PERMITIDOS)
    )
    puertos_ok = tuple(
        puertos
        if puertos is not None
        else _desde_settings("DESTINOS_PUERTOS_PERMITIDOS", PUERTOS_PERMITIDOS)
    )
    privados_ok = (
        permitir_privados
        if permitir_privados is not None
        else bool(_desde_settings("DESTINOS_PERMITIR_PRIVADOS", False))
    )

    try:
        partes = urlsplit(url)
    except ValueError as exc:
        raise DestinoInvalido("url_invalida", "La URL no se puede interpretar.") from exc

    esquema = partes.scheme.lower() or "(ninguno)"
    if esquema not in esquemas_ok:
        raise DestinoInvalido(
            "esquema_no_permitido",
            f"Esquema {esquema} no permitido; se aceptan {list(esquemas_ok)}.",
        )

    # Credenciales embebidas: casi siempre son un intento de saltarse un
    # filtro que mira lo que hay antes de la '@'.
    if "@" in partes.netloc:
        raise DestinoInvalido(
            "credenciales_en_url", "La URL no puede incluir credenciales antes del host."
        )

    try:
        host_bruto = partes.hostname
        puerto = partes.port
    except ValueError as exc:
        raise DestinoInvalido("puerto_invalido", "El puerto de la URL no es valido.") from exc

    if not host_bruto:
        raise DestinoInvalido("host_ausente", "La URL no tiene host.")

    host = _normalizar_host(host_bruto)
    puerto = puerto or PUERTOS_POR_ESQUEMA.get(esquema, 0)

    if puerto not in puertos_ok:
        raise DestinoInvalido(
            "puerto_no_permitido",
            f"Puerto {puerto} no permitido; se aceptan {list(puertos_ok)}.",
        )

    if not privados_ok and _host_bloqueado(host, SUFIJOS_BLOQUEADOS):
        raise DestinoInvalido("host_bloqueado", f"El host '{host}' apunta a la red local.")

    # Si el host ya es una IP literal no hay nada que resolver.
    try:
        ipaddress.ip_address(host)
    except ValueError:
        resolver = resolver or _resolver_dns
        direcciones = resolver(host, puerto)
    else:
        direcciones = [host]

    if not direcciones:
        raise DestinoInvalido(
            "resolucion_fallida", f"El host '{host}' no resolvio a ninguna direccion."
        )

    if not privados_ok:
        # Todas las direcciones deben ser publicas: basta una privada en el
        # round-robin para que la siguiente conexion acabe en la red interna.
        for direccion in direcciones:
            if not es_direccion_publica(direccion):
                raise DestinoInvalido(
                    "direccion_no_publica",
                    f"El host '{host}' resuelve a una direccion no publica ({direccion}).",
                )

    return DestinoValidado(
        url=url,
        esquema=esquema,
        host=host,
        puerto=puerto,
        direcciones=tuple(direcciones),
    )
