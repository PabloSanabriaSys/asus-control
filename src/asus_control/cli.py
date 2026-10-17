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
from typing import Any

from asus_control.commands import ASUSCTL, BUSCTL, AsusCtl, AuraBus, SubprocessRunner
from asus_control.errors import AsusControlError
from asus_control.fan_lock import default_lock_path, fan_lock
from asus_control.fans import FanService
from asus_control.hardware import HardwareService
from asus_control.models import Brightness, ChargeLimit, FanMode, Profile
from asus_control.sensors import SysfsSensors
from asus_control.serialization import state_to_json

logger = logging.getLogger(__name__)

_ON_OFF = {"on": True, "off": False}
_BRIGHTNESS = {level.argument: level for level in Brightness}


def build_service() -> HardwareService:
    asusctl = AsusCtl(SubprocessRunner(ASUSCTL))
    lock_path = default_lock_path()
    return HardwareService(
        asusctl,
        AuraBus(SubprocessRunner(BUSCTL)),
        FanService(asusctl, lambda: fan_lock(lock_path)),
        SysfsSensors(),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="asus-control", description="Controles de hardware ASUS (salida JSON)."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("state", help="estado completo")
    commands.add_parser("profile", help="solo el perfil activo")

    setter = commands.add_parser("set", help="cambia un ajuste y confirma el resultado")
    targets = setter.add_subparsers(dest="target", required=True)
    targets.add_parser("profile").add_argument("value", choices=[p.value for p in Profile])
    targets.add_parser("fan").add_argument("value", choices=[m.value for m in FanMode])
    targets.add_parser("brightness").add_argument("value", choices=list(_BRIGHTNESS))
    targets.add_parser("charge-limit").add_argument(
        "value", type=int, choices=[int(limit) for limit in ChargeLimit]
    )
    targets.add_parser("lightbar").add_argument("value", choices=list(_ON_OFF))
    return parser


def run(argv: Sequence[str], service: HardwareService) -> dict[str, Any]:
    """Ejecuta la orden y devuelve la respuesta JSON (sin imprimirla)."""
    args = build_parser().parse_args(argv)
    if args.command == "profile":
        profile = service.read_profile()
        return _response(True, None, {"profile": profile.value if profile else None})
    if args.command == "state":
        return _response(True, None, state_to_json(service.read_state()))

    action, success = _action(service, args.target, args.value)
    try:
        action()
    except AsusControlError as exc:
        return _response(False, str(exc), state_to_json(service.read_state()))
    return _response(True, success, state_to_json(service.read_state()))


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    try:
        response = run(sys.argv[1:] if argv is None else argv, build_service())
    except Exception:
        logger.exception("Error inesperado")
        return 1
    print(json.dumps(response, ensure_ascii=False))
    return 0


def _action(service: HardwareService, target: str, value: str) -> tuple[Callable[[], None], str]:
    if target == "profile":
        profile = Profile(value)
        return lambda: service.set_profile(profile), f"Perfil {profile} activo."
    if target == "fan":
        mode = FanMode(value)
        return lambda: service.set_fan_mode(mode), f"Ventilación {mode} activa."
    if target == "brightness":
        level = _BRIGHTNESS[value]
        return lambda: service.set_brightness(level), f"Iluminación: {level.label}."
    if target == "charge-limit":
        limit = int(value)
        return lambda: service.set_charge_limit(limit), f"Límite de carga: {limit} %."
    on = _ON_OFF[value]
    return lambda: service.set_lightbar(on), f"Cinta LED {'encendida' if on else 'apagada'}."


def _response(ok: bool, message: str | None, state: dict[str, Any]) -> dict[str, Any]:
    return {"ok": ok, "message": message, "state": state}
