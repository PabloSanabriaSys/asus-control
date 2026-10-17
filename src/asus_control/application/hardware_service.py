"""Caso de uso principal: leer el estado del equipo y aplicar cambios verificados."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import replace
from typing import TypeVar

from asus_control.application.fan_service import FanService
from asus_control.application.ports import LightbarPort, PlatformPort, SensorPort
from asus_control.domain.errors import HardwareAccessError, VerificationError
from asus_control.domain.fan_modes import FAN_PROFILE
from asus_control.domain.models import Brightness, FanMode, HardwareState, Profile

logger = logging.getLogger(__name__)

T = TypeVar("T")


class HardwareService:
    """Lecturas tolerantes a fallos y cambios confirmados con una lectura posterior."""

    def __init__(
        self,
        platform: PlatformPort,
        lightbar: LightbarPort,
        sensors: SensorPort,
        fans: FanService,
    ) -> None:
        self._platform = platform
        self._lightbar = lightbar
        self._sensors = sensors
        self._fans = fans

    def read_state(self) -> HardwareState:
        """Lee todo sin escribir nada; cada dato que falle queda como ``None``."""
        local = HardwareState(
            sensors=self._sensors.read_sensors(), battery=self._sensors.read_battery()
        )
        profile = _optional(self._platform.get_profile)
        if profile is None:
            # Sin asusd las demás lecturas también fallarían; se evita esperar por cada una.
            return local
        return replace(
            local,
            profile=profile,
            fans=_optional(self._fans.read_status) if profile is FAN_PROFILE else None,
            brightness=_optional(self._platform.get_brightness),
            lightbar=_optional(self._lightbar.read),
            charge_limit=_optional(self._platform.get_charge_limit),
        )

    def read_profile(self) -> Profile | None:
        return _optional(self._platform.get_profile)

    def set_profile(self, profile: Profile) -> None:
        self._platform.set_profile(profile)
        _confirm(self._platform.get_profile() is profile, f"el perfil {profile}")

    def set_fan_mode(self, mode: FanMode) -> None:
        self._fans.apply(mode)

    def set_brightness(self, level: Brightness) -> None:
        self._platform.set_brightness(level)
        _confirm(self._platform.get_brightness() is level, "el brillo")

    def set_charge_limit(self, percent: int) -> None:
        self._platform.set_charge_limit(percent)
        _confirm(self._platform.get_charge_limit() == percent, f"el límite de carga {percent} %")

    def set_lightbar(self, on: bool) -> None:
        current = self._lightbar.read()
        if current is None:
            raise VerificationError("asusd no admite la cinta LED en este equipo.")
        # Solo cambia el estado «despierto»; arranque, suspensión y apagado se conservan.
        self._lightbar.write(replace(current, awake=on))
        updated = self._lightbar.read()
        _confirm(updated is not None and updated.awake is on, "el estado de la cinta LED")


def _optional(read: Callable[[], T]) -> T | None:
    try:
        return read()
    except HardwareAccessError as exc:
        logger.info("Lectura no disponible: %s", exc)
        return None


def _confirm(ok: bool, what: str) -> None:
    if not ok:
        raise VerificationError(f"No se pudo confirmar {what}.")
