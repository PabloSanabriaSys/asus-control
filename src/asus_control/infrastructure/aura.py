"""Adaptador de ``LightbarPort``: lee de D-Bus de asusd (busctl) y escribe con asusctl.

El soporte real se toma de ``SupportedPowerZones``: si asusd no publica la zona
Lightbar, la cinta se considera no disponible.
"""

from __future__ import annotations

import json

from asus_control.domain.models import LightbarState
from asus_control.infrastructure.errors import ParseError
from asus_control.infrastructure.process import CommandRunner

LIGHTBAR_POWER_ZONE = 2
"""Valor de ``PowerZones::Lightbar`` en la interfaz D-Bus ``xyz.ljones.Aura``."""

_ASUSD_SERVICE = "xyz.ljones.Asusd"
_AURA_INTERFACE = "xyz.ljones.Aura"
_AURA_PATH_PREFIX = "/xyz/ljones/aura/"


class AsusdLightbar:
    """Cinta LED vía asusd. ``busctl`` y ``asusctl`` se inyectan como ejecutores."""

    def __init__(self, busctl: CommandRunner, asusctl: CommandRunner) -> None:
        self._busctl = busctl
        self._asusctl = asusctl

    def read(self) -> LightbarState | None:
        path = parse_aura_object_path(self._busctl(["--system", "--list", "tree", _ASUSD_SERVICE]))
        zones = parse_power_zones(self._property(path, "SupportedPowerZones"))
        if LIGHTBAR_POWER_ZONE not in zones:
            return None
        return parse_lightbar_power(self._property(path, "LedPower"))

    def write(self, state: LightbarState) -> None:
        flags = {
            "--boot": state.boot,
            "--awake": state.awake,
            "--sleep": state.sleep,
            "--shutdown": state.shutdown,
        }
        self._asusctl(["aura", "power", "lightbar", *(flag for flag, on in flags.items() if on)])

    def _property(self, path: str, name: str) -> str:
        target = [_ASUSD_SERVICE, path, _AURA_INTERFACE, name]
        return self._busctl(["--system", "--json=short", "get-property", *target])


def parse_aura_object_path(tree: str) -> str:
    """Primer dispositivo Aura de ``busctl --list tree``."""
    for line in tree.splitlines():
        path = line.strip()
        if path.startswith(_AURA_PATH_PREFIX):
            return path
    raise ParseError("asusd no expone ningún dispositivo Aura.")


def parse_power_zones(payload: str) -> frozenset[int]:
    data = _busctl_data(payload)
    if not isinstance(data, list) or not all(isinstance(zone, int) for zone in data):
        raise ParseError("Formato inesperado de SupportedPowerZones.")
    return frozenset(data)


def parse_lightbar_power(payload: str) -> LightbarState | None:
    """Estados de la cinta en ``LedPower``; ``None`` si no aparece."""
    data = _busctl_data(payload)
    if not isinstance(data, list) or len(data) != 1 or not isinstance(data[0], list):
        raise ParseError("Formato inesperado de LedPower.")
    try:
        for zone, boot, awake, sleep, shutdown in data[0]:
            if zone == LIGHTBAR_POWER_ZONE:
                return LightbarState(
                    boot=bool(boot), awake=bool(awake), sleep=bool(sleep), shutdown=bool(shutdown)
                )
    except (TypeError, ValueError) as exc:
        raise ParseError("Formato inesperado de LedPower.") from exc
    return None


def _busctl_data(payload: str) -> object:
    try:
        return json.loads(payload)["data"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ParseError("Respuesta JSON de busctl no válida.") from exc
