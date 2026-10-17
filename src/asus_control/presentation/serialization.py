"""Conversión del estado del hardware al JSON que consume el applet de Plasma."""

from __future__ import annotations

from typing import Any

from asus_control.domain.models import BatteryStatus, FanStatus, HardwareState, SensorReadings
from asus_control.presentation.labels import CHARGING_STATE_LABELS

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
    status = battery.charging_state
    return {
        "percent": battery.percent,
        "acOnline": battery.ac_online,
        "status": CHARGING_STATE_LABELS.get(status, status) if status else None,
    }


def _sensors(sensors: SensorReadings) -> JsonObject:
    return {
        "cpuTemp": sensors.cpu_package_temp,
        "cpuFan": sensors.cpu_fan_rpm,
        "gpuFan": sensors.gpu_fan_rpm,
        "midFan": sensors.mid_fan_rpm,
    }
