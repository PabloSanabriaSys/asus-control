from __future__ import annotations

import pytest

from asus_control.application.fan_service import FanService
from asus_control.domain.fan_modes import TEMPS, target_curves
from asus_control.domain.models import Brightness, Fan, FanCurve, FanMode, Profile
from asus_control.infrastructure.asusctl import AsusCtl
from tests.conftest import FakeRunner
from tests.fakes import no_lock
from tests.infrastructure.fake_asusd import FakeAsusd


def test_set_profile_does_not_touch_ac_or_battery_defaults(fake_runner: FakeRunner) -> None:
    AsusCtl(fake_runner).set_profile(Profile.PERFORMANCE)
    assert fake_runner.calls == [["profile", "set", "Performance"]]


def test_fan_curve_arguments_match_alternar_ventilacion(fake_runner: FakeRunner) -> None:
    asusctl = AsusCtl(fake_runner)

    asusctl.set_fan_curve(Profile.BALANCED, FanCurve(Fan.MID, (26, 51), (40, 55), enabled=True))
    asusctl.enable_fan_curves(Profile.BALANCED, False)

    assert fake_runner.calls == [
        ["fan-curve", "--mod-profile", "Balanced", "--fan", "mid", "--data", "40c:26,55c:51"],
        ["fan-curve", "--mod-profile", "Balanced", "--enable-fan-curves", "false"],
    ]


def test_brightness_and_charge_limit_arguments(fake_runner: FakeRunner) -> None:
    asusctl = AsusCtl(fake_runner)

    asusctl.set_brightness(Brightness.MEDIUM)
    asusctl.set_charge_limit(80)

    assert fake_runner.calls == [["leds", "set", "med"], ["battery", "limit", "80"]]


@pytest.mark.parametrize("mode", list(FanMode))
def test_fan_modes_round_trip_through_asusctl_format(mode: FanMode) -> None:
    """Integración: lo que escribe el adaptador, asusctl lo devuelve y se reconoce."""
    asusd = FakeAsusd()
    service = FanService(AsusCtl(asusd), no_lock)

    service.apply(mode)

    assert service.read_status().mode is mode
    stored = asusd.curves["CPU"]
    if mode is not FanMode.NORMAL:
        assert (stored.temps, stored.pwm) == (TEMPS, target_curves(mode)[0].pwm)
