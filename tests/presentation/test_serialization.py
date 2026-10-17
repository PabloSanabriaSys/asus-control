from __future__ import annotations

from asus_control.domain.models import (
    BatteryStatus,
    Brightness,
    FanStatus,
    HardwareState,
    LightbarState,
    Profile,
    SensorReadings,
)
from asus_control.presentation.serialization import state_to_json


def test_serializes_complete_state() -> None:
    state = HardwareState(
        profile=Profile.QUIET,
        fans=FanStatus(mode=None),
        brightness=Brightness.MEDIUM,
        lightbar=LightbarState(boot=True, awake=False, sleep=False, shutdown=False),
        charge_limit=60,
        battery=BatteryStatus(percent=66, ac_online=False, charging_state="Discharging"),
        sensors=SensorReadings(cpu_package_temp=59.0, cpu_fan_rpm=2000),
    )

    assert state_to_json(state) == {
        "asusdAvailable": True,
        "profile": "Quiet",
        "fans": {"mode": None},
        "brightness": "medium",
        "lightbar": {"on": False},
        "chargeLimit": 60,
        "battery": {"percent": 66, "acOnline": False, "status": "Descargando"},
        "sensors": {"cpuTemp": 59.0, "cpuFan": 2000, "gpuFan": None, "midFan": None},
    }


def test_unavailable_state_serializes_to_nulls() -> None:
    data = state_to_json(HardwareState())

    assert data["asusdAvailable"] is False
    assert all(data[key] is None for key in ("profile", "fans", "lightbar", "battery"))


def test_unknown_charging_state_is_kept_verbatim() -> None:
    battery = BatteryStatus(percent=50, ac_online=None, charging_state="Unknown")

    assert state_to_json(HardwareState(battery=battery))["battery"]["status"] == "Unknown"
