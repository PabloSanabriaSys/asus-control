from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

import pytest

from asus_control.application.power_saving_service import PowerSavingService
from asus_control.domain.errors import HardwareAccessError
from asus_control.domain.power_saving import PowerSavingCapture, SavedSetting
from asus_control.infrastructure.busctl import Busctl
from asus_control.infrastructure.gpu import GPU_ROOT, AsusGpu
from asus_control.infrastructure.power_saving_store import FilePowerSavingStore
from tests.fakes import no_lock


class DeferredGpuBus:
    def __init__(self, *, mux: int | None = 1, dgpu: int = 0) -> None:
        self.values = {"dgpu_disable": dgpu}
        if mux is not None:
            self.values["gpu_mux_mode"] = mux
        self.queue = dict.fromkeys(self.values, -1)
        self.writes: list[tuple[str, int]] = []

    def __call__(self, args: Sequence[str]) -> str:
        args = [a for a in args if a not in ("--system", "--json=short")]
        if args[:2] == ["--list", "tree"]:
            return "\n".join(GPU_ROOT + name for name in self.values)
        name = args[2].rsplit("/", 1)[-1]
        if args[0] == "get-property":
            values = {
                "CurrentValue": self.values[name],
                "QueuedGpuValue": self.queue[name],
                "PossibleValues": [0, 1],
            }
            return json.dumps({"type": "i", "data": values[args[4]]})
        if args[0] == "set-property":
            value = int(args[-1])
            self.writes.append((name, value))
            self.queue[name] = -1 if value == self.values[name] else value
            return ""
        raise AssertionError("Never apply queued GPU values in the live desktop session")

    def reboot(self) -> None:
        for name, queued in self.queue.items():
            if queued != -1:
                self.values[name] = queued
                self.queue[name] = -1


class GpuDevice:
    def __init__(self, fake: DeferredGpuBus) -> None:
        self.gpu = AsusGpu(Busctl(fake, "xyz.ljones.Asusd"), lambda _args: "active")

    def capture(self) -> PowerSavingCapture:
        original = self.gpu.read()
        return PowerSavingCapture(
            (SavedSetting("gpu.configuration", original, self.gpu.integrated_target(original)),)
        )

    def read(self, key: str) -> str:
        return self.gpu.read()

    def write(self, key: str, value: str) -> None:
        self.gpu.write(value)

    def restart_required(self, key: str, value: str) -> bool:
        return self.gpu.restart_required(value)


@pytest.mark.parametrize("mux", [None, 0, 1])
def test_gpu_on_restart_off_restart_restores_original(tmp_path: Path, mux: int | None) -> None:
    fake = DeferredGpuBus(mux=mux)
    original = dict(fake.values)
    device = GpuDevice(fake)
    store = FilePowerSavingStore(tmp_path / "state.json")
    saving = PowerSavingService(device, store, no_lock)
    saving.set_enabled(True)
    assert fake.values == original
    assert saving.status().pending == ("gpu.configuration",)
    check = saving.inspect().checks[0]
    assert check.restart_required and not check.confirmed
    assert not saving.status().errors
    timestamp = store.path.stat().st_mtime_ns
    saving.reconcile()
    assert store.path.stat().st_mtime_ns == timestamp

    fake.reboot()
    PowerSavingService(device, store, no_lock).reconcile()
    assert set(fake.values.values()) == {1}
    assert saving.inspect().checks[0].confirmed
    assert not saving.status().pending

    saving.set_enabled(False)
    assert not saving.status().enabled
    assert saving.inspect().checks[0].restart_required
    fake.reboot()
    PowerSavingService(device, store, no_lock).reconcile()
    assert fake.values == original
    assert store.load() is None


def test_turning_off_before_reboot_cancels_queue(tmp_path: Path) -> None:
    fake = DeferredGpuBus()
    saving = PowerSavingService(GpuDevice(fake), FilePowerSavingStore(tmp_path / "state"), no_lock)
    saving.set_enabled(True)
    assert fake.queue["dgpu_disable"] == 1
    saving.set_enabled(False)
    assert set(fake.queue.values()) == {-1}
    assert fake.values["dgpu_disable"] == 0
    assert saving.status() is None


def test_existing_integrated_mode_needs_no_restart(tmp_path: Path) -> None:
    fake = DeferredGpuBus(dgpu=1)
    saving = PowerSavingService(GpuDevice(fake), FilePowerSavingStore(tmp_path / "state"), no_lock)
    saving.set_enabled(True)
    assert saving.inspect().checks[0].confirmed
    assert not saving.status().pending
    assert not fake.writes


