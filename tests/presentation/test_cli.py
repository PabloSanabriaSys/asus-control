from __future__ import annotations

import json
from collections.abc import Callable

import pytest

from asus_control.application.fan_service import FanService
from asus_control.application.hardware_service import HardwareService
from asus_control.domain.models import Brightness, Profile
from asus_control.presentation.cli import main, run
from tests.fakes import FakeLightbar, FakePlatform, FakeSensors, no_lock


def make_service(
    platform: FakePlatform | None = None, lightbar: FakeLightbar | None = None
) -> HardwareService:
    platform = platform or FakePlatform()
    return HardwareService(
        platform, lightbar or FakeLightbar(), FakeSensors(), FanService(platform, no_lock)
    )


def test_state_command() -> None:
    response = run(["state"], make_service())

    assert response["ok"] is True
    assert response["state"]["profile"] == "Balanced"
    assert response["state"]["fans"] == {"mode": "Normal"}


def test_profile_command_reads_only_the_profile() -> None:
    platform = FakePlatform(profile=Profile.PERFORMANCE)

    response = run(["profile"], make_service(platform))

    assert response == {"ok": True, "error": None, "state": {"profile": "Performance"}}
    assert platform.calls == ["get_profile"]


@pytest.mark.parametrize(
    ("argv", "applied"),
    [
        (["set", "profile", "Quiet"], lambda p, _l: p.profile is Profile.QUIET),
        (["set", "brightness", "medium"], lambda p, _l: p.brightness is Brightness.MEDIUM),
        (["set", "charge-limit", "80"], lambda p, _l: p.charge_limit == 80),
        (["set", "lightbar", "on"], lambda _p, light: light.state.awake),
        (["set", "fan", "Ultra Mega"], lambda p, _l: all(c.enabled for c in p.curves.values())),
    ],
)
def test_set_commands_apply_and_return_new_state(
    argv: list[str], applied: Callable[[FakePlatform, FakeLightbar], bool]
) -> None:
    platform, lightbar = FakePlatform(), FakeLightbar()

    response = run(argv, make_service(platform, lightbar))

    assert (response["ok"], response["error"]) == (True, None)
    assert applied(platform, lightbar)


def test_expected_error_is_reported_with_current_state() -> None:
    platform = FakePlatform(profile=Profile.QUIET)

    response = run(["set", "fan", "Extra"], make_service(platform))

    assert response["ok"] is False
    assert response["error"] == {"code": "fanRequiresBalanced"}
    assert response["state"]["profile"] == "Quiet"
    assert platform.profile is Profile.QUIET


@pytest.mark.parametrize(
    "argv",
    [[], ["set", "profile", "Turbo"], ["set", "charge-limit", "75"], ["set", "lightbar", "1"]],
)
def test_rejects_invalid_arguments(argv: list[str]) -> None:
    with pytest.raises(SystemExit):
        run(argv, make_service())


def test_main_prints_single_json_line(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["state"], make_service) == 0

    output = capsys.readouterr().out
    assert output.count("\n") == 1
    assert json.loads(output)["state"]["profile"] == "Balanced"


def test_main_returns_error_code_on_unexpected_failure() -> None:
    def broken() -> HardwareService:
        raise RuntimeError("fallo de programación")

    assert main(["state"], broken) == 1
