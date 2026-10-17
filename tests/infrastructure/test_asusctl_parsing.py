from __future__ import annotations

import pytest

from asus_control.domain.models import Brightness, Fan, FanCurve, Profile
from asus_control.infrastructure.asusctl_parsing import (
    format_curve_data,
    parse_active_profile,
    parse_brightness,
    parse_charge_limit,
    parse_fan_curves,
)
from asus_control.infrastructure.errors import ParseError
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
    with pytest.raises(ParseError):
        parse_fan_curves("fan: CPU, pwm: (1, 2), temp: (40, 50), enabled: true,")


@pytest.mark.parametrize(
    ("reported", "level"),
    [("Off", Brightness.OFF), ("Low", Brightness.LOW), ("Med", Brightness.MEDIUM)],
)
def test_parses_brightness(reported: str, level: Brightness) -> None:
    assert parse_brightness(f"Current keyboard led brightness: {reported}\n") is level


def test_parses_real_brightness_and_charge_limit() -> None:
    assert parse_brightness(fixture_text("leds_get.txt")) is Brightness.HIGH
    assert parse_charge_limit(fixture_text("battery_info.txt")) == 60


def test_formats_curve_with_raw_pwm_values() -> None:
    curve = FanCurve(Fan.MID, (26, 51), (40, 55), enabled=True)
    assert format_curve_data(curve) == "40c:26,55c:51"
