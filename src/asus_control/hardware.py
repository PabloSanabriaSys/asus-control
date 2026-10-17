"""Fachada síncrona del hardware: lecturas tolerantes a fallos y cambios verificados."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import replace
from typing import TypeVar

from asus_control.commands import AsusCtl, AuraBus
from asus_control.errors import CommandError, ParseError, VerificationError
from asus_control.fans import FanService
from asus_control.models import Brightness, FanMode, HardwareState, LightbarState, Profile
from asus_control.sensors import SysfsSensors

logger = logging.getLogger(__name__)

T = TypeVar("T")


class HardwareService:
    """Reúne asusctl, el bus de asusd y sysfs. Debe usarse fuera del hilo de la interfaz."""

    def __init__(
        self, asusctl: AsusCtl, aura: AuraBus, fans: FanService, sensors: SysfsSensors
    ) -> None:
        self._asusctl = asusctl
        self._aura = aura
        self._fans = fans
        self._sensors = sensors

    def read_state(self) -> HardwareState:
        """Lee todo; cada dato que falle queda como ``None``."""
        local = HardwareState(
            sensors=self._sensors.read_sensors(), battery=self._sensors.read_battery()
        )
        profile = _optional(self._asusctl.get_profile)
        if profile is None:
            # Sin asusd las demás órdenes también fallarían; se evita esperar por cada una.
            return local
        return replace(
            local,
            profile=profile,
            fans=_optional(self._fans.read_status) if profile is Profile.BALANCED else None,
            brightness=_optional(self._asusctl.get_brightness),
            lightbar=_optional(self._aura.get_lightbar),
            charge_limit=_optional(self._asusctl.get_charge_limit),
        )

    def read_profile(self) -> Profile | None:
        return _optional(self._asusctl.get_profile)

    def set_profile(self, profile: Profile) -> None:
        self._asusctl.set_profile(profile)
        _confirm(self._asusctl.get_profile() is profile, f"el perfil {profile}")

    def set_fan_mode(self, mode: FanMode) -> None:
        self._fans.apply(mode)

    def set_brightness(self, level: Brightness) -> None:
        self._asusctl.set_brightness(level)
        _confirm(self._asusctl.get_brightness() is level, f"el brillo {level.label}")

    def set_charge_limit(self, percent: int) -> None:
        self._asusctl.set_charge_limit(percent)
        _confirm(self._asusctl.get_charge_limit() == percent, f"el límite de carga {percent} %")

    def set_lightbar(self, on: bool) -> None:
        current = self._aura.get_lightbar()
        if current is None:
            raise VerificationError("asusd no admite la cinta LED en este equipo.")
        self._asusctl.set_lightbar_power(replace(current, awake=on))
        state: LightbarState | None = self._aura.get_lightbar()
        _confirm(state is not None and state.awake is on, "el estado de la cinta LED")


def _optional(read: Callable[[], T]) -> T | None:
    try:
        return read()
    except (CommandError, ParseError) as exc:
        logger.info("Lectura no disponible: %s", exc)
        return None


def _confirm(ok: bool, what: str) -> None:
    if not ok:
        raise VerificationError(f"No se pudo confirmar {what}.")
