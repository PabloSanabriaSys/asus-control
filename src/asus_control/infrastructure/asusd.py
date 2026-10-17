"""Adaptadores de ``PlatformPort`` y ``LightbarPort`` sobre la interfaz D-Bus de asusd 6.5.

Es la misma interfaz que usa ``asusctl``, sin el coste de arrancar un proceso cliente
por cada orden. Valores verificados en el equipo (ver ``tests/fixtures/dbus_*.json``).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from asus_control.domain.models import Brightness, Fan, FanCurve, LightbarState, Profile
from asus_control.infrastructure.busctl import Busctl
from asus_control.infrastructure.errors import ParseError

ASUSD_SERVICE = "xyz.ljones.Asusd"
_ROOT_PATH = "/xyz/ljones"
_PLATFORM = "xyz.ljones.Platform"
_FAN_CURVES = "xyz.ljones.FanCurves"
_AURA = "xyz.ljones.Aura"
_AURA_PATH_PREFIX = "/xyz/ljones/aura/"

PROFILE_CODES = {Profile.BALANCED: 0, Profile.PERFORMANCE: 1, Profile.QUIET: 2}
"""``PlatformProfile`` de asusd; los métodos de ``FanCurves`` usan los mismos códigos."""

BRIGHTNESS_CODES = {Brightness.OFF: 0, Brightness.LOW: 1, Brightness.MEDIUM: 2, Brightness.HIGH: 3}

LIGHTBAR_POWER_ZONE = 2
"""``PowerZones::Lightbar``; ``1`` es ``Keyboard``."""

_FAN_CURVE_SIGNATURE = "u(s(yyyyyyyy)(yyyyyyyy)b)"
_LED_POWER_SIGNATURE = "(a(ubbbb))"


class AuraDevice:
    """Ruta D-Bus del dispositivo Aura (p. ej. ``/xyz/ljones/aura/19b6_2_4``), resuelta una vez."""

    def __init__(self, bus: Busctl) -> None:
        self._bus = bus
        self._path: str | None = None

    @property
    def path(self) -> str:
        if self._path is None:
            self._path = parse_aura_path(self._bus.object_paths())
        return self._path


class AsusdPlatform:
    """Perfil, curvas de ventilación, brillo y límite de carga."""

    def __init__(self, bus: Busctl, aura: AuraDevice) -> None:
        self._bus = bus
        self._aura = aura

    def get_profile(self) -> Profile:
        code = self._bus.get_property(_ROOT_PATH, _PLATFORM, "PlatformProfile")
        return _decode(PROFILE_CODES, code, "profile")

    def set_profile(self, profile: Profile) -> None:
        # Solo el perfil activo: PlatformProfileOnAc/OnBattery (gestión de asusd) no se tocan.
        self._bus.set_property(
            _ROOT_PATH, _PLATFORM, "PlatformProfile", "u", PROFILE_CODES[profile]
        )

    def get_fan_curves(self, profile: Profile) -> dict[Fan, FanCurve]:
        reply = self._bus.call(_ROOT_PATH, _FAN_CURVES, "FanCurveData", "u", PROFILE_CODES[profile])
        return parse_fan_curves(reply)

    def set_fan_curve(self, profile: Profile, curve: FanCurve) -> None:
        self._bus.call(
            _ROOT_PATH,
            _FAN_CURVES,
            "SetFanCurve",
            _FAN_CURVE_SIGNATURE,
            PROFILE_CODES[profile],
            curve.fan.value,
            *curve.pwm,
            *curve.temps,
            curve.enabled,
        )

    def enable_fan_curves(self, profile: Profile, enabled: bool) -> None:
        self._bus.call(
            _ROOT_PATH, _FAN_CURVES, "SetFanCurvesEnabled", "ub", PROFILE_CODES[profile], enabled
        )

    def get_brightness(self) -> Brightness:
        code = self._bus.get_property(self._aura.path, _AURA, "Brightness")
        return _decode(BRIGHTNESS_CODES, code, "brightness")

    def set_brightness(self, level: Brightness) -> None:
        self._bus.set_property(self._aura.path, _AURA, "Brightness", "u", BRIGHTNESS_CODES[level])

    def get_charge_limit(self) -> int:
        value = self._bus.get_property(_ROOT_PATH, _PLATFORM, "ChargeControlEndThreshold")
        if not isinstance(value, int):
            raise ParseError(f"Unexpected charge limit: {value!r}")
        return value

    def set_charge_limit(self, percent: int) -> None:
        self._bus.set_property(_ROOT_PATH, _PLATFORM, "ChargeControlEndThreshold", "y", percent)


class AsusdLightbar:
    """Estados de energía de la cinta LED en ``LedPower``.

    El soporte real se toma de ``SupportedPowerZones``: sin la zona Lightbar, la cinta
    no está disponible.
    """

    def __init__(self, bus: Busctl, aura: AuraDevice) -> None:
        self._bus = bus
        self._aura = aura

    def read(self) -> LightbarState | None:
        zones = self._bus.get_property(self._aura.path, _AURA, "SupportedPowerZones")
        if not isinstance(zones, list) or LIGHTBAR_POWER_ZONE not in zones:
            return None
        return parse_lightbar_power(self._led_power())

    def write(self, state: LightbarState) -> None:
        # LedPower se escribe completo: se conservan las demás zonas (teclado) tal cual.
        entries = [
            entry
            for entry in parse_led_power_entries(self._led_power())
            if entry[0] != LIGHTBAR_POWER_ZONE
        ]
        entries.append((LIGHTBAR_POWER_ZONE, state.boot, state.awake, state.sleep, state.shutdown))
        values = [value for entry in entries for value in entry]
        self._bus.set_property(
            self._aura.path, _AURA, "LedPower", _LED_POWER_SIGNATURE, len(entries), *values
        )

    def _led_power(self) -> object:
        return self._bus.get_property(self._aura.path, _AURA, "LedPower")


PowerEntry = tuple[int, bool, bool, bool, bool]
T = TypeVar("T")


def parse_aura_path(paths: list[str]) -> str:
    for path in paths:
        if path.startswith(_AURA_PATH_PREFIX):
            return path
    raise ParseError("asusd exposes no Aura device.")


def parse_fan_curves(reply: object) -> dict[Fan, FanCurve]:
    """Respuesta de ``FanCurveData``: ``[[[nombre, pwm[8], temps[8], activa], ...]]``."""
    entries = _single_value(reply, "FanCurveData")
    try:
        curves = {
            Fan(name): FanCurve(Fan(name), tuple(pwm), tuple(temps), bool(enabled))
            for name, pwm, temps, enabled in entries
        }
    except (TypeError, ValueError) as exc:
        raise ParseError(f"Unexpected FanCurveData reply: {reply!r}") from exc
    if set(curves) != set(Fan):
        raise ParseError("Could not read the three fan curves.")
    return curves


def parse_led_power_entries(data: object) -> list[PowerEntry]:
    """``LedPower``: ``[[[zona, arranque, activo, suspensión, apagado], ...]]``."""
    entries = _single_value(data, "LedPower")
    try:
        return [
            (int(zone), bool(boot), bool(awake), bool(sleep), bool(shutdown))
            for zone, boot, awake, sleep, shutdown in entries
        ]
    except (TypeError, ValueError) as exc:
        raise ParseError(f"Unexpected LedPower value: {data!r}") from exc


def parse_lightbar_power(data: object) -> LightbarState | None:
    for zone, boot, awake, sleep, shutdown in parse_led_power_entries(data):
        if zone == LIGHTBAR_POWER_ZONE:
            return LightbarState(boot=boot, awake=awake, sleep=sleep, shutdown=shutdown)
    return None


def _single_value(data: object, what: str) -> list[Any]:
    """busctl devuelve la estructura externa como una lista de un elemento."""
    if not isinstance(data, list) or len(data) != 1 or not isinstance(data[0], list):
        raise ParseError(f"Unexpected {what} value: {data!r}")
    return data[0]


def _decode(codes: Mapping[T, int], value: object, what: str) -> T:
    for item, code in codes.items():
        if code == value:
            return item
    raise ParseError(f"Unknown {what} code: {value!r}")