def test_existing_external_gpu_queue_is_not_overwritten(tmp_path: Path) -> None:
    fake = DeferredGpuBus()
    fake.queue["dgpu_disable"] = 1
    saving = PowerSavingService(GpuDevice(fake), FilePowerSavingStore(tmp_path / "state"), no_lock)
    with pytest.raises(HardwareAccessError):
        saving.set_enabled(True)
    assert not fake.writes
    assert fake.queue["dgpu_disable"] == 1
    assert saving.status() is None


def test_shutdown_handler_is_required_before_queuing() -> None:
    def missing(_args: Sequence[str]) -> str:
        raise HardwareAccessError("No shutdown handler")

    fake = DeferredGpuBus()
    gpu = AsusGpu(Busctl(fake, "xyz.ljones.Asusd"), missing)
    with pytest.raises(HardwareAccessError):
        gpu.integrated_target(gpu.read())
    assert not fake.writes


def test_partial_queue_failure_can_be_cancelled_without_reboot(tmp_path: Path) -> None:
    class FailingGpuBus(DeferredGpuBus):
        def __call__(self, args: Sequence[str]) -> str:
            if "set-property" in args and GPU_ROOT + "dgpu_disable" in args and args[-1] == "1":
                raise HardwareAccessError("Failed to queue dedicated GPU disable")
            return super().__call__(args)

    fake = FailingGpuBus(mux=0)
    saving = PowerSavingService(GpuDevice(fake), FilePowerSavingStore(tmp_path / "state"), no_lock)
    with pytest.raises(HardwareAccessError):
        saving.set_enabled(True)
    assert fake.queue["gpu_mux_mode"] == 1
    assert not saving.inspect().checks[0].restart_required
    saving.set_enabled(False)
    assert fake.values == {"gpu_mux_mode": 0, "dgpu_disable": 0}
    assert set(fake.queue.values()) == {-1}
    assert saving.status() is None


class ManualGpuDevice(GpuDevice):
    def __init__(self, fake: DeferredGpuBus) -> None:
        super().__init__(fake)
        self.profile = "Balanced"

    def capture(self) -> PowerSavingCapture:
        try:
            gpu = super().capture().settings
        except HardwareAccessError:
            gpu = ()  # The production capture reports an existing GPU queue as optional.
        return PowerSavingCapture((*gpu, SavedSetting("profile", self.profile, "Quiet")))

    def read(self, key: str) -> str:
        return self.profile if key == "profile" else super().read(key)

    def write(self, key: str, value: str) -> None:
        if key == "profile":
            self.profile = value
        else:
            super().write(key, value)

    def restart_required(self, key: str, value: str) -> bool:
        return key != "profile" and super().restart_required(key, value)


def test_manual_changes_survive_gpu_restoration_and_restart(tmp_path: Path) -> None:
    fake = DeferredGpuBus()
    device = ManualGpuDevice(fake)
    store = FilePowerSavingStore(tmp_path / "state")
    saving = PowerSavingService(device, store, no_lock)
    saving.set_enabled(True)
    with pytest.raises(HardwareAccessError), saving.manual_control():
        pytest.fail("Active saving must keep manual controls locked")
    fake.reboot()
    saving.reconcile()
    saving.set_enabled(False)
    assert device.profile == "Balanced"
    assert [s.key for s in saving.status().settings] == ["gpu.configuration"]
    with saving.manual_control():
        device.profile = "Performance"
    saving.reconcile()
    assert device.profile == "Performance"
    assert [c.key for c in saving.inspect().checks] == ["gpu.configuration"]
    fake.reboot()
    PowerSavingService(device, store, no_lock).reconcile()
    assert saving.status() is None
    assert device.profile == "Performance"


def test_reenable_during_gpu_restore_captures_new_manual_originals(tmp_path: Path) -> None:
    fake = DeferredGpuBus()
    device = ManualGpuDevice(fake)
    saving = PowerSavingService(device, FilePowerSavingStore(tmp_path / "state"), no_lock)
    saving.set_enabled(True)
    fake.reboot()
    saving.reconcile()
    saving.set_enabled(False)
    gpu_original = saving.status().settings[0].original
    with saving.manual_control():
        device.profile = "Performance"
    saving.set_enabled(True)
    assert device.profile == "Quiet"
    assert next(s.original for s in saving.status().settings if s.key == "profile") == "Performance"
    assert (
        next(s.original for s in saving.status().settings if s.key == "gpu.configuration")
        == gpu_original
    )
    saving.set_enabled(False)
    assert device.profile == "Performance"
    fake.reboot()
    saving.reconcile()
    assert saving.status() is None
