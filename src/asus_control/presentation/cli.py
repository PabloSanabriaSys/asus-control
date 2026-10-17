"""Línea de órdenes que usa el applet de Plasma.

Cada invocación imprime una sola línea JSON: ``{"ok", "message", "state"}``.
Los errores esperados devuelven ``ok: false``; los no previstos, código de salida 1.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from asus_control.application.hardware_service import HardwareService
from asus_control.domain.errors import AsusControlError
from asus_control.domain.models import Brightness, ChargeLimit, FanMode, Profile
from asus_control.presentation.labels import BRIGHTNESS_LABELS
from asus_control.presentation.serialization import JsonObject, state_to_json

logger = logging.getLogger(__name__)

_SWITCH = {"on": True, "off": False}


@dataclass(frozen=True)
class _Setting:
    """Un ajuste de ``asus-control set <nombre> <valor>``."""

    choices: Sequence[str]
    apply: Callable[[HardwareService, str], None]
    success: Callable[[str], str]


_SETTINGS: dict[str, _Setting] = {
    "profile": _Setting(
        choices=[profile.value for profile in Profile],
        apply=lambda service, value: service.set_profile(Profile(value)),
        success=lambda value: f"Perfil {value} activo.",
    ),
    "fan": _Setting(
        choices=[mode.value for mode in FanMode],
        apply=lambda service, value: service.set_fan_mode(FanMode(value)),
        success=lambda value: f"Ventilación {value} activa.",
    ),
    "brightness": _Setting(
        choices=[level.value for level in Brightness],
        apply=lambda service, value: service.set_brightness(Brightness(value)),
        success=lambda value: f"Iluminación: {BRIGHTNESS_LABELS[Brightness(value)]}.",
    ),
    "charge-limit": _Setting(
        choices=[str(limit.value) for limit in ChargeLimit],
        apply=lambda service, value: service.set_charge_limit(int(value)),
        success=lambda value: f"Límite de carga: {value} %.",
    ),
    "lightbar": _Setting(
        choices=list(_SWITCH),
        apply=lambda service, value: service.set_lightbar(_SWITCH[value]),
        success=lambda value: f"Cinta LED {'encendida' if _SWITCH[value] else 'apagada'}.",
    ),
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="asus-control", description="Controles de hardware ASUS (salida JSON)."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("state", help="estado completo")
    commands.add_parser("profile", help="solo el perfil activo")
    setter = commands.add_parser("set", help="cambia un ajuste y confirma el resultado")
    targets = setter.add_subparsers(dest="setting", required=True)
    for name, setting in _SETTINGS.items():
        targets.add_parser(name).add_argument("value", choices=setting.choices)
    return parser


def run(argv: Sequence[str], service: HardwareService) -> JsonObject:
    """Ejecuta la orden y devuelve la respuesta (sin imprimirla)."""
    args = build_parser().parse_args(argv)
    if args.command == "profile":
        profile = service.read_profile()
        return _response(True, None, {"profile": profile.value if profile else None})
    if args.command == "state":
        return _response(True, None, state_to_json(service.read_state()))

    setting = _SETTINGS[args.setting]
    try:
        setting.apply(service, args.value)
    except AsusControlError as exc:
        return _response(False, str(exc), state_to_json(service.read_state()))
    return _response(True, setting.success(args.value), state_to_json(service.read_state()))


def main(argv: Sequence[str], build_service: Callable[[], HardwareService]) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    try:
        response = run(argv, build_service())
    except Exception:
        logger.exception("Error inesperado")
        return 1
    sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
    return 0


def _response(ok: bool, message: str | None, state: dict[str, Any]) -> JsonObject:
    return {"ok": ok, "message": message, "state": state}
