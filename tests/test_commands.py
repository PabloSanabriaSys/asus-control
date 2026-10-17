from __future__ import annotations

from collections.abc import Sequence

import pytest

from asus_control.commands import AsusCtl, AuraBus, SubprocessRunner
from asus_control.errors import CommandError
from asus_control.models import Brightness, Fan, LightbarState, Profile
from tests.conftest import FakeRunner, fixture_text


def test_set_profile_does_not_touch_ac_or_battery_defaults(fake_runner: FakeRunner) -> None:
    AsusCtl(fake_runner).set_profile(Profile.PERFORMANCE)
    assert fake_runner.calls == [["profile", "set", "Performance"]]


def test_fan_curve_commands_match_alternar_ventilacion(fake_runner: FakeRunner) -> None:
    asusctl = AsusCtl(fake_runner)

    asusctl.set_fan_curve(Profile.BALANCED, Fan.MID, "40c:26,55c:51")
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


def test_lightbar_keeps_other_power_states(fake_runner: FakeRunner) -> None:
    AsusCtl(fake_runner).set_lightbar_power(
        LightbarState(boot=True, awake=False, sleep=False, shutdown=True)
    )
    assert fake_runner.calls == [["aura", "power", "lightbar", "--boot", "--shutdown"]]


def test_aura_bus_reports_missing_lightbar_support() -> None:
    def handler(args: Sequence[str]) -> str:
        if "tree" in args:
            return fixture_text("busctl_tree.txt")
        if args[-1] == "SupportedPowerZones":
            return fixture_text("aura_zones_keyboard_only.json")
        return fixture_text("aura_led_power_keyboard_only.json")

    assert AuraBus(FakeRunner(handler)).get_lightbar() is None


def test_aura_bus_reads_lightbar_when_supported() -> None:
    def handler(args: Sequence[str]) -> str:
        if "tree" in args:
            return fixture_text("busctl_tree.txt")
        if args[-1] == "SupportedPowerZones":
            return '{"type":"au","data":[1,2]}'
        return '{"type":"(a(ubbbb))","data":[[[1,true,true,true,true],[2,true,true,true,true]]]}'

    state = AuraBus(FakeRunner(handler)).get_lightbar()
    assert state is not None
    assert state.awake


def test_subprocess_runner_reports_failures() -> None:
    with pytest.raises(CommandError, match="falló"):
        SubprocessRunner("/usr/bin/false")([])
    with pytest.raises(CommandError, match="No se encontró"):
        SubprocessRunner("/nonexistent/asusctl")([])
    with pytest.raises(CommandError, match="tiempo límite"):
        SubprocessRunner("/usr/bin/sleep", timeout=0.1)(["5"])


def test_subprocess_runner_passes_arguments_without_shell() -> None:
    assert SubprocessRunner("/usr/bin/echo")(["a b", "$HOME"]) == "a b $HOME\n"
