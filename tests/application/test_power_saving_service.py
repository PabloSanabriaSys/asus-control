from __future__ import annotations

from pathlib import Path

import pytest

from asus_control.application.fan_service import FanService
from asus_control.application.hardware_service import HardwareService
from asus_control.application.power_saving_service import PowerSavingService
from asus_control.domain.errors import HardwareAccessError
from asus_control.domain.power_saving import PowerSavingCapture, SavedSetting
from asus_control.infrastructure.power_saving_store import FilePowerSavingStore
from asus_control.presentation.cli import run
from tests.fakes import FakeLightbar, FakePlatform, FakeSensors, no_lock


class Device:
    def __init__(self) -> None:
        self.values = {"profile": "Balanced", "brightness": "high"}
        self.captures = 0
        self.writes: list[str] = []
        self.fail: set[str] = set()
        self.ignore_writes = False
        self.crash = False

    def capture(self, brightness_percent: int) -> PowerSavingCapture:
        self.captures += 1
        return PowerSavingCapture(
            tuple(
                SavedSetting(key, value, target)
                for (key, value), target in zip(self.values.items(), ("Quiet", "off"), strict=True)
            ),
            ("gpu.manual",),
        )

    def read(self, key: str) -> str:
        return self.values[key]

    def write(self, key: str, value: str) -> None:
        self.writes.append(key)
        if key in self.fail:
            raise HardwareAccessError("Device disconnected")
        if not self.ignore_writes:
            self.values[key] = value
        if self.crash:
            raise KeyboardInterrupt


def service(device: Device, path: Path) -> PowerSavingService:
    return PowerSavingService(device, FilePowerSavingStore(path), no_lock)


