from __future__ import annotations

import pytest

from asus_control.errors import ParseError
from asus_control.models import Brightness, Fan, LightbarState, Profile
from asus_control.parsing import (
    parse_active_profile,
    parse_aura_object_path,
    parse_brightness,
    parse_charge_limit,
    parse_fan_curves,
    parse_lightbar_power,
    parse_power_zones,
)
from tests.conftest import fixture_text


def test_parses_active_profile_from_real_output() -> None:
    assert parse_active_profile(fixture_text("profile_balanced.txt")) is Profile.BALANCED


def test_ignores_ac_and_battery_profile_lines() -> None:
    text = "Active profile: Performance\n\nAC profile Balanced\nBattery profile Quiet\n"
    assert parse_active_profile(text) is Profile.PERFORMANCE


@pytest.mark.parametrize("text", ["", "Active profile: Turbo\n"])
def test_rejects_missing_or_unknown_profile(text: str) -> None:
    with pytest.raises(ParseError):
        parse_active_profile(text)


def test_parses_three_fan_curves_from_real_output() -> None:
    curves = parse_fan_curves(fixture_text("fan_curves_disabled.txt"))

    assert set(curves) == set(Fan)
    assert curves[Fan.CPU].temps == (40, 55, 64, 68, 71, 74, 77, 80)
    assert curves[Fan.MID].pwm == (255,) * 8
    assert not any(curve.enabled for curve in curves.values())


def test_rejects_incomplete_fan_curves() -> None:
    text = "fan: CPU, pwm: (1, 2), temp: (40, 50), enabled: true,"
    with pytest.raises(ParseError):
        parse_fan_curves(text)


def test_parses_brightness_and_charge_limit() -> None:
    assert parse_brightness(fixture_text("leds_get.txt")) is Brightness.HIGH
    assert parse_brightness("Current keyboard led brightness: Med\n") is Brightness.MEDIUM
    assert parse_charge_limit(fixture_text("battery_info.txt")) == 60


def test_finds_aura_device_in_bus_tree() -> None:
    assert parse_aura_object_path(fixture_text("busctl_tree.txt")) == "/xyz/ljones/aura/19b6_2_4"


def test_generic_config_exposes_only_keyboard_zone() -> None:
    assert parse_power_zones(fixture_text("aura_zones_keyboard_only.json")) == {1}
    assert parse_lightbar_power(fixture_text("aura_led_power_keyboard_only.json")) is None


def test_reads_lightbar_power_states() -> None:
    payload = '{"type":"(a(ubbbb))","data":[[[1,true,true,true,true],[2,false,true,false,false]]]}'
    assert parse_lightbar_power(payload) == LightbarState(
        boot=False, awake=True, sleep=False, shutdown=False
    )


@pytest.mark.parametrize("payload", ["no json", '{"type":"au"}', '{"data":[[1]]}'])
def test_rejects_malformed_bus_payloads(payload: str) -> None:
    with pytest.raises(ParseError):
        parse_lightbar_power(payload)
