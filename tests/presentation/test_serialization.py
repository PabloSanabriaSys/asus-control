from __future__ import annotations

import pytest

from asus_control.domain.errors import (
    AsusControlError,
    FanModeError,
    FanModeRequiresBalancedError,
    HardwareAccessError,
    LightbarUnsupportedError,
    LockBusyError,
    VerificationError,
)
from asus_control.domain.models import (
    BatteryStatus,
    Brightness,
    FanMode,
    FanStatus,
    HardwareState,
    LightbarState,
    Profile,
    SensorReadings,
    Setting,
)
from asus_control.presentation.serialization import error_to_json, state_to_json


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
        "battery": {"percent": 66, "acOnline": False, "status": "Discharging"},
        "sensors": {"cpuTemp": 59.0, "cpuFan": 2000, "gpuFan": None, "midFan": None},
    }


def test_unavailable_state_serializes_to_nulls() -> None:
    data = state_to_json(HardwareState())

    assert data["asusdAvailable"] is False
    assert all(data[key] is None for key in ("profile", "fans", "lightbar", "battery"))


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (FanModeRequiresBalancedError(), {"code": "fanRequiresBalanced"}),
        (
            FanModeError(FanMode.ULTRA, restored=False),
            {"code": "fanModeFailed", "mode": "Ultra", "restored": False},
        ),
        (LockBusyError(), {"code": "fanChangeInProgress"}),
        (LightbarUnsupportedError(), {"code": "lightbarUnsupported"}),
        (
            VerificationError(Setting.CHARGE_LIMIT),
            {"code": "notConfirmed", "setting": "charge-limit"},
        ),
        (
            HardwareAccessError("asusctl timed out"),
            {"code": "hardwareAccess", "detail": "asusctl timed out"},
        ),
    ],
)
def test_errors_become_stable_codes(error: AsusControlError, expected: dict[str, object]) -> None:
    assert error_to_json(error) == expected
