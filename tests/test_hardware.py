from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path

import pytest

from asus_control.commands import AsusCtl, AuraBus
from asus_control.errors import CommandError, VerificationError
from asus_control.fans import FanService
from asus_control.hardware import HardwareService
from asus_control.models import Brightness, FanMode, LightbarState, Profile
from asus_control.sensors import SysfsSensors
from tests.conftest import FakeRunner, fixture_text
from tests.fake_asusd import FakeAsusd


@contextmanager
def no_lock() -> Iterator[None]:
    yield


class FakeAura:
    """Bus Aura con cinta LED soportada, cuyo estado cambia con ``aura power lightbar``."""

    def __init__(self) -> None:
        self.lightbar = LightbarState(boot=True, awake=False, sleep=True, shutdown=True)

    def __call__(self, args: Sequence[str]) -> str:
        if "tree" in args:
            return fixture_text("busctl_tree.txt")
        if args[-1] == "SupportedPowerZones":
            return '{"type":"au","data":[1,2]}'
        state = self.lightbar
        flags = [state.boot, state.awake, state.sleep, state.shutdown]
        entry = ",".join(str(flag).lower() for flag in flags)
        return f'{{"type":"(a(ubbbb))","data":[[[1,true,true,true,true],[2,{entry}]]]}}'

    def apply(self, args: Sequence[str]) -> None:
        self.lightbar = LightbarState(
            boot="--boot" in args,
            awake="--awake" in args,
            sleep="--sleep" in args,
            shutdown="--shutdown" in args,
        )


def make_service(
    asusd: FakeAsusd, aura: FakeAura | None = None, sysfs: Path = Path("/nonexistent")
) -> HardwareService:
    aura = aura or FakeAura()

    def asusctl(args: Sequence[str]) -> str:
        if list(args[:3]) == ["aura", "power", "lightbar"]:
            aura.apply(args)
            return ""
        return asusd(args)

    client = AsusCtl(asusctl)
    return HardwareService(client, AuraBus(aura), FanService(client, no_lock), SysfsSensors(sysfs))


def test_reads_complete_state_in_balanced() -> None:
    state = make_service(FakeAsusd()).read_state()

    assert state.asusd_available
    assert state.profile is Profile.BALANCED
    assert state.fans is not None
    assert state.fans.mode is FanMode.NORMAL
    assert state.brightness is Brightness.HIGH
    assert state.charge_limit == 60
    assert state.lightbar is not None


def test_fan_curves_are_not_read_outside_balanced() -> None:
    asusd = FakeAsusd(profile="Performance")

    state = make_service(asusd).read_state()

    assert state.fans is None
    assert not any(call[0] == "fan-curve" for call in asusd.calls)


def test_asusd_unavailable_skips_remaining_commands() -> None:
    asusd = FakeAsusd(fail_on={("profile",)})

    state = make_service(asusd).read_state()

    assert not state.asusd_available
    assert state.brightness is None
    assert asusd.calls == [["profile", "get"]]


def test_reading_never_writes_hardware() -> None:
    asusd = FakeAsusd()

    make_service(asusd).read_state()

    read_commands = [
        ["profile", "get"],
        ["fan-curve", "--mod-profile", "Balanced"],
        ["leds", "get"],
        ["battery", "info"],
    ]
    assert all(call in read_commands for call in asusd.calls)


def test_lightbar_is_unavailable_without_bus_support() -> None:
    def keyboard_only(args: Sequence[str]) -> str:
        if "tree" in args:
            return fixture_text("busctl_tree.txt")
        if args[-1] == "SupportedPowerZones":
            return fixture_text("aura_zones_keyboard_only.json")
        return fixture_text("aura_led_power_keyboard_only.json")

    asusd = FakeAsusd()
    client = AsusCtl(asusd)
    service = HardwareService(
        client,
        AuraBus(FakeRunner(keyboard_only)),
        FanService(client, no_lock),
        SysfsSensors(Path("/nonexistent")),
    )

    assert service.read_state().lightbar is None
    with pytest.raises(VerificationError):
        service.set_lightbar(True)


def test_changes_are_confirmed_by_reading_back() -> None:
    asusd = FakeAsusd()
    service = make_service(asusd)

    service.set_profile(Profile.QUIET)
    service.set_brightness(Brightness.LOW)
    service.set_charge_limit(80)

    assert (asusd.profile, asusd.brightness, asusd.charge_limit) == ("Quiet", "Low", 80)
    assert asusd.calls[-1] == ["battery", "info"]


@pytest.mark.parametrize(
    "action",
    [
        lambda service: service.set_profile(Profile.PERFORMANCE),
        lambda service: service.set_brightness(Brightness.OFF),
        lambda service: service.set_charge_limit(100),
    ],
)
def test_unconfirmed_change_is_an_error(action: Callable[[HardwareService], None]) -> None:
    service = make_service(FakeAsusd(ignore_writes=True))

    with pytest.raises(VerificationError):
        action(service)


def test_command_failure_propagates() -> None:
    service = make_service(FakeAsusd(fail_on={("leds", "set")}))

    with pytest.raises(CommandError):
        service.set_brightness(Brightness.OFF)


def test_lightbar_toggle_preserves_other_power_states() -> None:
    aura = FakeAura()
    service = make_service(FakeAsusd(), aura)

    service.set_lightbar(True)

    assert aura.lightbar == LightbarState(boot=True, awake=True, sleep=True, shutdown=True)
    service.set_lightbar(False)
    assert not aura.lightbar.awake
    assert aura.lightbar.boot
