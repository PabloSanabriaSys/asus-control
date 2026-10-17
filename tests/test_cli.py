from __future__ import annotations

import json
from collections.abc import Callable

import pytest

from asus_control.cli import main, run
from asus_control.models import (
    BatteryStatus,
    Brightness,
    FanMode,
    FanStatus,
    HardwareState,
    LightbarState,
    Profile,
    SensorReadings,
)
from asus_control.serialization import state_to_json
from tests.fake_asusd import FakeAsusd
from tests.test_hardware import FakeAura, make_service


def test_state_serialization() -> None:
    state = HardwareState(
        profile=Profile.QUIET,
        fans=FanStatus(mode=None),
        brightness=Brightness.LOW,
        lightbar=LightbarState(boot=True, awake=False, sleep=False, shutdown=False),
        charge_limit=60,
        battery=BatteryStatus(percent=66, ac_online=False, charging_state="Discharging"),
        sensors=SensorReadings(cpu_package_temp=59.0, cpu_fan_rpm=2000),
    )

    assert state_to_json(state) == {
        "asusdAvailable": True,
        "profile": "Quiet",
        "fans": {"mode": None},
        "brightness": "low",
        "lightbar": {"on": False},
        "chargeLimit": 60,
        "battery": {"percent": 66, "acOnline": False, "status": "Descargando"},
        "sensors": {"cpuTemp": 59.0, "cpuFan": 2000, "gpuFan": None, "midFan": None},
    }


def test_unavailable_state_serializes_to_nulls() -> None:
    data = state_to_json(HardwareState())

    assert data["asusdAvailable"] is False
    assert data["profile"] is None
    assert data["fans"] is None
    assert data["lightbar"] is None
    assert data["battery"] is None


def test_state_command() -> None:
    response = run(["state"], make_service(FakeAsusd()))

    assert response["ok"] is True
    assert response["state"]["profile"] == "Balanced"
    assert response["state"]["fans"] == {"mode": "Normal"}


def test_profile_command_reads_only_the_profile() -> None:
    asusd = FakeAsusd(profile="Performance")

    response = run(["profile"], make_service(asusd))

    assert response == {"ok": True, "message": None, "state": {"profile": "Performance"}}
    assert asusd.calls == [["profile", "get"]]


@pytest.mark.parametrize(
    ("argv", "check"),
    [
        (["set", "profile", "Quiet"], lambda a, _l: a.profile == "Quiet"),
        (["set", "brightness", "med"], lambda a, _l: a.brightness == "Med"),
        (["set", "charge-limit", "80"], lambda a, _l: a.charge_limit == 80),
        (["set", "lightbar", "on"], lambda _a, light: light.lightbar.awake),
        (["set", "fan", "Ultra Mega"], lambda a, _l: all(c.enabled for c in a.curves.values())),
    ],
)
def test_set_commands_apply_and_confirm(
    argv: list[str], check: Callable[[FakeAsusd, FakeAura], bool]
) -> None:
    asusd, aura = FakeAsusd(), FakeAura()

    response = run(argv, make_service(asusd, aura))

    assert response["ok"] is True, response["message"]
    assert response["message"]
    assert check(asusd, aura)


def test_expected_error_is_reported_with_current_state() -> None:
    asusd = FakeAsusd(profile="Quiet")

    response = run(["set", "fan", FanMode.EXTRA.value], make_service(asusd))

    assert response["ok"] is False
    assert "Balanced" in response["message"]
    assert response["state"]["profile"] == "Quiet"
    assert asusd.profile == "Quiet"


@pytest.mark.parametrize(
    "argv",
    [[], ["set", "profile", "Turbo"], ["set", "charge-limit", "75"], ["set", "lightbar", "1"]],
)
def test_rejects_invalid_arguments(argv: list[str]) -> None:
    with pytest.raises(SystemExit):
        run(argv, make_service(FakeAsusd()))


def test_main_prints_single_json_line(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("asus_control.cli.build_service", lambda: make_service(FakeAsusd()))

    assert main(["state"]) == 0
    output = capsys.readouterr().out
    assert output.count("\n") == 1
    assert json.loads(output)["state"]["profile"] == "Balanced"


def test_main_returns_error_code_on_unexpected_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken() -> object:
        raise RuntimeError("fallo de programación")

    monkeypatch.setattr("asus_control.cli.build_service", broken)

    assert main(["state"]) == 1
