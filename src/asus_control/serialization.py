"""Conversión del estado del hardware al JSON que consume el applet de Plasma."""

from __future__ import annotations

from typing import Any

from asus_control.models import BatteryStatus, HardwareState

_CHARGING_STATES = {
    "Charging": "Cargando",
    "Discharging": "Descargando",
    "Not charging": "Sin cargar",
    "Full": "Completa",
}

JsonObject = dict[str, Any]


def state_to_json(state: HardwareState) -> JsonObject:
    """Serializa el estado; ``None`` en cualquier campo significa «No disponible»."""
    sensors = state.sensors
    return {
        "asusdAvailable": state.asusd_available,
        "profile": state.profile.value if state.profile else None,
        "fans": None if state.fans is None else _fan_mode(state),
        "brightness": state.brightness.argument if state.brightness else None,
        "lightbar": None if state.lightbar is None else {"on": state.lightbar.awake},
        "chargeLimit": state.charge_limit,
        "battery": _battery(state.battery),
        "sensors": {
            "cpuTemp": sensors.cpu_package_temp,
            "cpuFan": sensors.cpu_fan_rpm,
            "gpuFan": sensors.gpu_fan_rpm,
            "midFan": sensors.mid_fan_rpm,
        },
    }


def _fan_mode(state: HardwareState) -> JsonObject:
    mode = state.fans.mode if state.fans else None
    # ``mode`` nulo con ``fans`` presente: curvas activas que no son de ningún modo conocido.
    return {"mode": mode.value if mode else None}


def _battery(battery: BatteryStatus | None) -> JsonObject | None:
    if battery is None:
        return None
    state = battery.charging_state
    return {
        "percent": battery.percent,
        "acOnline": battery.ac_online,
        "status": _CHARGING_STATES.get(state, state) if state else None,
    }
