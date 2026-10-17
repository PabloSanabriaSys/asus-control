"""Adaptador de ``PlatformPort`` sobre la línea de órdenes ``asusctl``."""

from __future__ import annotations

from asus_control.domain.models import Brightness, Fan, FanCurve, Profile
from asus_control.infrastructure.asusctl_parsing import (
    BRIGHTNESS_ARGUMENTS,
    format_curve_data,
    parse_active_profile,
    parse_brightness,
    parse_charge_limit,
    parse_fan_curves,
)
from asus_control.infrastructure.process import CommandRunner


class AsusCtl:
    """Operaciones de asusctl; cada llamada es síncrona y bloqueante."""

    def __init__(self, run: CommandRunner) -> None:
        self._run = run

    def get_profile(self) -> Profile:
        return parse_active_profile(self._run(["profile", "get"]))

    def set_profile(self, profile: Profile) -> None:
        # Sin -a/-b: asusd conserva sus perfiles de corriente y batería.
        self._run(["profile", "set", profile.value])

    def get_fan_curves(self, profile: Profile) -> dict[Fan, FanCurve]:
        return parse_fan_curves(self._run(["fan-curve", "--mod-profile", profile.value]))

    def set_fan_curve(self, profile: Profile, curve: FanCurve) -> None:
        fan = curve.fan.value.lower()
        data = format_curve_data(curve)
        self._run(["fan-curve", "--mod-profile", profile.value, "--fan", fan, "--data", data])

    def enable_fan_curves(self, profile: Profile, enabled: bool) -> None:
        flag = "true" if enabled else "false"
        self._run(["fan-curve", "--mod-profile", profile.value, "--enable-fan-curves", flag])

    def get_brightness(self) -> Brightness:
        return parse_brightness(self._run(["leds", "get"]))

    def set_brightness(self, level: Brightness) -> None:
        self._run(["leds", "set", BRIGHTNESS_ARGUMENTS[level]])

    def get_charge_limit(self) -> int:
        return parse_charge_limit(self._run(["battery", "info"]))

    def set_charge_limit(self, percent: int) -> None:
        self._run(["battery", "limit", str(percent)])
