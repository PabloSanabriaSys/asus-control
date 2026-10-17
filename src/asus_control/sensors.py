"""Lectura de sensores y batería desde sysfs.

Los dispositivos se localizan por ``name``, ``*_label`` y ``type``; nunca por el
número de ``hwmonN``, que cambia entre arranques.
"""

from __future__ import annotations

import logging
from pathlib import Path

from asus_control.models import BatteryStatus, SensorReadings

logger = logging.getLogger(__name__)

_ASUS_HWMON = "asus"
_CORETEMP_HWMON = "coretemp"
_CPU_PACKAGE_LABEL = "Package id 0"
_FAN_LABELS = {"cpu": "cpu_fan", "gpu": "gpu_fan", "mid": "mid_fan"}
_MILLIDEGREES_PER_DEGREE = 1000


class SysfsSensors:
    """Lee sensores de ``/sys``; la raíz es configurable para las pruebas."""

    def __init__(self, sysfs_root: Path = Path("/sys")) -> None:
        self._hwmon_dir = sysfs_root / "class" / "hwmon"
        self._power_supply_dir = sysfs_root / "class" / "power_supply"

    def read_sensors(self) -> SensorReadings:
        asus = self._find_hwmon(_ASUS_HWMON)
        coretemp = self._find_hwmon(_CORETEMP_HWMON)
        temp = _read_labelled(coretemp, "temp", _CPU_PACKAGE_LABEL) if coretemp else None
        return SensorReadings(
            cpu_package_temp=None if temp is None else temp / _MILLIDEGREES_PER_DEGREE,
            cpu_fan_rpm=_read_labelled(asus, "fan", _FAN_LABELS["cpu"]) if asus else None,
            gpu_fan_rpm=_read_labelled(asus, "fan", _FAN_LABELS["gpu"]) if asus else None,
            mid_fan_rpm=_read_labelled(asus, "fan", _FAN_LABELS["mid"]) if asus else None,
        )

    def read_battery(self) -> BatteryStatus | None:
        battery = self._find_power_supply("Battery")
        if battery is None:
            return None
        mains = self._find_power_supply("Mains")
        online = _read_int(mains / "online") if mains else None
        return BatteryStatus(
            percent=_read_int(battery / "capacity"),
            ac_online=None if online is None else online == 1,
            charging_state=_read_text(battery / "status"),
        )

    def _find_hwmon(self, name: str) -> Path | None:
        return _first_with(self._hwmon_dir, "name", name)

    def _find_power_supply(self, kind: str) -> Path | None:
        # Los periféricos (ratones, mandos) tienen scope=Device: no son la batería del equipo.
        for device in _children(self._power_supply_dir):
            if _read_text(device / "type") == kind and _read_text(device / "scope") != "Device":
                return device
        return None


def _first_with(directory: Path, attribute: str, value: str) -> Path | None:
    for device in _children(directory):
        if _read_text(device / attribute) == value:
            return device
    return None


def _children(directory: Path) -> list[Path]:
    try:
        return sorted(directory.iterdir())
    except OSError:
        return []


def _read_labelled(hwmon: Path, kind: str, label: str) -> int | None:
    """Lee ``<kind>N_input`` cuyo ``<kind>N_label`` coincide con ``label``."""
    for label_file in sorted(hwmon.glob(f"{kind}*_label")):
        if _read_text(label_file) == label:
            channel = label_file.name.removesuffix("_label")
            return _read_int(hwmon / f"{channel}_input")
    return None


def _read_int(path: Path) -> int | None:
    text = _read_text(path)
    if text is None:
        return None
    try:
        return int(text)
    except ValueError:
        logger.warning("Valor no numérico en %s: %r", path, text)
        return None


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text().strip()
    except OSError:
        return None
