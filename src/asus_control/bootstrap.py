"""Raíz de composición: el único lugar que conoce todas las capas y las conecta."""

from __future__ import annotations

import sys

from asus_control.application.fan_service import FanService
from asus_control.application.hardware_service import HardwareService
from asus_control.infrastructure.asusctl import AsusCtl
from asus_control.infrastructure.aura import AsusdLightbar
from asus_control.infrastructure.fan_lock import default_lock_path, fan_lock
from asus_control.infrastructure.process import ASUSCTL, BUSCTL, SubprocessRunner
from asus_control.infrastructure.sysfs import SysfsSensors
from asus_control.presentation import cli


def build_hardware_service() -> HardwareService:
    asusctl_runner = SubprocessRunner(ASUSCTL)
    platform = AsusCtl(asusctl_runner)
    lock_path = default_lock_path()
    return HardwareService(
        platform=platform,
        lightbar=AsusdLightbar(busctl=SubprocessRunner(BUSCTL), asusctl=asusctl_runner),
        sensors=SysfsSensors(),
        fans=FanService(platform, lambda: fan_lock(lock_path)),
    )


def main() -> int:
    """Punto de entrada de ``asus-control``."""
    return cli.main(sys.argv[1:], build_hardware_service)
