"""Modos de ventilación de Balanced.

Las temperaturas y curvas son una copia literal de ``~/.local/bin/alternar-ventilacion``;
``tests/domain/test_fan_modes.py`` comprueba que no diverjan.
"""

from __future__ import annotations

from collections.abc import Mapping

from asus_control.domain.models import Fan, FanCurve, FanMode, Profile

FAN_PROFILE = Profile.BALANCED
"""Único perfil cuyas curvas se gestionan."""

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


def target_curves(mode: FanMode) -> list[FanCurve]:
    """Curvas que deben quedar activas para ``mode`` (vacío en Normal: control automático)."""
    if mode is FanMode.NORMAL:
        return []
    return [FanCurve(fan, pwm, TEMPS, enabled=True) for fan, pwm in CURVES[mode].items()]


def detect_mode(curves: Mapping[Fan, FanCurve]) -> FanMode | None:
    """Identifica el modo activo; ``None`` si las curvas no son de ningún modo conocido."""
    if not any(curve.enabled for curve in curves.values()):
        return FanMode.NORMAL
    for mode in CURVES:
        if all(curves.get(curve.fan) == curve for curve in target_curves(mode)):
            return mode
    return None
