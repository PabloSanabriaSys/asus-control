"""Puertos: lo que la aplicación necesita del exterior, sin saber cómo se implementa.

La infraestructura los implementa (D-Bus de asusd, sysfs, ``flock``) y las
pruebas los sustituyen por dobles en memoria. Ante cualquier fallo de acceso se lanza
``HardwareAccessError``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from typing import Protocol

from asus_control.domain.models import (
    BatteryStatus,
    Brightness,
    Fan,
    FanCurve,
    LightbarState,
    Profile,
    SensorReadings,
)
from asus_control.domain.power_saving import PowerSavingCapture, PowerSavingSession


class PowerSavingStore(Protocol):
    def load(self) -> PowerSavingSession | None: ...

    def save(self, session: PowerSavingSession | None) -> None: ...


class PowerSavingDevice(Protocol):
    def capture(self, brightness_percent: int) -> PowerSavingCapture: ...

    def read(self, key: str) -> str: ...

    def write(self, key: str, value: str) -> None: ...


class PlatformPort(Protocol):
    """Ajustes de plataforma gestionados por asusd."""

    def get_profile(self) -> Profile: ...

    def set_profile(self, profile: Profile) -> None: ...

    def get_fan_curves(self, profile: Profile) -> Mapping[Fan, FanCurve]: ...

    def set_fan_curve(self, profile: Profile, curve: FanCurve) -> None:
        """Escribe los puntos de la curva; su activación se controla con ``enable_fan_curves``."""
        ...

    def enable_fan_curves(self, profile: Profile, enabled: bool) -> None: ...

    def get_brightness(self) -> Brightness: ...

    def set_brightness(self, level: Brightness) -> None: ...

    def get_charge_limit(self) -> int: ...

    def set_charge_limit(self, percent: int) -> None: ...


class LightbarPort(Protocol):
    """Estados de energía de la cinta LED."""

    def read(self) -> LightbarState | None:
        """Estado actual, o ``None`` si el equipo no admite la cinta."""
        ...

    def write(self, state: LightbarState) -> None: ...


class SensorPort(Protocol):
    """Sensores y batería; los datos que falten llegan como ``None``, nunca como error."""

    def read_sensors(self) -> SensorReadings: ...

    def read_battery(self) -> BatteryStatus | None: ...


FanLock = Callable[[], AbstractContextManager[None]]
"""Bloqueo exclusivo de los cambios de ventilación; lanza ``LockBusyError`` si está ocupado."""
