from __future__ import annotations

import json
from pathlib import Path

import pytest

from asus_control.domain.errors import HardwareAccessError
from asus_control.infrastructure.busctl import Busctl
from asus_control.infrastructure.kde_power import KdePower, encode, policy_targets
from tests.conftest import FakeRunner


def kde(config: Path) -> KdePower:
    bus = Busctl(FakeRunner(), "fake", scope="--user")
    return KdePower(bus, bus, config)


def test_policy_restore_preserves_unrelated_values_and_absent_keys(tmp_path: Path) -> None:
    config = tmp_path / "powerdevilrc"
    config.write_text(
        "# preserved comment\n[AC][Display]\nTurnOffDisplayWhenIdle=false\n"
        "Unrelated=keep\n\n[AC][SuspendAndShutdown]\nLidAction=0\n"
    )
    power = kde(config)
    targets = policy_targets(True)
    original = power.read_policy(list(targets))
    power.write_policy(encode(targets))
    assert json.loads(power.read_policy(list(targets))) == targets
    # Simulate a user's unrelated edit while saving is enabled.
    config.write_text(config.read_text().replace("LidAction=0", "LidAction=32"))
    power.write_policy(original)
    assert power.read_policy(list(targets)) == original
    assert "Unrelated=keep" in config.read_text()
    assert "# preserved comment" in config.read_text()
    assert "LidAction=32" in config.read_text()
    assert "AutoSuspendIdleTimeoutSec=" not in config.read_text()


def panel(mode_id: str = "44", rate: float = 165) -> dict[str, object]:
    return {
        "name": "eDP-1",
        "connected": True,
        "enabled": True,
        "currentModeId": mode_id,
        "modes": [
            {"id": mode_id, "size": {"width": 1920, "height": 1200}, "refreshRate": rate},
            {"id": "45", "size": {"width": 1920, "height": 1200}, "refreshRate": 60},
            {"id": "46", "size": {"width": 1280, "height": 800}, "refreshRate": 60},
        ],
    }


def test_screen_restore_resolves_mode_ids_after_reboot(tmp_path: Path) -> None:
    power = kde(tmp_path / "config")
    screen = FakeRunner(lambda _args: json.dumps({"outputs": [panel()]}))
    power._screen = screen
    original = power.read_refresh()
    target = json.loads(power.refresh_target())
    assert target["refresh"] == 60
    assert target["size"] == {"width": 1920, "height": 1200}
    screen._handler = lambda _args: json.dumps({"outputs": [panel("99")]})
    power.write_refresh(original)
    assert screen.calls[-1] == ["output.eDP-1.mode.99"]


def test_missing_internal_screen_does_not_touch_external_monitor(tmp_path: Path) -> None:
    power = kde(tmp_path / "config")
    output = dict(panel(), name="HDMI-A-1")
    screen = FakeRunner(lambda _args: json.dumps({"outputs": [output]}))
    power._screen = screen
    with pytest.raises(HardwareAccessError):
        power.read_refresh()
    assert screen.calls == [["-j"]]


def test_screen_with_no_native_60hz_mode_is_skipped(tmp_path: Path) -> None:
    power = kde(tmp_path / "config")
    output = panel()
    output["modes"] = output["modes"][:1]
    power._screen = FakeRunner(lambda _args: json.dumps({"outputs": [output]}))
    with pytest.raises(HardwareAccessError):
        power.refresh_target()


def test_suspension_settings_are_not_added_when_unsupported() -> None:
    assert not any("SuspendAndShutdown" in key for key in policy_targets(False))
