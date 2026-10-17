"""Conversión del estado y de los errores al JSON que consume el applet de Plasma.

No contiene textos para el usuario: el applet traduce los valores y los códigos.
"""

from __future__ import annotations

from typing import Any

from asus_control.domain.errors import (
    AsusControlError,
    FanModeError,
    FanModeRequiresBalancedError,
    HardwareAccessError,
    LightbarUnsupportedError,
    LockBusyError,
    VerificationError,
)
from asus_control.domain.models import BatteryStatus, FanStatus, HardwareState, SensorReadings

JsonObject = dict[str, Any]


def state_to_json(state: HardwareState) -> JsonObject:
    """Serializa el estado; ``null`` en cualquier campo significa «No disponible»."""
    return {
        "asusdAvailable": state.asusd_available,
        "profile": state.profile.value if state.profile else None,
        "fans": _fans(state.fans),
        "brightness": state.brightness.value if state.brightness else None,
        "lightbar": None if state.lightbar is None else {"on": state.lightbar.awake},
        "chargeLimit": state.charge_limit,
        "battery": _battery(state.battery),
        "sensors": _sensors(state.sensors),
    }


def _fans(fans: FanStatus | None) -> JsonObject | None:
    if fans is None:
        return None
    # ``mode`` nulo: curvas activas que no corresponden a ningún modo conocido.
    return {"mode": fans.mode.value if fans.mode else None}


def _battery(battery: BatteryStatus | None) -> JsonObject | None:
    if battery is None:
        return None
    return {
        "percent": battery.percent,
        "acOnline": battery.ac_online,
        # Valor de sysfs sin traducir: Charging, Discharging, Not charging, Full…
        "status": battery.charging_state,
    }


def _sensors(sensors: SensorReadings) -> JsonObject:
    return {
        "cpuTemp": sensors.cpu_package_temp,
        "cpuFan": sensors.cpu_fan_rpm,
        "gpuFan": sensors.gpu_fan_rpm,
        "midFan": sensors.mid_fan_rpm,
    }


def error_to_json(error: AsusControlError) -> JsonObject:
    """Código estable y datos del error; el applet compone el mensaje traducido."""
    details: JsonObject
    match error:
        case FanModeRequiresBalancedError():
            details = {"code": "fanRequiresBalanced"}
        case FanModeError(mode=mode, restored=restored):
            details = {"code": "fanModeFailed", "mode": mode.value, "restored": restored}
        case LockBusyError():
            details = {"code": "fanChangeInProgress"}
        case LightbarUnsupportedError():
            details = {"code": "lightbarUnsupported"}
        case VerificationError(setting=setting):
            details = {"code": "notConfirmed", "setting": setting.value}
        case HardwareAccessError():
            details = {"code": "hardwareAccess", "detail": str(error)}
        case _:
            details = {"code": "unknown", "detail": str(error)}
    return details
