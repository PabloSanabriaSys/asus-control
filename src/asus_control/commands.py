"""Clientes de asusctl y del bus de asusd.

Las llamadas son síncronas y deben ejecutarse fuera del hilo de la interfaz.
"""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Sequence
from typing import Protocol

from asus_control.errors import CommandError
from asus_control.models import Brightness, Fan, FanCurve, LightbarState, Profile
from asus_control.parsing import (
    LIGHTBAR_POWER_ZONE,
    parse_active_profile,
    parse_aura_object_path,
    parse_brightness,
    parse_charge_limit,
    parse_fan_curves,
    parse_lightbar_power,
    parse_power_zones,
)

logger = logging.getLogger(__name__)

ASUSCTL = "/usr/bin/asusctl"
BUSCTL = "/usr/bin/busctl"
COMMAND_TIMEOUT_SECONDS = 10.0

_ASUSD_SERVICE = "xyz.ljones.Asusd"
_AURA_INTERFACE = "xyz.ljones.Aura"


class CommandRunner(Protocol):
    """Ejecuta una orden con argumentos separados y devuelve su salida estándar."""

    def __call__(self, args: Sequence[str]) -> str: ...


class SubprocessRunner:
    """Ejecuta un programa fijo sin shell y con tiempo límite."""

    def __init__(self, executable: str, timeout: float = COMMAND_TIMEOUT_SECONDS) -> None:
        self._executable = executable
        self._timeout = timeout

    def __call__(self, args: Sequence[str]) -> str:
        command = [self._executable, *args]
        logger.debug("Ejecutando %s", command)
        try:
            completed = subprocess.run(
                command, check=True, capture_output=True, text=True, timeout=self._timeout
            )
        except FileNotFoundError as exc:
            raise CommandError(f"No se encontró {self._executable}.") from exc
        except subprocess.TimeoutExpired as exc:
            raise CommandError(f"{' '.join(command)} superó el tiempo límite.") from exc
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or "").strip()
            raise CommandError(f"{' '.join(command)} falló: {detail}") from exc
        return completed.stdout


class AsusCtl:
    """Operaciones de asusctl usadas por la aplicación."""

    def __init__(self, run: CommandRunner) -> None:
        self._run = run

    def get_profile(self) -> Profile:
        return parse_active_profile(self._run(["profile", "get"]))

    def set_profile(self, profile: Profile) -> None:
        # Sin -a/-b: asusd conserva sus perfiles de corriente y batería.
        self._run(["profile", "set", profile.value])

    def get_fan_curves(self, profile: Profile) -> dict[Fan, FanCurve]:
        return parse_fan_curves(self._run(["fan-curve", "--mod-profile", profile.value]))

    def set_fan_curve(self, profile: Profile, fan: Fan, data: str) -> None:
        fan_name = fan.value.lower()
        self._run(["fan-curve", "--mod-profile", profile.value, "--fan", fan_name, "--data", data])

    def enable_fan_curves(self, profile: Profile, enabled: bool) -> None:
        self._run(
            ["fan-curve", "--mod-profile", profile.value, "--enable-fan-curves", _flag(enabled)]
        )

    def get_brightness(self) -> Brightness:
        return parse_brightness(self._run(["leds", "get"]))

    def set_brightness(self, level: Brightness) -> None:
        self._run(["leds", "set", level.argument])

    def get_charge_limit(self) -> int:
        return parse_charge_limit(self._run(["battery", "info"]))

    def set_charge_limit(self, percent: int) -> None:
        self._run(["battery", "limit", str(percent)])

    def set_lightbar_power(self, state: LightbarState) -> None:
        flags = {
            "--boot": state.boot,
            "--awake": state.awake,
            "--sleep": state.sleep,
            "--shutdown": state.shutdown,
        }
        self._run(["aura", "power", "lightbar", *(flag for flag, on in flags.items() if on)])


class AuraBus:
    """Lecturas de la interfaz Aura de asusd por D-Bus (solo lectura)."""

    def __init__(self, run: CommandRunner) -> None:
        self._run = run

    def get_lightbar(self) -> LightbarState | None:
        """Estado de la cinta, o ``None`` si asusd no la admite en este equipo."""
        path = parse_aura_object_path(self._run(["--system", "--list", "tree", _ASUSD_SERVICE]))
        zones = parse_power_zones(self._get_property(path, "SupportedPowerZones"))
        if LIGHTBAR_POWER_ZONE not in zones:
            return None
        return parse_lightbar_power(self._get_property(path, "LedPower"))

    def _get_property(self, path: str, name: str) -> str:
        target = [_ASUSD_SERVICE, path, _AURA_INTERFACE, name]
        return self._run(["--system", "--json=short", "get-property", *target])


def _flag(enabled: bool) -> str:
    return "true" if enabled else "false"
