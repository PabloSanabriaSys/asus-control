"""Caso de uso: leer y cambiar el modo de ventilación de Balanced."""

from __future__ import annotations

import logging

from asus_control.application.ports import FanLock, PlatformPort
from asus_control.domain.errors import (
    FanModeError,
    FanModeRequiresBalancedError,
    HardwareAccessError,
    VerificationError,
)
from asus_control.domain.fan_modes import FAN_PROFILE, detect_mode, target_curves
from asus_control.domain.models import FanMode, FanStatus, Setting

logger = logging.getLogger(__name__)


class FanService:
    """Aplica modos con verificación y, si fallan, recupera el control automático."""

    def __init__(self, platform: PlatformPort, lock: FanLock) -> None:
        self._platform = platform
        self._lock = lock

    def read_status(self) -> FanStatus:
        return FanStatus(mode=detect_mode(self._platform.get_fan_curves(FAN_PROFILE)))

    def apply(self, mode: FanMode) -> None:
        """Aplica ``mode`` si el perfil activo es Balanced.

        Lanza ``LockBusyError`` si otro proceso cambia la ventilación,
        ``FanModeRequiresBalancedError`` fuera de Balanced y ``FanModeError`` si no se pudo
        aplicar o confirmar; en ese caso antes intenta volver al modo automático.
        """
        with self._lock():
            self._require_fan_profile()
            try:
                self._write(mode)
                self._verify(mode)
            except (HardwareAccessError, VerificationError) as exc:
                logger.error("Failed to apply fan mode %s: %s", mode, exc)
                raise self._recover(mode) from exc

    def _require_fan_profile(self) -> None:
        # Se revalida dentro del bloqueo: el perfil pudo cambiar desde la última lectura.
        if self._platform.get_profile() is not FAN_PROFILE:
            raise FanModeRequiresBalancedError

    def _write(self, mode: FanMode) -> None:
        curves = target_curves(mode)
        for curve in curves:
            self._platform.set_fan_curve(FAN_PROFILE, curve)
        self._platform.enable_fan_curves(FAN_PROFILE, bool(curves))

    def _verify(self, mode: FanMode) -> None:
        if self.read_status().mode is not mode:
            raise VerificationError(Setting.FAN_MODE)

    def _recover(self, mode: FanMode) -> FanModeError:
        try:
            self._platform.enable_fan_curves(FAN_PROFILE, False)
            restored = self.read_status().mode is FanMode.NORMAL
        except HardwareAccessError:
            restored = False
        return FanModeError(mode, restored=restored)
