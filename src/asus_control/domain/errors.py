"""Errores esperados de la aplicación; su mensaje se muestra al usuario."""


class AsusControlError(Exception):
    """Base de todos los errores esperados."""


class HardwareAccessError(AsusControlError):
    """No se pudo leer o escribir el hardware (asusd caído, orden fallida, salida inesperada).

    La infraestructura lanza subclases concretas; la aplicación solo conoce esta base.
    """


class VerificationError(AsusControlError):
    """La lectura posterior no confirma el cambio solicitado."""


class LockBusyError(AsusControlError):
    """Otro proceso está cambiando la ventilación."""


class FanModeError(AsusControlError):
    """Falló un cambio de ventilación; ``restored`` indica si se recuperó el modo automático."""

    def __init__(self, message: str, *, restored: bool | None) -> None:
        super().__init__(message)
        self.restored = restored
