"""Simulación con estado de las órdenes de asusctl usadas por la aplicación."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from asus_control.infrastructure.errors import CommandError

_DEFAULT_PWM = (255,) * 8
_DEFAULT_TEMPS = (40, 55, 64, 68, 71, 74, 77, 80)


@dataclass
class StoredCurve:
    pwm: tuple[int, ...] = _DEFAULT_PWM
    temps: tuple[int, ...] = _DEFAULT_TEMPS
    enabled: bool = False


@dataclass
class FakeAsusd:
    profile: str = "Balanced"
    brightness: str = "High"
    charge_limit: int = 60
    curves: dict[str, StoredCurve] = field(
        default_factory=lambda: {fan: StoredCurve() for fan in ("CPU", "GPU", "MID")}
    )
    fail_on: set[tuple[str, ...]] = field(default_factory=set)
    """Prefijos de argumentos que deben fallar."""
    ignore_writes: bool = False
    calls: list[list[str]] = field(default_factory=list)

    def __call__(self, args: Sequence[str]) -> str:
        self.calls.append(list(args))
        if any(tuple(args[: len(prefix)]) == prefix for prefix in self.fail_on):
            raise CommandError(f"fallo simulado: {' '.join(args)}")
        match list(args):
            case ["profile", "get"]:
                return f"Active profile: {self.profile}\n\nAC profile Balanced\n"
            case ["profile", "set", name]:
                self._write("profile", name)
            case ["leds", "get"]:
                return f"Current keyboard led brightness: {self.brightness}\n"
            case ["leds", "set", level]:
                self._write("brightness", level.capitalize())
            case ["battery", "info"]:
                return f"Current battery charge limit: {self.charge_limit}%\n"
            case ["battery", "limit", value]:
                self._write("charge_limit", int(value))
            case ["fan-curve", "--mod-profile", "Balanced"]:
                return self._render_curves()
            case ["fan-curve", "--mod-profile", "Balanced", "--fan", fan, "--data", data]:
                if not self.ignore_writes:
                    self._store_curve(fan.upper(), data)
            case ["fan-curve", "--mod-profile", "Balanced", "--enable-fan-curves", value]:
                if not self.ignore_writes:
                    for curve in self.curves.values():
                        curve.enabled = value == "true"
            case _:
                raise CommandError(f"orden no simulada: {args}")
        return ""

    def _write(self, attribute: str, value: object) -> None:
        if not self.ignore_writes:
            setattr(self, attribute, value)

    def _store_curve(self, fan: str, data: str) -> None:
        points = [point.split(":") for point in data.split(",")]
        curve = self.curves[fan]
        curve.temps = tuple(int(temp.removesuffix("c")) for temp, _ in points)
        curve.pwm = tuple(int(pwm) for _, pwm in points)

    def _render_curves(self) -> str:
        entries = "".join(
            f"    (\n        fan: {fan},\n"
            f"        pwm: ({', '.join(map(str, curve.pwm))}),\n"
            f"        temp: ({', '.join(map(str, curve.temps))}),\n"
            f"        enabled: {str(curve.enabled).lower()},\n    ),\n"
            for fan, curve in self.curves.items()
        )
        return f"\nFan curves for Balanced\n\n[\n{entries}]\n"
