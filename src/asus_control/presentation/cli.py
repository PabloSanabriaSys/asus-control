"""Línea de órdenes que usa el applet de Plasma.

Cada invocación imprime una sola línea JSON: ``{"ok", "error", "state"}``.
Los errores esperados devuelven ``ok: false`` y un ``error`` con código estable;
los no previstos, código de salida 1. No hay textos para el usuario: los traduce el applet.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections.abc import Callable, Sequence
from contextlib import nullcontext
from dataclasses import dataclass

from asus_control.application.hardware_service import HardwareService
from asus_control.application.power_saving_service import PowerSavingService
from asus_control.domain.errors import AsusControlError
from asus_control.domain.models import Brightness, ChargeLimit, FanMode, Profile, Setting
from asus_control.presentation.serialization import JsonObject, error_to_json, state_to_json

logger = logging.getLogger(__name__)

_SWITCH = {"on": True, "off": False}


@dataclass(frozen=True)
class _SettingCommand:
    """Valores aceptados y acción de ``asus-control set <ajuste> <valor>``."""

    choices: Sequence[str]
    apply: Callable[[HardwareService, str], None]


_SETTINGS: dict[Setting, _SettingCommand] = {
    Setting.PROFILE: _SettingCommand(
        choices=[profile.value for profile in Profile],
        apply=lambda service, value: service.set_profile(Profile(value)),
    ),
    Setting.FAN_MODE: _SettingCommand(
        choices=[mode.value for mode in FanMode],
        apply=lambda service, value: service.set_fan_mode(FanMode(value)),
    ),
    Setting.BRIGHTNESS: _SettingCommand(
        choices=[level.value for level in Brightness],
        apply=lambda service, value: service.set_brightness(Brightness(value)),
    ),
    Setting.CHARGE_LIMIT: _SettingCommand(
        choices=[str(limit.value) for limit in ChargeLimit],
        apply=lambda service, value: service.set_charge_limit(int(value)),
    ),
    Setting.LIGHTBAR: _SettingCommand(
        choices=list(_SWITCH),
        apply=lambda service, value: service.set_lightbar(_SWITCH[value]),
    ),
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="asus-control", description="ASUS hardware controls (JSON output)."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("state", help="full hardware state")
    commands.add_parser("profile", help="active profile only")
    saving = commands.add_parser("power-saving", help="reversible maximum battery saving")
    saving.add_argument("action", choices=["on", "off", "reconcile", "watch"])
    saving.add_argument(
        "--brightness",
        type=int,
        choices=range(1, 101),
        default=30,
        metavar="1-100",
        help="internal panel brightness ceiling (default: 30)",
    )
    setter = commands.add_parser("set", help="change a setting and confirm it")
    targets = setter.add_subparsers(dest="setting", required=True)
    for setting, command in _SETTINGS.items():
        targets.add_parser(setting.value).add_argument("value", choices=command.choices)
    return parser


def run(
    argv: Sequence[str], service: HardwareService, saving: PowerSavingService | None = None
) -> JsonObject:
    """Ejecuta la orden y devuelve la respuesta (sin imprimirla)."""
    args = build_parser().parse_args(argv)
    if args.command == "profile":
        profile = service.read_profile()
        return _response({"profile": profile.value if profile else None})
    try:
        if args.command == "power-saving":
            if saving is None:
                raise AsusControlError("Battery saving is not configured")
            if args.action == "reconcile":
                saving.reconcile()
            elif args.action == "watch":
                raise AsusControlError("The watcher must be started through the installed launcher")
            else:
                saving.set_enabled(args.action == "on", args.brightness)
        elif args.command == "set":
            with saving.manual_control() if saving else nullcontext():
                _SETTINGS[Setting(args.setting)].apply(service, args.value)
    except AsusControlError as error:
        return _response(_state(service, saving), error=error_to_json(error))
    return _response(_state(service, saving))


def _state(service: HardwareService, saving: PowerSavingService | None) -> JsonObject:
    state = state_to_json(service.read_state())
    if saving is not None:
        try:
            session = saving.status()
        except AsusControlError as exc:
            state["powerSaving"] = {
                "available": False,
                "enabled": False,
                "restoring": False,
                "errors": [str(exc)],
            }
        else:
            state["powerSaving"] = {
                "available": True,
                "enabled": session.enabled if session else False,
                "restoring": session is not None and not session.enabled,
                "pending": list(session.pending) if session else [],
                "unavailable": list(session.unavailable) if session else [],
                "settings": [item.key for item in session.settings] if session else [],
                "errors": list(session.errors) if session else [],
            }
    return state


def main(
    argv: Sequence[str],
    build_service: Callable[[], HardwareService],
    saving: PowerSavingService | None = None,
) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    try:
        response = run(argv, build_service(), saving)
    except Exception:
        logger.exception("Unexpected error")
        return 1
    sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
    return 0


def _response(state: JsonObject, error: JsonObject | None = None) -> JsonObject:
    return {"ok": error is None, "error": error, "state": state}
