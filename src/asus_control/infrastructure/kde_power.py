"""KDE screen and PowerDevil integration, restricted to the internal panel."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from asus_control.domain.errors import HardwareAccessError
from asus_control.infrastructure.busctl import Busctl
from asus_control.infrastructure.process import SubprocessRunner

POWER_SERVICE = "org.kde.Solid.PowerManagement"
POWER_PATH = "/org/kde/Solid/PowerManagement"
BRIGHTNESS_SERVICE = "org.kde.ScreenBrightness"
BRIGHTNESS_PATH = "/org/kde/ScreenBrightness"
BRIGHTNESS_INTERFACE = "org.kde.ScreenBrightness.Display"


def encode(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def policy_targets(can_suspend: bool) -> dict[str, str]:
    entries = {
        "Display/UseProfileSpecificDisplayBrightness": "false",
        "Keyboard/UseProfileSpecificKeyboardBrightness": "false",
        "Display/TurnOffDisplayWhenIdle": "true",
        "Display/TurnOffDisplayIdleTimeoutSec": "120",
        "Display/TurnOffDisplayIdleTimeoutWhenLockedSec": "60",
        # Avoid PowerDevil overriding Quiet when switching power source.
        "Performance/PowerProfile": "",
    }
    if can_suspend:
        entries.update(
            {
                "SuspendAndShutdown/AutoSuspendAction": "1",
                "SuspendAndShutdown/AutoSuspendIdleTimeoutSec": "600",
                "SuspendAndShutdown/SleepMode": "1",
            }
        )
    return {
        f"{profile}][{group}/{key}": value
        for profile in ("AC", "Battery", "LowBattery")
        for entry, value in entries.items()
        for group, key in [entry.split("/")]
    }


class KdePower:
    def __init__(self, user_bus: Busctl, login_bus: Busctl, config_path: Path) -> None:
        self._brightness = user_bus
        self._login = login_bus
        self._config_path = config_path
        self._power = Busctl(SubprocessRunner("/usr/bin/busctl"), POWER_SERVICE, scope="--user")
        self._screen = SubprocessRunner("/usr/bin/kscreen-doctor")

    def read_brightness(self) -> str:
        path = self._internal_brightness_path()
        value = self._brightness.get_property(path, BRIGHTNESS_INTERFACE, "Brightness")
        maximum = self._brightness.get_property(path, BRIGHTNESS_INTERFACE, "MaxBrightness")
        if type(value) is not int or type(maximum) is not int or maximum <= 0:
            raise HardwareAccessError("Invalid internal display brightness")
        if not 0 <= value <= maximum:
            raise HardwareAccessError("Internal display brightness is outside its range")
        return encode({"value": value, "max": maximum})

    def write_brightness(self, value: str) -> None:
        data = json.loads(value)
        path = self._internal_brightness_path()
        self._brightness.call(path, BRIGHTNESS_INTERFACE, "SetBrightness", "iu", data["value"], 1)

    def _internal_brightness_path(self) -> str:
        names = self._brightness.get_property(
            BRIGHTNESS_PATH, BRIGHTNESS_SERVICE, "DisplaysDBusNames"
        )
        if isinstance(names, list):
            for name in names:
                path = f"{BRIGHTNESS_PATH}/{name}"
                if self._brightness.get_property(path, BRIGHTNESS_INTERFACE, "IsInternal") is True:
                    return path
        raise HardwareAccessError("No controllable internal display")

    def panel(self) -> dict[str, Any]:
        try:
            outputs = json.loads(self._screen(["-j"]))["outputs"]
            for output in outputs:
                if (
                    output["name"].startswith(("eDP-", "LVDS-", "DSI-"))
                    and output["connected"]
                    and output["enabled"]
                ):
                    return dict(output)
        except (ValueError, KeyError, TypeError) as exc:
            raise HardwareAccessError(f"Invalid KScreen output: {exc}") from exc
        raise HardwareAccessError("No active internal panel")

    def read_refresh(self) -> str:
        panel = self.panel()
        mode = next((m for m in panel["modes"] if m["id"] == panel["currentModeId"]), None)
        if mode is None:
            raise HardwareAccessError("Internal panel mode is unavailable")
        return self._mode_value(panel, mode)

    def refresh_target(self) -> str:
        panel = self.panel()
        current = next((m for m in panel["modes"] if m["id"] == panel["currentModeId"]), None)
        if current is None:
            raise HardwareAccessError("Internal panel mode is unavailable")
        if current["refreshRate"] <= 60.5:
            return self._mode_value(panel, current)
        candidates = [
            m
            for m in panel["modes"]
            if m["size"] == current["size"] and 59 <= m["refreshRate"] <= 60.5
        ]
        if not candidates:
            raise HardwareAccessError("No 60 Hz mode at the current resolution")
        return self._mode_value(panel, min(candidates, key=lambda m: abs(m["refreshRate"] - 60)))

    def write_refresh(self, value: str) -> None:
        requested = json.loads(value)
        panel = self.panel()
        if panel["name"] != requested["name"]:
            raise HardwareAccessError("The original internal panel is unavailable")
        # Resolve a stable physical mode, never save numeric IDs across boots.
        mode = next((m for m in panel["modes"] if self._mode_value(panel, m) == value), None)
        if mode is None:
            raise HardwareAccessError("The saved display mode is unavailable")
        self._screen([f"output.{panel['name']}.mode.{mode['id']}"])

    @staticmethod
    def _mode_value(panel: dict[str, Any], mode: dict[str, Any]) -> str:
        return encode(
            {"name": panel["name"], "size": mode["size"], "refresh": round(mode["refreshRate"], 2)}
        )

    def can_suspend(self) -> bool:
        return self._login.call(
            "/org/freedesktop/login1", "org.freedesktop.login1.Manager", "CanSuspend"
        ) == ["yes"]

    def check_policy_support(self) -> None:
        self._power.call(POWER_PATH, POWER_SERVICE, "currentProfile")
        if any("[$i]" in line for line in self._config_lines()):
            raise HardwareAccessError("PowerDevil configuration is immutable")

    def read_policy(self, keys: list[str]) -> str:
        lines = self._config_lines()
        values: dict[str, str | None] = dict.fromkeys(keys)
        group = ""
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                group = stripped[1:-1]
            elif "=" in line and not stripped.startswith(("#", ";")):
                key, value = line.rstrip("\n").split("=", 1)
                address = f"{group}/{key}"
                if address in values:
                    values[address] = value
        return encode(values)

    def write_policy(self, value: str) -> None:
        values: dict[str, str | None] = json.loads(value)
        groups: dict[str, dict[str, str | None]] = {}
        for address, entry in values.items():
            group, key = address.split("/", 1)
            groups.setdefault(group, {})[key] = entry
        output: list[str] = []
        group = ""
        for line in self._config_lines():
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                self._append_entries(output, groups.pop(group, {}))
                group = stripped[1:-1]
            elif "=" in line and not stripped.startswith(("#", ";")):
                key = line.split("=", 1)[0]
                if key in groups.get(group, {}):
                    continue
            output.append(line if line.endswith("\n") else line + "\n")
        self._append_entries(output, groups.pop(group, {}))
        for name, entries in groups.items():
            if any(entry is not None for entry in entries.values()):
                output.append(f"\n[{name}]\n")
                self._append_entries(output, entries)
        self._atomic_config(self._remove_empty_groups(output, set(values)))
        self._power.call(POWER_PATH, POWER_SERVICE, "reparseConfiguration")
        self._power.call(POWER_PATH, POWER_SERVICE, "loadProfile", "b", True)

    def _config_lines(self) -> list[str]:
        try:
            return self._config_path.read_text().splitlines(keepends=True)
        except FileNotFoundError:
            return []
        except OSError as exc:
            raise HardwareAccessError(f"Cannot read PowerDevil settings: {exc}") from exc

    @staticmethod
    def _append_entries(output: list[str], entries: dict[str, str | None]) -> None:
        output.extend(f"{key}={value}\n" for key, value in entries.items() if value is not None)

    @staticmethod
    def _remove_empty_groups(lines: list[str], addresses: set[str]) -> str:
        managed = {address.split("/", 1)[0] for address in addresses}
        blocks: list[list[str]] = [[]]
        for line in lines:
            if line.strip().startswith("["):
                blocks.append([])
            blocks[-1].append(line)
        return "".join(
            "".join(block)
            for block in blocks
            if not block
            or block[0].strip()[1:-1] not in managed
            or any(line.strip() for line in block[1:])
        )

    def _atomic_config(self, text: str) -> None:
        temporary: str | None = None
        try:
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w", dir=self._config_path.parent, prefix=".asus-control-", delete=False
            ) as handle:
                temporary = handle.name
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            Path(temporary).replace(self._config_path)
        except OSError as exc:
            raise HardwareAccessError(f"Cannot update PowerDevil settings: {exc}") from exc
        finally:
            if temporary is not None:
                Path(temporary).unlink(missing_ok=True)
