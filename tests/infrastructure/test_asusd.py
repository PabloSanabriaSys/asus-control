from __future__ import annotations

import json

import pytest

from asus_control.application.fan_service import FanService
from asus_control.domain.fan_modes import target_curves
from asus_control.domain.models import Brightness, Fan, FanMode, LightbarState, Profile
from asus_control.infrastructure.asusd import (
    AsusdLightbar,
    AsusdPlatform,
    AuraDevice,
    parse_fan_curves,
    parse_lightbar_power,
)
from asus_control.infrastructure.busctl import Busctl
from asus_control.infrastructure.errors import ParseError
from tests.conftest import fixture_text
from tests.fakes import no_lock
from tests.infrastructure.fake_asusd_bus import FakeAsusdBus


def adapters(fake: FakeAsusdBus) -> tuple[AsusdPlatform, AsusdLightbar]:
    bus = Busctl(fake, "xyz.ljones.Asusd")
    aura = AuraDevice(bus)
    return AsusdPlatform(bus, aura), AsusdLightbar(bus, aura)


def fixture_data(name: str) -> object:
    return json.loads(fixture_text(name))["data"]


def test_real_replies_decode_as_expected() -> None:
    curves = parse_fan_curves(fixture_data("dbus_fan_curves_extra.json"))

    assert {curve.fan for curve in curves.values()} == set(Fan)
    assert all(curve.enabled for curve in curves.values())
    assert curves[Fan.MID].pwm == (26, 51, 77, 97, 115, 128, 140, 153)
    assert parse_lightbar_power(fixture_data("dbus_led_power_lightbar.json")) == LightbarState(
        boot=True, awake=True, sleep=False, shutdown=False
    )


@pytest.mark.parametrize(
    ("code", "profile"), [(0, Profile.BALANCED), (1, Profile.PERFORMANCE), (2, Profile.QUIET)]
)
def test_profile_codes(code: int, profile: Profile) -> None:
    fake = FakeAsusdBus(profile=code)
    platform, _ = adapters(fake)

    assert platform.get_profile() is profile
    platform.set_profile(Profile.QUIET)
    assert fake.profile == 2


def test_profile_change_does_not_touch_ac_or_battery_defaults() -> None:
    fake = FakeAsusdBus()

    adapters(fake)[0].set_profile(Profile.PERFORMANCE)

    written = [call[4] for call in fake.calls if call[0] == "set-property"]
    assert written == ["PlatformProfile"]


def test_brightness_and_charge_limit_round_trip() -> None:
    fake = FakeAsusdBus()
    platform, _ = adapters(fake)

    platform.set_brightness(Brightness.MEDIUM)
    platform.set_charge_limit(80)

    assert (platform.get_brightness(), platform.get_charge_limit()) == (Brightness.MEDIUM, 80)
    assert fake.brightness == 2


def test_unknown_codes_are_parse_errors() -> None:
    with pytest.raises(ParseError):
        adapters(FakeAsusdBus(profile=7))[0].get_profile()


def test_fan_curve_is_sent_with_dbus_signature() -> None:
    fake = FakeAsusdBus()
    curve = target_curves(FanMode.EXTRA)[2]

    adapters(fake)[0].set_fan_curve(Profile.BALANCED, curve)

    call = fake.calls[-1]
    assert call[4:7] == ["SetFanCurve", "u(s(yyyyyyyy)(yyyyyyyy)b)", "0"]
    assert call[7:] == ["MID", *map(str, curve.pwm), *map(str, curve.temps), "true"]


@pytest.mark.parametrize("mode", list(FanMode))
def test_fan_modes_round_trip_through_dbus(mode: FanMode) -> None:
    """Integración: lo que escribe el adaptador, asusd lo devuelve y se reconoce."""
    platform, _ = adapters(FakeAsusdBus())
    service = FanService(platform, no_lock)

    service.apply(mode)

    assert service.read_status().mode is mode


def test_lightbar_write_preserves_keyboard_zone() -> None:
    fake = FakeAsusdBus()
    _, lightbar = adapters(fake)

    lightbar.write(LightbarState(boot=True, awake=True, sleep=False, shutdown=False))

    assert fake.led_power == [[1, True, True, True, True], [2, True, True, False, False]]
    assert lightbar.read() == LightbarState(boot=True, awake=True, sleep=False, shutdown=False)


def test_lightbar_unavailable_without_zone_support() -> None:
    assert adapters(FakeAsusdBus(power_zones=[1]))[1].read() is None


def test_aura_path_is_resolved_once() -> None:
    fake = FakeAsusdBus()
    platform, lightbar = adapters(fake)

    platform.get_brightness()
    lightbar.read()

    assert sum(call[:2] == ["--list", "tree"] for call in fake.calls) == 1
