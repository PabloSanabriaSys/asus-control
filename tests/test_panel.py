from __future__ import annotations

from dataclasses import replace

import pytest
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from asus_control.models import (
    BatteryStatus,
    Brightness,
    FanMode,
    FanStatus,
    HardwareState,
    LightbarState,
    Profile,
    SensorReadings,
)
from asus_control.panel import UNAVAILABLE, Panel

FULL_STATE = HardwareState(
    profile=Profile.BALANCED,
    fans=FanStatus(mode=FanMode.EXTRA),
    brightness=Brightness.MEDIUM,
    lightbar=LightbarState(boot=True, awake=True, sleep=False, shutdown=False),
    charge_limit=80,
    battery=BatteryStatus(percent=73, ac_online=True, charging_state="Not charging"),
    sensors=SensorReadings(
        cpu_package_temp=55.4, cpu_fan_rpm=2500, gpu_fan_rpm=0, mid_fan_rpm=2200
    ),
)


@pytest.fixture
def panel(qt_app: QApplication) -> Panel:
    panel = Panel(QIcon())
    panel.show()
    return panel


def button(panel: Panel, text: str) -> QPushButton:
    matches = [b for b in panel.findChildren(QPushButton) if b.text() == text]
    assert len(matches) == 1, text
    return matches[0]


def texts(panel: Panel) -> set[str]:
    return {label.text() for label in panel.findChildren(QLabel)}


def test_shows_real_state(panel: Panel) -> None:
    panel.show_state(FULL_STATE)

    assert button(panel, "Balanced").isChecked()
    assert button(panel, "Extra").isChecked()
    assert button(panel, "Medio").isChecked()
    assert button(panel, "Encendida").isChecked()
    assert button(panel, "80 %").isChecked()
    assert {"55 °C", "2500 RPM", "0 RPM", "73 % · Conectado a corriente · Sin cargar"} <= texts(
        panel
    )


@pytest.mark.parametrize("profile", [Profile.QUIET, Profile.PERFORMANCE])
def test_fan_section_only_visible_in_balanced(panel: Panel, profile: Profile) -> None:
    panel.show_state(FULL_STATE)
    assert button(panel, "Ultra Mega").isVisible()

    panel.show_state(replace(FULL_STATE, profile=profile, fans=None))

    assert not button(panel, "Ultra Mega").isVisible()


def test_unsupported_lightbar_is_hidden(panel: Panel) -> None:
    panel.show_state(replace(FULL_STATE, lightbar=None))

    assert not button(panel, "Encendida").isVisible()


def test_without_asusd_controls_are_disabled(panel: Panel) -> None:
    panel.show_state(HardwareState())

    assert not button(panel, "Quiet").isEnabled()
    assert not button(panel, "Alto").isEnabled()
    assert UNAVAILABLE in texts(panel)
    assert not button(panel, "Normal").isVisible()


def test_click_requests_change_without_optimistic_check(panel: Panel) -> None:
    panel.show_state(FULL_STATE)
    requested: list[object] = []
    panel.profile_selected.connect(requested.append)

    button(panel, "Performance").click()

    assert requested == [Profile.PERFORMANCE]
    assert not button(panel, "Performance").isChecked()
    assert button(panel, "Balanced").isChecked()


def test_busy_disables_controls(panel: Panel) -> None:
    panel.show_state(FULL_STATE)

    panel.set_busy(True)
    assert not button(panel, "Quiet").isEnabled()
    panel.set_busy(False)
    assert button(panel, "Quiet").isEnabled()


def test_closing_only_hides(panel: Panel) -> None:
    visibility: list[bool] = []
    panel.visibility_changed.connect(visibility.append)

    panel.close()

    assert not panel.isVisible()
    assert visibility == [False]
