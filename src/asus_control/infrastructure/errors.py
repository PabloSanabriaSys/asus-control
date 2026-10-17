"""Errores concretos de acceso al hardware."""

from asus_control.domain.errors import HardwareAccessError


class CommandError(HardwareAccessError):
    """Una orden externa falló, no existe o superó el tiempo límite."""


class ParseError(HardwareAccessError):
    """La salida de una orden no tiene el formato esperado."""
