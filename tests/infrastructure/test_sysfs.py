from __future__ import annotations

from pathlib import Path

from asus_control.domain.models import BatteryStatus, SensorReadings
from asus_control.infrastructure.sysfs import SysfsSensors


def write_attributes(directory: Path, **attributes: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name, value in attributes.items():
        (directory / name).write_text(f"{value}\n")


def build_sysfs(root: Path) -> None:
    hwmon = root / "class" / "hwmon"
    # Números distintos a los del equipo real para asegurar que no se usan índices fijos.
    write_attributes(hwmon / "hwmon0", name="nvme", temp1_input="40000", temp1_label="Composite")
    write_attributes(
        hwmon / "hwmon3",
        name="coretemp",
        temp1_input="61000",
        temp1_label="Core 0",
        temp9_input="72500",
        temp9_label="Package id 0",
    )
    write_attributes(
        hwmon / "hwmon7",
        name="asus",
        fan1_input="2600",
        fan1_label="mid_fan",
        fan2_input="3100",
        fan2_label="cpu_fan",
        fan3_input="0",
        fan3_label="gpu_fan",
    )
    supplies = root / "class" / "power_supply"
    write_attributes(supplies / "hid-mouse", type="Battery", scope="Device", capacity="10")
    write_attributes(supplies / "BAT1", type="Battery", capacity="73", status="Not charging")
    write_attributes(supplies / "ACAD", type="Mains", online="1")


def test_discovers_sensors_by_name_and_label(tmp_path: Path) -> None:
    build_sysfs(tmp_path)

    readings = SysfsSensors(tmp_path).read_sensors()

    assert readings == SensorReadings(
        cpu_package_temp=72.5, cpu_fan_rpm=3100, gpu_fan_rpm=0, mid_fan_rpm=2600
    )


def test_reads_system_battery_and_mains(tmp_path: Path) -> None:
    build_sysfs(tmp_path)

    assert SysfsSensors(tmp_path).read_battery() == BatteryStatus(
        percent=73, ac_online=True, charging_state="Not charging"
    )


def test_missing_devices_are_unavailable(tmp_path: Path) -> None:
    sensors = SysfsSensors(tmp_path)

    assert sensors.read_sensors() == SensorReadings()
    assert sensors.read_battery() is None


def test_missing_fan_label_is_unavailable(tmp_path: Path) -> None:
    write_attributes(tmp_path / "class" / "hwmon" / "hwmon1", name="asus", fan1_input="1")

    assert SysfsSensors(tmp_path).read_sensors().cpu_fan_rpm is None


def test_real_sysfs_is_readable() -> None:
    readings = SysfsSensors().read_sensors()
    # En otro equipo los valores pueden faltar, pero la lectura nunca debe fallar.
    assert isinstance(readings, SensorReadings)
