from __future__ import annotations

from pathlib import Path

import pytest

from asus_control.application.fan_service import FanService
from asus_control.application.hardware_service import HardwareService
from asus_control.application.power_saving_service import PowerSavingService
from asus_control.domain.errors import HardwareAccessError
from asus_control.domain.power_saving import (
    PowerSavingCapture,
    PowerSavingMigration,
    PowerSavingSession,
    SavedSetting,
)
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

    def capture(self) -> PowerSavingCapture:
        self.captures += 1
        return PowerSavingCapture(
            tuple(
                SavedSetting(key, value, target)
                for (key, value), target in zip(self.values.items(), ("Quiet", "off"), strict=True)
            ),
            ("gpu.manual",),
        )

    def restart_required(self, key: str, value: str) -> bool:
        return False

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


def test_charge_limit_is_blocked_while_saving_is_active(tmp_path: Path) -> None:
    saving = service(Device(), tmp_path / "state.json")
    platform = FakePlatform()
    hardware = HardwareService(
        platform, FakeLightbar(), FakeSensors(), FanService(platform, no_lock)
    )
    saving.set_enabled(True)
    assert not run(["set", "charge-limit", "60"], hardware, saving)["ok"]
    assert "set_charge_limit" not in platform.calls
    saving.set_enabled(False)
    assert run(["set", "charge-limit", "80"], hardware, saving)["ok"]


def test_audit_detects_external_drift_without_writes_or_recapture(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    device = Device()
    saving = service(device, path)
    saving.set_enabled(True)
    device.values["profile"] = "Performance"
    backup = path.read_bytes()
    writes = list(device.writes)
    inspection = saving.inspect()
    check = next(c for c in inspection.checks if c.key == "profile")
    assert not check.confirmed
    assert check.expected == "Quiet" and check.actual == "Performance"
    assert path.read_bytes() == backup
    assert device.writes == writes
    assert device.captures == 1


def test_pending_write_is_repeated_when_side_effect_failed_after_value_was_saved(
    tmp_path: Path,
) -> None:
    class ReloadFailure(Device):
        failed = False

        def write(self, key: str, value: str) -> None:
            super().write(key, value)
            if key == "profile" and not self.failed:
                self.failed = True
                raise HardwareAccessError("Configuration saved but reload failed")

    device = ReloadFailure()
    saving = service(device, tmp_path / "state.json")
    with pytest.raises(HardwareAccessError):
        saving.set_enabled(True)
    assert device.values["profile"] == "Quiet"
    assert saving.status().pending == ("profile",)
    saving.reconcile()
    assert device.writes.count("profile") == 2
    assert saving.status().pending == ()


def test_removed_brightness_is_restored_once_without_replacing_other_originals(
    tmp_path: Path,
) -> None:
    device = Device()
    device.values["display.brightness"] = "30"
    store = FilePowerSavingStore(tmp_path / "state.json")
    original = SavedSetting("profile", "Balanced", "Quiet")
    store.save(
        PowerSavingSession(True, (original, SavedSetting("display.brightness", "80", "30")), ())
    )
    saving = PowerSavingService(
        device, store, no_lock, migration=PowerSavingMigration(retired_keys=("display.brightness",))
    )
    saving.reconcile()
    assert device.values["display.brightness"] == "80"
    assert store.load().settings == (original,)
    saving.reconcile()
    assert device.writes.count("display.brightness") == 1
    assert device.captures == 0
    saving.set_enabled(False)
    assert device.values["profile"] == "Balanced"


def test_failed_retirement_keeps_backup_and_does_not_apply_old_brightness_target(
    tmp_path: Path,
) -> None:
    device = Device()
    device.values["display.brightness"] = "30"
    device.fail.add("display.brightness")
    store = FilePowerSavingStore(tmp_path / "state.json")
    original = PowerSavingSession(
        True,
        (
            SavedSetting("profile", "Balanced", "Quiet"),
            SavedSetting("display.brightness", "80", "30"),
        ),
        (),
    )
    store.save(original)
    saving = PowerSavingService(
        device, store, no_lock, migration=PowerSavingMigration(retired_keys=("display.brightness",))
    )
    with pytest.raises(HardwareAccessError):
        saving.reconcile()
    assert store.load().settings == original.settings
    assert "display.brightness" in store.load().pending
    assert device.values["display.brightness"] == "30"
    assert device.captures == 0


def test_old_brightness_restores_after_policy_side_effects(tmp_path: Path) -> None:
    class PolicyReload(Device):
        def write(self, key: str, value: str) -> None:
            super().write(key, value)
            if key == "profile":
                self.values["display.brightness"] = "40"

    device = PolicyReload()
    device.values.update({"profile": "Quiet", "display.brightness": "30"})
    store = FilePowerSavingStore(tmp_path / "state.json")
    store.save(
        PowerSavingSession(
            True,
            (
                SavedSetting("display.brightness", "80", "30"),
                SavedSetting("profile", "Balanced", "Quiet"),
            ),
            (),
        )
    )
    saving = PowerSavingService(
        device, store, no_lock, migration=PowerSavingMigration(retired_keys=("display.brightness",))
    )
    saving.set_enabled(False)
    assert device.values["display.brightness"] == "80"
    assert device.values["profile"] == "Balanced"
    assert store.load() is None


def test_active_session_adds_charge_limit_without_replacing_old_originals(tmp_path: Path) -> None:
    class UpgradedDevice(Device):
        def capture(self) -> PowerSavingCapture:
            self.captures += 1
            return PowerSavingCapture(
                (
                    SavedSetting("profile", self.values["profile"], "Quiet"),
                    SavedSetting("battery.chargeLimit", self.values["battery.chargeLimit"], "100"),
                )
            )

    device = UpgradedDevice()
    device.values.update({"profile": "Quiet", "battery.chargeLimit": "80"})
    store = FilePowerSavingStore(tmp_path / "state")
    original = SavedSetting("profile", "Performance", "Quiet")
    store.save(PowerSavingSession(True, (original,), ()))
    saving = PowerSavingService(
        device, store, no_lock, migration=PowerSavingMigration(added_keys=("battery.chargeLimit",))
    )
    saving.reconcile()
    assert store.load().settings[0] == original
    assert device.values["battery.chargeLimit"] == "100"
    assert store.load().settings[1].original == "80"
    saving.reconcile()
    assert device.captures == 1
    saving.set_enabled(False)
    assert device.values["profile"] == "Performance"
    assert device.values["battery.chargeLimit"] == "80"
