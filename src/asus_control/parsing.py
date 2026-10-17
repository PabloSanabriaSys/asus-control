"""Interpretación de las salidas de texto de asusctl y busctl."""

from __future__ import annotations

import json
import re

from asus_control.errors import ParseError
from asus_control.models import Brightness, Fan, FanCurve, LightbarState, Profile

_ACTIVE_PROFILE = re.compile(r"^Active profile:\s*(\w+)\s*$", re.MULTILINE)
_FAN_CURVE = re.compile(
    r"fan:\s*(CPU|GPU|MID),\s*pwm:\s*\(([^)]+)\),\s*temp:\s*\(([^)]+)\),\s*enabled:\s*(true|false)"
)
_BRIGHTNESS = re.compile(r"^Current keyboard led brightness:\s*(\w+)\s*$", re.MULTILINE)
_CHARGE_LIMIT = re.compile(r"^Current battery charge limit:\s*(\d+)%\s*$", re.MULTILINE)

LIGHTBAR_POWER_ZONE = 2
"""Valor de ``PowerZones::Lightbar`` en la interfaz D-Bus ``xyz.ljones.Aura``."""


def parse_active_profile(text: str) -> Profile:
    match = _ACTIVE_PROFILE.search(text)
    if match is None:
        raise ParseError("No se encontró el perfil activo.")
    try:
        return Profile(match.group(1))
    except ValueError as exc:
        raise ParseError(f"Perfil desconocido: {match.group(1)}") from exc


def parse_fan_curves(text: str) -> dict[Fan, FanCurve]:
    curves = {
        Fan(fan): FanCurve(
            fan=Fan(fan),
            pwm=_int_tuple(pwm),
            temps=_int_tuple(temps),
            enabled=enabled == "true",
        )
        for fan, pwm, temps, enabled in _FAN_CURVE.findall(text)
    }
    if set(curves) != set(Fan):
        raise ParseError("No se pudo leer el estado de los tres ventiladores.")
    return curves


def parse_brightness(text: str) -> Brightness:
    match = _BRIGHTNESS.search(text)
    if match is None:
        raise ParseError("No se encontró el brillo del teclado.")
    for level in Brightness:
        if level.reported == match.group(1):
            return level
    raise ParseError(f"Brillo desconocido: {match.group(1)}")


def parse_charge_limit(text: str) -> int:
    match = _CHARGE_LIMIT.search(text)
    if match is None:
        raise ParseError("No se encontró el límite de carga.")
    return int(match.group(1))


def parse_aura_object_path(tree: str) -> str:
    """Devuelve el primer dispositivo Aura de ``busctl --list tree``."""
    for line in tree.splitlines():
        path = line.strip()
        if path.startswith("/xyz/ljones/aura/"):
            return path
    raise ParseError("asusd no expone ningún dispositivo Aura.")


def parse_power_zones(payload: str) -> frozenset[int]:
    data = _busctl_data(payload)
    if not isinstance(data, list) or not all(isinstance(zone, int) for zone in data):
        raise ParseError("Formato inesperado de SupportedPowerZones.")
    return frozenset(data)


def parse_lightbar_power(payload: str) -> LightbarState | None:
    """Extrae los estados de la cinta de ``LedPower``; ``None`` si no aparece."""
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
        document = json.loads(payload)
        return document["data"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ParseError("Respuesta JSON de busctl no válida.") from exc


def _int_tuple(values: str) -> tuple[int, ...]:
    try:
        return tuple(int(value) for value in values.split(","))
    except ValueError as exc:
        raise ParseError(f"Valores no numéricos: {values}") from exc
