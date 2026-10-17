"""Errores esperados.

Llevan datos estructurados, no textos para el usuario: la presentación los traduce
(el applet de Plasma los muestra en el idioma del sistema). ``str(error)`` es una
descripción técnica en inglés para los registros.
"""

from __future__ import annotations

from asus_control.domain.models import FanMode, Setting


class AsusControlError(Exception):
    """Base de todos los errores esperados."""


class HardwareAccessError(AsusControlError):
    """No se pudo leer o escribir el hardware (asusd caído, orden fallida, salida inesperada).

    La infraestructura lanza subclases concretas; la aplicación solo conoce esta base.
    """


class VerificationError(AsusControlError):
    """La lectura posterior no confirma el cambio de ``setting``."""

    def __init__(self, setting: Setting) -> None:
        super().__init__(f"Could not confirm the new {setting} value.")
        self.setting = setting


class LightbarUnsupportedError(AsusControlError):
    """asusd no publica la zona Lightbar en este equipo."""

    def __init__(self) -> None:
        super().__init__("asusd does not support the lightbar on this device.")


class LockBusyError(AsusControlError):
    """Otro proceso está cambiando la ventilación."""

    def __init__(self) -> None:
        super().__init__("Another fan change is in progress.")


class FanModeRequiresBalancedError(AsusControlError):
    """Los modos de ventilación solo existen en Balanced; el perfil no se cambia."""

    def __init__(self) -> None:
        super().__init__("Fan modes can only be changed in Balanced.")


class FanModeError(AsusControlError):
    """Falló un cambio de ventilación; ``restored`` indica si se recuperó el modo automático."""

    def __init__(self, mode: FanMode, *, restored: bool) -> None:
        outcome = "automatic control restored" if restored else "automatic control NOT restored"
        super().__init__(f"Could not apply fan mode {mode} ({outcome}).")
        self.mode = mode
        self.restored = restored
