"""ASUS GPU transitions queued for asus-shutdown, never forced into a live session."""

from __future__ import annotations

import json

from asus_control.domain.errors import HardwareAccessError
from asus_control.infrastructure.busctl import Busctl
from asus_control.infrastructure.kde_power import encode
from asus_control.infrastructure.process import CommandRunner, SubprocessRunner

GPU_ROOT = "/xyz/ljones/asus_armoury/"
GPU_INTERFACE = "xyz.ljones.AsusArmoury"


class AsusGpu:
    def __init__(self, bus: Busctl, shutdown_check: CommandRunner | None = None) -> None:
        self._bus = bus
        self._shutdown_check = shutdown_check or SubprocessRunner("/usr/bin/systemctl")

    def read(self) -> str:
        paths = self._bus.object_paths()
        if GPU_ROOT + "dgpu_disable" not in paths:
            raise HardwareAccessError("Integrated GPU switching is unavailable")
        result: dict[str, list[int]] = {}
        for name in ("gpu_mux_mode", "dgpu_disable"):
            path = GPU_ROOT + name
            if path not in paths:
                continue
            current = self._bus.get_property(path, GPU_INTERFACE, "CurrentValue")
            queued = self._bus.get_property(path, GPU_INTERFACE, "QueuedGpuValue")
            possible = self._bus.get_property(path, GPU_INTERFACE, "PossibleValues")
            if (
                type(current) is not int
                or current not in (0, 1)
                or type(queued) is not int
                or queued not in (-1, 0, 1)
                or not isinstance(possible, list)
                or not {0, 1} <= set(possible)
            ):
                raise HardwareAccessError("GPU does not support safe deferred switching")
            result[name] = [current, queued]
        return encode(result)

    def integrated_target(self, original: str) -> str:
        values = json.loads(original)
        if any(queued != -1 for _, queued in values.values()):
            raise HardwareAccessError("Another GPU transition is already queued")
        # No writes unless the shutdown handler that safely applies the queue is running.
        self._shutdown_check(["is-active", "asus-shutdown.service"])
        return encode({name: [1, -1] for name in values})

    def write(self, value: str) -> None:
        expected = json.loads(value)
        current = json.loads(self.read())
        if set(expected) != set(current):
            raise HardwareAccessError("The original GPU controls are unavailable")
        for name in ("gpu_mux_mode", "dgpu_disable"):
            if name not in expected:
                continue
            if current[name] == expected[name]:
                continue
            target, queued = expected[name]
            if target not in (0, 1) or queued != -1:
                raise HardwareAccessError("Invalid saved GPU mode")
            # The setter queues a different value, or cancels a queue if already current.
            # ApplyQueuedGpuValue is deliberately NEVER called in the desktop session.
            self._bus.set_property(GPU_ROOT + name, GPU_INTERFACE, "CurrentValue", "i", target)

    def restart_required(self, value: str) -> bool:
        expected = json.loads(value)
        current = json.loads(self.read())
        if set(current) != set(expected):
            return False
        pending = False
        for name, (target, no_queue) in expected.items():
            actual, queued = current[name]
            if no_queue != -1:
                return False
            if actual == target and queued == -1:
                continue
            if actual != target and queued == target:
                pending = True
                continue
            return False
        return pending
