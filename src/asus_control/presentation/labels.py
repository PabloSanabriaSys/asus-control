"""Textos en español para el usuario."""

from __future__ import annotations

from asus_control.domain.models import Brightness

BRIGHTNESS_LABELS = {
    Brightness.OFF: "Apagado",
    Brightness.LOW: "Bajo",
    Brightness.MEDIUM: "Medio",
    Brightness.HIGH: "Alto",
}

CHARGING_STATE_LABELS = {
    "Charging": "Cargando",
    "Discharging": "Descargando",
    "Not charging": "Sin cargar",
    "Full": "Completa",
}
"""Valores de ``/sys/class/power_supply/*/status``."""
