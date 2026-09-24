#!/usr/bin/env python
"""Utilidad de linea de comandos de Django para alerta-segura."""

import os
import sys


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:  # pragma: no cover - solo entorno mal instalado
        raise ImportError(
            "No se pudo importar Django. Revisa que este instalado y que el "
            "entorno virtual este activo."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
