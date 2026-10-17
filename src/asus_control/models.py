"""Tipos de dominio compartidos por todas las capas."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, IntEnum, StrEnum


class Profile(StrEnum):
    """Perfiles de plataforma expuestos por asusd."""

    QUIET = "Quiet"
    BALANCED = "Balanced"
    PERFORMANCE = "Performance"


class FanMode(StrEnum):
    """Modos de ventilación de Balanced, compatibles con ``alternar-ventilacion``."""

    NORMAL = "Normal"
    EXTRA = "Extra"
    ULTRA = "Ultra"
    ULTRA_MEGA = "Ultra Mega"


class Fan(StrEnum):
    """Ventiladores con curva configurable, con el nombre que imprime asusctl."""

    CPU = "CPU"
    GPU = "GPU"
    MID = "MID"


class Brightness(Enum):
    """Niveles de brillo compartido del teclado y la iluminación."""

    OFF = ("off", "Off", "Apagado")
    LOW = ("low", "Low", "Bajo")
    MEDIUM = ("med", "Med", "Medio")
    HIGH = ("high", "High", "Alto")

    def __init__(self, argument: str, reported: str, label: str) -> None:
        self.argument = argument
        self.reported = reported
        self.label = label


class ChargeLimit(IntEnum):
    """Límites de carga ofrecidos en el panel."""

    ECO = 60
    BALANCED = 80
    FULL = 100


@dataclass(frozen=True)
class FanCurve:
    """Curva de un ventilador tal como la reporta asusctl."""

    fan: Fan
    pwm: tuple[int, ...]
    temps: tuple[int, ...]
    enabled: bool


@dataclass(frozen=True)
class LightbarState:
    """Estados de energía de la cinta LED en asusd."""

    boot: bool
    awake: bool
    sleep: bool
    shutdown: bool


@dataclass(frozen=True)
class BatteryStatus:
    """Estado de la batería leído de sysfs."""

    percent: int | None
    ac_online: bool | None
    charging_state: str | None


@dataclass(frozen=True)
class SensorReadings:
    """Temperatura del paquete CPU y RPM de los ventiladores."""

    cpu_package_temp: float | None = None
    cpu_fan_rpm: int | None = None
    gpu_fan_rpm: int | None = None
    mid_fan_rpm: int | None = None


@dataclass(frozen=True)
class FanStatus:
    """Estado de las curvas de Balanced; ``mode`` es ``None`` si son personalizadas."""

    mode: FanMode | None


@dataclass(frozen=True)
class HardwareState:
    """Fotografía del hardware. ``None`` significa «No disponible»."""

    profile: Profile | None = None
    fans: FanStatus | None = None
    brightness: Brightness | None = None
    lightbar: LightbarState | None = None
    charge_limit: int | None = None
    battery: BatteryStatus | None = None
    sensors: SensorReadings = field(default_factory=SensorReadings)

    @property
    def asusd_available(self) -> bool:
        return self.profile is not None
