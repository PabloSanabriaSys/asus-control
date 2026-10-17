"""Excepciones de la aplicación."""


class AsusControlError(Exception):
    """Base de los errores esperados; su mensaje se muestra al usuario."""


class CommandError(AsusControlError):
    """Una orden externa falló, no existe o superó el tiempo límite."""


class ParseError(AsusControlError):
    """La salida de una orden no tiene el formato esperado."""


class VerificationError(AsusControlError):
    """La lectura posterior no confirma el cambio solicitado."""


class LockBusyError(AsusControlError):
    """Otro proceso está cambiando la ventilación."""


class FanModeError(AsusControlError):
    """Falló un cambio de ventilación; ``restored`` indica si se recuperó el modo automático."""

    def __init__(self, message: str, *, restored: bool | None) -> None:
        super().__init__(message)
        self.restored = restored
