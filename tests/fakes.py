"""Dobles en memoria de los puertos de la aplicación."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field

from asus_control.domain.errors import HardwareAccessError
from asus_control.domain.fan_modes import TEMPS
from asus_control.domain.models import (
    BatteryStatus,
    Brightness,
    Fan,
    FanCurve,
    LightbarState,
    Profile,
    SensorReadings,
)


def automatic_curves() -> dict[Fan, FanCurve]:
    """Curvas tal como las deja asusd con el control automático (desactivadas)."""
    return {fan: FanCurve(fan, (255,) * 8, TEMPS, enabled=False) for fan in Fan}


@dataclass
class FakePlatform:
    """``PlatformPort`` con estado.

    ``failing``: métodos que siempre fallan. ``fail_on``: método → número de llamada
    (desde 1) que falla, para simular fallos parciales.
    """

    profile: Profile = Profile.BALANCED
    brightness: Brightness = Brightness.HIGH
    charge_limit: int = 60
    curves: dict[Fan, FanCurve] = field(default_factory=automatic_curves)
    failing: set[str] = field(default_factory=set)
    fail_on: dict[str, int] = field(default_factory=dict)
    ignore_writes: bool = False
    calls: list[str] = field(default_factory=list)

    def get_profile(self) -> Profile:
        self._call("get_profile")
        return self.profile

    def set_profile(self, profile: Profile) -> None:
        self._call("set_profile")
        if not self.ignore_writes:
            self.profile = profile

    def get_fan_curves(self, profile: Profile) -> Mapping[Fan, FanCurve]:
        self._call("get_fan_curves")
        return dict(self.curves)

    def set_fan_curve(self, profile: Profile, curve: FanCurve) -> None:
        self._call("set_fan_curve")
        if not self.ignore_writes:
            enabled = self.curves[curve.fan].enabled
            self.curves[curve.fan] = FanCurve(curve.fan, curve.pwm, curve.temps, enabled)

    def enable_fan_curves(self, profile: Profile, enabled: bool) -> None:
        self._call("enable_fan_curves")
        if not self.ignore_writes:
            for fan, curve in self.curves.items():
                self.curves[fan] = FanCurve(fan, curve.pwm, curve.temps, enabled)

    def get_brightness(self) -> Brightness:
        self._call("get_brightness")
        return self.brightness

    def set_brightness(self, level: Brightness) -> None:
        self._call("set_brightness")
        if not self.ignore_writes:
            self.brightness = level

    def get_charge_limit(self) -> int:
        self._call("get_charge_limit")
        return self.charge_limit

    def set_charge_limit(self, percent: int) -> None:
        self._call("set_charge_limit")
        if not self.ignore_writes:
            self.charge_limit = percent

    def _call(self, name: str) -> None:
        self.calls.append(name)
        if name in self.failing or self.fail_on.get(name) == self.calls.count(name):
            raise HardwareAccessError(f"fallo simulado: {name}")


@dataclass
class FakeLightbar:
    """``LightbarPort``; ``state`` nulo equivale a un equipo sin cinta LED."""

    state: LightbarState | None = field(
        default_factory=lambda: LightbarState(boot=True, awake=False, sleep=True, shutdown=True)
    )

    def read(self) -> LightbarState | None:
        return self.state

    def write(self, state: LightbarState) -> None:
        self.state = state


@dataclass
class FakeSensors:
    """``SensorPort`` con lecturas fijas."""

    sensors: SensorReadings = field(default_factory=SensorReadings)
    battery: BatteryStatus | None = None

    def read_sensors(self) -> SensorReadings:
        return self.sensors

    def read_battery(self) -> BatteryStatus | None:
        return self.battery


@contextmanager
def no_lock() -> Iterator[None]:
    yield
