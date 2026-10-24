"""Raíz de composición: el único lugar que conoce todas las capas y las conecta."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from asus_control.application.fan_service import FanService
from asus_control.application.hardware_service import HardwareService
from asus_control.application.power_saving_service import PowerSavingService
from asus_control.domain.power_saving import PowerSavingMigration
from asus_control.infrastructure.asusd import (
    ASUSD_SERVICE,
    AsusdLightbar,
    AsusdPlatform,
    AuraDevice,
)
from asus_control.infrastructure.busctl import Busctl
from asus_control.infrastructure.fan_lock import default_lock_path, fan_lock
from asus_control.infrastructure.kde_power import BRIGHTNESS_SERVICE, KdePower
from asus_control.infrastructure.power_saving_device import PowerSavingHardware
from asus_control.infrastructure.power_saving_store import FilePowerSavingStore, default_state_path
from asus_control.infrastructure.power_saving_watch import watch
from asus_control.infrastructure.process import BUSCTL, SubprocessRunner
from asus_control.infrastructure.sysfs import SysfsSensors
from asus_control.presentation import cli


def build_hardware_service() -> HardwareService:
    bus = Busctl(SubprocessRunner(BUSCTL), ASUSD_SERVICE)
    aura = AuraDevice(bus)
    platform = AsusdPlatform(bus, aura)
    lock_path = default_lock_path()
    return HardwareService(
        platform=platform,
        lightbar=AsusdLightbar(bus, aura),
        sensors=SysfsSensors(),
        fans=FanService(platform, lambda: fan_lock(lock_path)),
    )


def main() -> int:
    """Punto de entrada de ``asus-control``."""
    saving = build_power_saving_service()
    if sys.argv[1:] == ["power-saving", "watch"]:
        return watch(saving)
    return cli.main(sys.argv[1:], build_hardware_service, saving)


def build_power_saving_service() -> PowerSavingService:
    runner = SubprocessRunner(BUSCTL)
    bus = Busctl(runner, ASUSD_SERVICE)
    aura = AuraDevice(bus)
    config_root = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    kde = KdePower(
        Busctl(runner, BRIGHTNESS_SERVICE, scope="--user"),
        Busctl(runner, "org.freedesktop.login1"),
        config_root / "powerdevilrc",
    )
    power_lock = default_lock_path().with_name("asus-control-power-saving.lock")
    return PowerSavingService(
        PowerSavingHardware(AsusdPlatform(bus, aura), AsusdLightbar(bus, aura), bus, kde),
        FilePowerSavingStore(default_state_path()),
        lambda: fan_lock(power_lock, wait_seconds=3.0),
        lambda: fan_lock(default_lock_path()),
        migration=PowerSavingMigration(
            retired_keys=("display.brightness",),
            added_keys=("battery.chargeLimit", "gpu.configuration"),
        ),
    )
