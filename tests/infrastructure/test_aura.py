from __future__ import annotations

from collections.abc import Sequence

import pytest

from asus_control.domain.models import LightbarState
from asus_control.infrastructure.aura import (
    AsusdLightbar,
    parse_aura_object_path,
    parse_lightbar_power,
    parse_power_zones,
)
from asus_control.infrastructure.errors import ParseError
from tests.conftest import FakeRunner, fixture_text

BOTH_ZONES = '{"type":"au","data":[1,2]}'
LIGHTBAR_ON = '{"type":"(a(ubbbb))","data":[[[1,true,true,true,true],[2,true,true,false,false]]]}'


def bus(zones: str, power: str) -> FakeRunner:
    def handler(args: Sequence[str]) -> str:
        if "tree" in args:
            return fixture_text("busctl_tree.txt")
        return zones if args[-1] == "SupportedPowerZones" else power

    return FakeRunner(handler)


def test_finds_aura_device_in_bus_tree() -> None:
    assert parse_aura_object_path(fixture_text("busctl_tree.txt")) == "/xyz/ljones/aura/19b6_2_4"


def test_generic_config_exposes_only_keyboard_zone() -> None:
    assert parse_power_zones(fixture_text("aura_zones_keyboard_only.json")) == {1}
    assert parse_lightbar_power(fixture_text("aura_led_power_keyboard_only.json")) is None


@pytest.mark.parametrize("payload", ["no json", '{"type":"au"}', '{"data":[[1]]}'])
def test_rejects_malformed_bus_payloads(payload: str) -> None:
    with pytest.raises(ParseError):
        parse_lightbar_power(payload)


def test_reports_missing_lightbar_support() -> None:
    lightbar = AsusdLightbar(
        bus(
            fixture_text("aura_zones_keyboard_only.json"),
            fixture_text("aura_led_power_keyboard_only.json"),
        ),
        FakeRunner(),
    )

    assert lightbar.read() is None


def test_reads_lightbar_when_supported() -> None:
    lightbar = AsusdLightbar(bus(BOTH_ZONES, LIGHTBAR_ON), FakeRunner())

    assert lightbar.read() == LightbarState(boot=True, awake=True, sleep=False, shutdown=False)


def test_writes_only_enabled_power_states(fake_runner: FakeRunner) -> None:
    AsusdLightbar(FakeRunner(), fake_runner).write(
        LightbarState(boot=True, awake=False, sleep=False, shutdown=True)
    )

    assert fake_runner.calls == [["aura", "power", "lightbar", "--boot", "--shutdown"]]
