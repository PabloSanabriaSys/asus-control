"""Formato de texto de asusctl 6.5.0: interpretación de salidas y argumentos."""

from __future__ import annotations

import re

from asus_control.domain.models import Brightness, Fan, FanCurve, Profile
from asus_control.infrastructure.errors import ParseError

_ACTIVE_PROFILE = re.compile(r"^Active profile:\s*(\w+)\s*$", re.MULTILINE)
_FAN_CURVE = re.compile(
    r"fan:\s*(CPU|GPU|MID),\s*pwm:\s*\(([^)]+)\),\s*temp:\s*\(([^)]+)\),\s*enabled:\s*(true|false)"
)
_BRIGHTNESS = re.compile(r"^Current keyboard led brightness:\s*(\w+)\s*$", re.MULTILINE)
_CHARGE_LIMIT = re.compile(r"^Current battery charge limit:\s*(\d+)%\s*$", re.MULTILINE)

BRIGHTNESS_ARGUMENTS = {
    Brightness.OFF: "off",
    Brightness.LOW: "low",
    Brightness.MEDIUM: "med",
    Brightness.HIGH: "high",
}
"""Argumento de ``asusctl leds set``; ``leds get`` imprime el mismo nombre capitalizado."""


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
    reported = match.group(1).lower()
    for level, argument in BRIGHTNESS_ARGUMENTS.items():
        if argument == reported:
            return level
    raise ParseError(f"Brillo desconocido: {match.group(1)}")


def parse_charge_limit(text: str) -> int:
    match = _CHARGE_LIMIT.search(text)
    if match is None:
        raise ParseError("No se encontró el límite de carga.")
    return int(match.group(1))


def format_curve_data(curve: FanCurve) -> str:
    """Argumento ``--data``: ``40c:51,55c:71,...`` (PWM 0-255, sin ``%``)."""
    points = zip(curve.temps, curve.pwm, strict=True)
    return ",".join(f"{temp}c:{pwm}" for temp, pwm in points)


def _int_tuple(values: str) -> tuple[int, ...]:
    try:
        return tuple(int(value) for value in values.split(","))
    except ValueError as exc:
        raise ParseError(f"Valores no numéricos: {values}") from exc
