from __future__ import annotations

from collections.abc import Callable

import pytest

from asus_control.application.fan_service import FanService
from asus_control.application.hardware_service import HardwareService
from asus_control.domain.errors import (
    HardwareAccessError,
    LightbarUnsupportedError,
    VerificationError,
)
from asus_control.domain.models import (
    BatteryStatus,
    Brightness,
    FanMode,
    LightbarState,
    Profile,
    SensorReadings,
)
from tests.fakes import FakeLightbar, FakePlatform, FakeSensors, no_lock

READINGS = SensorReadings(cpu_package_temp=55.0, cpu_fan_rpm=2500)
BATTERY = BatteryStatus(percent=73, ac_online=True, charging_state="Not charging")


def make_service(
    platform: FakePlatform | None = None, lightbar: FakeLightbar | None = None
) -> HardwareService:
    platform = platform or FakePlatform()
    return HardwareService(
        platform=platform,
        lightbar=lightbar or FakeLightbar(),
        sensors=FakeSensors(READINGS, BATTERY),
        fans=FanService(platform, no_lock),
    )


def test_reads_complete_state_in_balanced() -> None:
    state = make_service().read_state()

    assert state.asusd_available
    assert state.profile is Profile.BALANCED
    assert state.fans is not None
    assert state.fans.mode is FanMode.NORMAL
    assert state.brightness is Brightness.HIGH
    assert state.charge_limit == 60
    assert state.lightbar is not None
    assert (state.sensors, state.battery) == (READINGS, BATTERY)


def test_fan_curves_are_not_read_outside_balanced() -> None:
    platform = FakePlatform(profile=Profile.PERFORMANCE)

    state = make_service(platform).read_state()

    assert state.fans is None
    assert "get_fan_curves" not in platform.calls


def test_asusd_unavailable_keeps_local_readings_and_skips_the_rest() -> None:
    platform = FakePlatform(failing={"get_profile"})

    state = make_service(platform).read_state()

    assert not state.asusd_available
    assert state.brightness is None
    assert state.sensors == READINGS
    assert platform.calls == ["get_profile"]


def test_single_failed_reading_is_unavailable() -> None:
    state = make_service(FakePlatform(failing={"get_brightness"})).read_state()

    assert state.brightness is None
    assert state.charge_limit == 60


def test_reading_never_writes_hardware() -> None:
    platform = FakePlatform()

    make_service(platform).read_state()

    assert all(call.startswith("get_") for call in platform.calls)


def test_changes_are_confirmed_by_reading_back() -> None:
    platform = FakePlatform()
    service = make_service(platform)

    service.set_profile(Profile.QUIET)
    service.set_brightness(Brightness.LOW)
    service.set_charge_limit(80)

    assert (platform.profile, platform.brightness, platform.charge_limit) == (
        Profile.QUIET,
        Brightness.LOW,
        80,
    )
    assert platform.calls[-1] == "get_charge_limit"


@pytest.mark.parametrize(
    "action",
    [
        lambda service: service.set_profile(Profile.PERFORMANCE),
        lambda service: service.set_brightness(Brightness.OFF),
        lambda service: service.set_charge_limit(100),
    ],
)
def test_unconfirmed_change_is_an_error(action: Callable[[HardwareService], None]) -> None:
    service = make_service(FakePlatform(ignore_writes=True))

    with pytest.raises(VerificationError) as error:
        action(service)
    assert error.value.setting.value in {"profile", "brightness", "charge-limit"}


def test_access_failure_propagates() -> None:
    service = make_service(FakePlatform(failing={"set_brightness"}))

    with pytest.raises(HardwareAccessError):
        service.set_brightness(Brightness.OFF)


def test_lightbar_toggle_preserves_other_power_states() -> None:
    lightbar = FakeLightbar()
    service = make_service(lightbar=lightbar)

    service.set_lightbar(True)

    assert lightbar.state == LightbarState(boot=True, awake=True, sleep=True, shutdown=True)
    service.set_lightbar(False)
    assert lightbar.state is not None
    assert not lightbar.state.awake
    assert lightbar.state.boot


def test_lightbar_without_support() -> None:
    service = make_service(lightbar=FakeLightbar(state=None))

    assert service.read_state().lightbar is None
    with pytest.raises(LightbarUnsupportedError):
        service.set_lightbar(True)
