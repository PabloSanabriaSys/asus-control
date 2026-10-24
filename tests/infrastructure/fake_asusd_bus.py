"""Simulación con estado de ``busctl`` frente a asusd: mismas órdenes y mismo JSON."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field

from asus_control.infrastructure.errors import CommandError

AURA_PATH = "/xyz/ljones/aura/19b6_2_4"
_DEFAULT_PWM = [255] * 8
_DEFAULT_TEMPS = [40, 55, 64, 68, 71, 74, 77, 80]


def _automatic_curves() -> dict[str, list[object]]:
    return {
        fan: [fan, list(_DEFAULT_PWM), list(_DEFAULT_TEMPS), False] for fan in ("CPU", "GPU", "MID")
    }


@dataclass
class FakeAsusdBus:
    profile: int = 0
    brightness: int = 3
    charge_limit: int = 60
    power_zones: list[int] = field(default_factory=lambda: [1, 2])
    led_power: list[list[object]] = field(
        default_factory=lambda: [[1, True, True, True, True], [2, True, False, True, True]]
    )
    curves: dict[str, list[object]] = field(default_factory=_automatic_curves)
    quiet_curves: dict[str, list[object]] = field(default_factory=_automatic_curves)
    auto_ac: bool = True
    auto_battery: bool = True
    armoury: dict[str, int] = field(
        default_factory=lambda: {"panel_overdrive": 1, "dgpu_disable": 0}
    )
    fail_on: set[str] = field(default_factory=set)
    """Miembros D-Bus (propiedad o método) cuya llamada falla."""
    calls: list[list[str]] = field(default_factory=list)

    def __call__(self, args: Sequence[str]) -> str:
        args = [arg for arg in args if arg not in {"--system", "--json=short"}]
        self.calls.append(args)
        match args:
            case ["--list", "tree", _service]:
                return f"/\n/xyz\n/xyz/ljones\n/xyz/ljones/aura\n{AURA_PATH}\n"
            case ["get-property", _service, path, _iface, name]:
                self._check(name)
                return self._get(name, path)
            case ["set-property", _service, path, _iface, name, _signature, *values]:
                self._check(name)
                self._set(name, values, path)
                return ""
            case ["call", _service, _path, _iface, method, _signature, *values]:
                self._check(method)
                return self._call(method, values)
        raise CommandError(f"orden no simulada: {args}")

    def _check(self, member: str) -> None:
        if member in self.fail_on:
            raise CommandError(f"fallo simulado: {member}")

    def _get(self, name: str, path: str) -> str:
        values: dict[str, tuple[str, object]] = {
            "PlatformProfile": ("u", self.profile),
            "Brightness": ("u", self.brightness),
            "ChargeControlEndThreshold": ("y", self.charge_limit),
            "SupportedPowerZones": ("au", self.power_zones),
            "LedPower": ("(a(ubbbb))", [self.led_power]),
            "ChangePlatformProfileOnAc": ("b", self.auto_ac),
            "ChangePlatformProfileOnBattery": ("b", self.auto_battery),
        }
        if name == "CurrentValue":
            return json.dumps({"type": "i", "data": self.armoury[path.rsplit("/", 1)[-1]]})
        signature, value = values[name]
        return json.dumps({"type": signature, "data": value})

    def _set(self, name: str, values: list[str], path: str) -> None:
        match name:
            case "PlatformProfile":
                self.profile = int(values[0])
            case "Brightness":
                self.brightness = int(values[0])
            case "ChargeControlEndThreshold":
                self.charge_limit = int(values[0])
            case "ChangePlatformProfileOnAc":
                self.auto_ac = values[0] == "true"
            case "ChangePlatformProfileOnBattery":
                self.auto_battery = values[0] == "true"
            case "CurrentValue":
                self.armoury[path.rsplit("/", 1)[-1]] = int(values[0])
            case "LedPower":
                count, flat = int(values[0]), values[1:]
                self.led_power = [
                    [int(flat[i * 5]), *(flag == "true" for flag in flat[i * 5 + 1 : i * 5 + 5])]
                    for i in range(count)
                ]

    def _call(self, method: str, values: list[str]) -> str:
        curves = self.quiet_curves if values and values[0] == "2" else self.curves
        match method:
            case "FanCurveData":
                data = [[curves[fan] for fan in ("CPU", "GPU", "MID")]]
                return json.dumps({"type": "a(s(yyyyyyyy)(yyyyyyyy)b)", "data": data})
            case "SetFanCurve":
                _profile, fan, *rest = values
                curves[fan] = [
                    fan,
                    [int(v) for v in rest[:8]],
                    [int(v) for v in rest[8:16]],
                    rest[16] == "true",
                ]
            case "SetFanCurvesEnabled":
                for curve in curves.values():
                    curve[3] = values[1] == "true"
            case "SetProfileFanCurveEnabled":
                curves[values[1]][3] = values[2] == "true"
        return ""