def test_enable_restart_reconcile_disable_preserves_original_snapshot(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    device = Device()
    service(device, path).set_enabled(True)
    snapshot = service(device, path).status()
    assert device.values == {"profile": "Quiet", "brightness": "off"}

    # Firmware / session tools reset values during boot. The saved originals must survive.
    device.values = {"profile": "Performance", "brightness": "medium"}
    restarted = service(device, path)
    restarted.reconcile()
    restarted.set_enabled(True)
    assert restarted.status().settings == snapshot.settings
    assert device.captures == 1

    restarted.set_enabled(False)
    assert device.values == {"profile": "Balanced", "brightness": "high"}
    assert restarted.status() is None


def test_status_and_disabled_reconcile_do_not_touch_hardware(tmp_path: Path) -> None:
    device = Device()
    saving = service(device, tmp_path / "state.json")
    assert saving.status() is None
    saving.reconcile()
    saving.set_enabled(False)
    assert device.captures == 0
    assert device.writes == []
    assert not (tmp_path / "state.json").exists()


def test_failed_durable_write_prevents_any_hardware_write(tmp_path: Path) -> None:
    device = Device()
    path = tmp_path / "not-a-directory"
    path.write_text("blocked")
    with pytest.raises(HardwareAccessError):
        service(device, path / "state.json").set_enabled(True)
    assert device.writes == []


def test_crash_after_hardware_write_is_recoverable(tmp_path: Path) -> None:
    device = Device()
    path = tmp_path / "state.json"
    device.crash = True
    with pytest.raises(KeyboardInterrupt):
        service(device, path).set_enabled(True)
    assert FilePowerSavingStore(path).load().settings[0].original == "Balanced"
    device.crash = False
    service(device, path).set_enabled(False)
    assert device.values == {"profile": "Balanced", "brightness": "high"}


def test_failed_restore_retains_backup_and_resumes_after_restart(tmp_path: Path) -> None:
    device = Device()
    path = tmp_path / "state.json"
    saving = service(device, path)
    saving.set_enabled(True)
    device.fail.add("brightness")
    with pytest.raises(HardwareAccessError):
        saving.set_enabled(False)
    pending = FilePowerSavingStore(path).load()
    assert not pending.enabled
    assert pending.pending == ("brightness",)
    assert pending.settings[1].original == "high"
    with pytest.raises(HardwareAccessError), saving.manual_control():
        pytest.fail("Manual writes must be blocked until restoration finishes")
    device.fail.clear()
    service(device, path).reconcile()
    assert device.values == {"profile": "Balanced", "brightness": "high"}
    assert saving.status() is None


def test_unconfirmed_writes_remain_pending_and_retryable(tmp_path: Path) -> None:
    device = Device()
    saving = service(device, tmp_path / "state.json")
    device.ignore_writes = True
    with pytest.raises(HardwareAccessError):
        saving.set_enabled(True)
    assert set(saving.status().pending) == {"profile", "brightness"}
    device.ignore_writes = False
    saving.reconcile()
    assert saving.status().pending == ()


def test_corrupt_backup_blocks_activation_and_manual_changes(tmp_path: Path) -> None:
    device = Device()
    path = tmp_path / "state.json"
    path.write_text('{"version": 99}')
    saving = service(device, path)
    with pytest.raises(HardwareAccessError):
        saving.set_enabled(True)
    with pytest.raises(HardwareAccessError), saving.manual_control():
        pytest.fail("Corrupt backup must not be overwritten")
    assert device.writes == []
    assert path.read_text() == '{"version": 99}'


def test_restore_rechecks_settings_changed_by_later_side_effects(tmp_path: Path) -> None:
    class SideEffectDevice(Device):
        def write(self, key: str, value: str) -> None:
            super().write(key, value)
            if key == "brightness" and value == "high":
                self.values["profile"] = "Performance"

    device = SideEffectDevice()
    saving = service(device, tmp_path / "state.json")
    saving.set_enabled(True)
    with pytest.raises(HardwareAccessError):
        saving.set_enabled(False)
    assert saving.status().pending == ("profile",)
    saving.reconcile()
    assert saving.status() is None


def test_reconcile_with_matching_targets_does_not_rewrite_backup(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    saving = service(Device(), path)
    saving.set_enabled(True)
    timestamp = path.stat().st_mtime_ns
    saving.reconcile()
    assert path.stat().st_mtime_ns == timestamp


def test_activation_detects_side_effects_and_retries_without_recapture(tmp_path: Path) -> None:
    class SideEffectDevice(Device):
        def write(self, key: str, value: str) -> None:
            super().write(key, value)
            if key == "brightness" and value == "off":
                self.values["profile"] = "Performance"

    device = SideEffectDevice()
    saving = service(device, tmp_path / "state.json")
    with pytest.raises(HardwareAccessError):
        saving.set_enabled(True)
    assert saving.status().pending == ("profile",)
    saving.reconcile()
    assert not saving.status().pending
    assert device.values == {"profile": "Quiet", "brightness": "off"}
    assert device.captures == 1


def test_cli_reports_state_and_blocks_manual_changes_until_restored(tmp_path: Path) -> None:
    saving = service(Device(), tmp_path / "state.json")
    platform = FakePlatform()
    hardware = HardwareService(
        platform, FakeLightbar(), FakeSensors(), FanService(platform, no_lock)
    )
    assert run(["state"], hardware, saving)["state"]["powerSaving"]["enabled"] is False
    assert run(["power-saving", "on"], hardware, saving)["ok"]
    blocked = run(["set", "profile", "Performance"], hardware, saving)
    assert not blocked["ok"]
    assert "set_profile" not in platform.calls
    assert run(["power-saving", "off"], hardware, saving)["ok"]
    assert run(["set", "profile", "Performance"], hardware, saving)["ok"]


def test_cli_exposes_corrupt_snapshot_without_overwriting_it(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text("broken")
    platform = FakePlatform()
    hardware = HardwareService(
        platform, FakeLightbar(), FakeSensors(), FanService(platform, no_lock)
    )
    state = run(["state"], hardware, service(Device(), path))["state"]["powerSaving"]
    assert not state["available"]
    assert state["errors"]
    assert path.read_text() == "broken"
