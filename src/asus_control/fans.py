"""Modos de ventilación de Balanced.

Las temperaturas y curvas son una copia literal de ``~/.local/bin/alternar-ventilacion``;
``tests/test_fans.py`` comprueba que no diverjan.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager

from asus_control.commands import AsusCtl
from asus_control.errors import (
    CommandError,
    FanModeError,
    ParseError,
    VerificationError,
)
from asus_control.models import Fan, FanCurve, FanMode, FanStatus, Profile

logger = logging.getLogger(__name__)

FAN_PROFILE = Profile.BALANCED

TEMPS: tuple[int, ...] = (40, 55, 64, 68, 71, 74, 77, 80)
CURVES: Mapping[FanMode, Mapping[Fan, tuple[int, ...]]] = {
    FanMode.ULTRA_MEGA: dict.fromkeys(Fan, (255,) * 8),
    FanMode.EXTRA: {
        Fan.CPU: (51, 71, 89, 107, 128, 153, 191, 230),
        Fan.GPU: (51, 71, 89, 107, 128, 153, 191, 230),
        Fan.MID: (26, 51, 77, 97, 115, 128, 140, 153),
    },
    FanMode.ULTRA: {
        Fan.CPU: (89, 115, 140, 166, 191, 217, 242, 255),
        Fan.GPU: (89, 115, 140, 166, 191, 217, 242, 255),
        Fan.MID: (51, 77, 102, 128, 153, 179, 204, 230),
    },
}

LockFactory = Callable[[], AbstractContextManager[None]]


def detect_mode(curves: Mapping[Fan, FanCurve]) -> FanMode | None:
    """Identifica el modo activo; ``None`` si las curvas no son de ningún modo conocido."""
    if not any(curve.enabled for curve in curves.values()):
        return FanMode.NORMAL
    for mode, targets in CURVES.items():
        if all(
            curves[fan] == FanCurve(fan, pwm, TEMPS, enabled=True) for fan, pwm in targets.items()
        ):
            return mode
    return None


def curve_data(pwm: tuple[int, ...]) -> str:
    """Formato ``--data`` de asusctl: ``40c:51,55c:71,...`` (PWM 0-255)."""
    return ",".join(f"{temp}c:{value}" for temp, value in zip(TEMPS, pwm, strict=True))


class FanService:
    """Lee y aplica modos de ventilación con verificación y recuperación."""

    def __init__(self, asusctl: AsusCtl, lock: LockFactory) -> None:
        self._asusctl = asusctl
        self._lock = lock

    def read_status(self) -> FanStatus:
        return FanStatus(mode=detect_mode(self._asusctl.get_fan_curves(FAN_PROFILE)))

    def apply(self, mode: FanMode) -> None:
        """Aplica ``mode`` si el perfil activo es Balanced.

        Lanza ``LockBusyError`` si otro proceso cambia la ventilación y ``FanModeError``
        si no se pudo aplicar o confirmar; en ese caso intenta volver al modo automático.
        """
        with self._lock():
            if self._asusctl.get_profile() is not FAN_PROFILE:
                raise FanModeError(
                    "La ventilación solo se puede cambiar en Balanced. No se cambió el perfil.",
                    restored=None,
                )
            try:
                self._write(mode)
                self._verify(mode)
            except (CommandError, ParseError, VerificationError) as exc:
                logger.error("Fallo al aplicar %s: %s", mode, exc)
                raise self._recover(mode) from exc

    def _write(self, mode: FanMode) -> None:
        if mode is FanMode.NORMAL:
            self._asusctl.enable_fan_curves(FAN_PROFILE, False)
            return
        for fan, pwm in CURVES[mode].items():
            self._asusctl.set_fan_curve(FAN_PROFILE, fan, curve_data(pwm))
        self._asusctl.enable_fan_curves(FAN_PROFILE, True)

    def _verify(self, mode: FanMode) -> None:
        if self.read_status().mode is not mode:
            raise VerificationError(f"No se pudo confirmar la ventilación {mode}.")

    def _recover(self, mode: FanMode) -> FanModeError:
        try:
            self._asusctl.enable_fan_curves(FAN_PROFILE, False)
            restored = self.read_status().mode is FanMode.NORMAL
        except (CommandError, ParseError):
            restored = False
        if restored:
            message = f"No se pudo aplicar {mode}. Se restauró el control automático."
        else:
            message = f"No se pudo aplicar {mode} ni restaurar el control automático."
        return FanModeError(message, restored=restored)
