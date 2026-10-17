"""Panel compacto con el estado y los controles."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Generic, TypeVar

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCloseEvent, QHideEvent, QIcon, QShowEvent
from PySide6.QtWidgets import (
    QButtonGroup,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from asus_control.models import (
    BatteryStatus,
    Brightness,
    ChargeLimit,
    FanMode,
    FanStatus,
    HardwareState,
    Profile,
    SensorReadings,
)

UNAVAILABLE = "No disponible"
PANEL_WIDTH = 380
ERROR_COLOR = "#d0302f"

_CHARGING_STATES = {
    "Charging": "Cargando",
    "Discharging": "Descargando",
    "Not charging": "Sin cargar",
    "Full": "Completa",
}

V = TypeVar("V")


class OptionGroup(QGroupBox, Generic[V]):
    """Botones exclusivos. Solo se marcan con el estado leído, nunca de forma optimista."""

    selected = Signal(object)

    def __init__(self, title: str, options: Sequence[tuple[V, str]]) -> None:
        super().__init__(title)
        self._values: list[V] = []
        self._group = QButtonGroup(self)
        self._group.setExclusive(False)
        self._status = QLabel()
        self._status.setVisible(False)
        buttons = QHBoxLayout()
        buttons.setSpacing(4)
        for index, (value, label) in enumerate(options):
            button = QPushButton(label)
            button.setCheckable(True)
            self._group.addButton(button, index)
            buttons.addWidget(button)
            self._values.append(value)
        self._group.idClicked.connect(self._on_clicked)
        layout = QVBoxLayout(self)
        layout.addLayout(buttons)
        layout.addWidget(self._status)

    def set_current(self, value: V | None) -> None:
        for index, option in enumerate(self._values):
            self._group.button(index).setChecked(value is not None and option == value)

    def set_status(self, text: str | None) -> None:
        self._status.setText(text or "")
        self._status.setVisible(bool(text))

    def _on_clicked(self, index: int) -> None:
        # Se deshace el cambio visual: el botón se marcará cuando la lectura lo confirme.
        button = self._group.button(index)
        button.setChecked(not button.isChecked())
        self.selected.emit(self._values[index])


class Panel(QWidget):
    """Ventana del panel. Cerrarla solo la oculta; la aplicación sigue en la bandeja."""

    visibility_changed = Signal(bool)
    profile_selected = Signal(object)
    fan_mode_selected = Signal(object)
    brightness_selected = Signal(object)
    lightbar_selected = Signal(object)
    charge_limit_selected = Signal(object)

    def __init__(self, icon: QIcon) -> None:
        super().__init__()
        self.setWindowTitle("ASUS Control")
        self.setWindowIcon(icon)
        self.setFixedWidth(PANEL_WIDTH)

        self._asusd_banner = QLabel("asusd no responde. Los controles están deshabilitados.")
        self._asusd_banner.setWordWrap(True)
        self._asusd_banner.setStyleSheet(f"color: {ERROR_COLOR}; font-weight: bold;")
        self._asusd_banner.setVisible(False)

        self._profile = OptionGroup[Profile]("Rendimiento", [(p, p.value) for p in Profile])
        self._fans = OptionGroup[FanMode]("Ventilación", [(m, m.value) for m in FanMode])
        self._lighting = OptionGroup[Brightness](
            "Iluminación", [(level, level.label) for level in Brightness]
        )
        self._lightbar = OptionGroup[bool]("Cinta LED", [(False, "Apagada"), (True, "Encendida")])
        self._charge = OptionGroup[int](
            "Límite de carga", [(int(limit), f"{int(limit)} %") for limit in ChargeLimit]
        )
        self._battery = QLabel(UNAVAILABLE)
        self._sensor_labels = {
            name: QLabel(UNAVAILABLE)
            for name in (
                "Temperatura CPU",
                "Ventilador CPU",
                "Ventilador GPU",
                "Ventilador central",
            )
        }
        self._message = QLabel()
        self._message.setWordWrap(True)

        self._profile.selected.connect(self.profile_selected)
        self._fans.selected.connect(self.fan_mode_selected)
        self._lighting.selected.connect(self.brightness_selected)
        self._lightbar.selected.connect(self.lightbar_selected)
        self._charge.selected.connect(self.charge_limit_selected)

        layout = QVBoxLayout(self)
        for widget in (
            self._asusd_banner,
            self._profile,
            self._fans,
            self._lighting,
            self._lightbar,
            self._battery_box(),
            self._sensors_box(),
            self._message,
        ):
            layout.addWidget(widget)
        self._busy = False
        self._state = HardwareState()
        self.show_state(self._state)

    def show_state(self, state: HardwareState) -> None:
        self._state = state
        available = state.asusd_available
        self._asusd_banner.setVisible(not available)

        self._profile.set_current(state.profile)
        self._profile.set_status(None if available else UNAVAILABLE)

        # Ventilación solo existe en Balanced; nunca se cambia el perfil para mostrarla.
        self._fans.setVisible(state.profile is Profile.BALANCED)
        self._fans.set_current(state.fans.mode if state.fans else None)
        self._fans.set_status(_fan_status(state.fans))

        self._lighting.set_current(state.brightness)
        self._lighting.set_status(None if state.brightness else UNAVAILABLE)

        self._lightbar.setVisible(state.lightbar is not None)
        self._lightbar.set_current(state.lightbar.awake if state.lightbar else None)

        self._charge.set_current(state.charge_limit)
        self._charge.set_status(_charge_status(state.charge_limit))
        self._battery.setText(_battery_text(state.battery))
        self._show_sensors(state.sensors)
        self._update_enabled()
        # Al ocultar secciones (ventilación, cinta) la ventana se encoge.
        self.adjustSize()

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        self._update_enabled()
        if busy:
            self.show_message("Aplicando…", is_error=False)

    def show_message(self, text: str, *, is_error: bool) -> None:
        self._message.setText(text)
        self._message.setStyleSheet(f"color: {ERROR_COLOR};" if is_error else "")

    def _update_enabled(self) -> None:
        state = self._state
        idle = not self._busy and state.asusd_available
        self._profile.setEnabled(idle)
        self._fans.setEnabled(idle and state.fans is not None)
        self._lighting.setEnabled(idle and state.brightness is not None)
        self._lightbar.setEnabled(idle and state.lightbar is not None)
        self._charge.setEnabled(idle and state.charge_limit is not None)

    def _battery_box(self) -> QGroupBox:
        box = QGroupBox("Batería")
        layout = QVBoxLayout(box)
        layout.addWidget(self._battery)
        layout.addWidget(self._charge)
        self._charge.setFlat(True)
        return box

    def _sensors_box(self) -> QGroupBox:
        box = QGroupBox("Sensores")
        form = QFormLayout(box)
        for name, label in self._sensor_labels.items():
            label.setAlignment(Qt.AlignmentFlag.AlignRight)
            form.addRow(name, label)
        return box

    def _show_sensors(self, sensors: SensorReadings) -> None:
        temp = sensors.cpu_package_temp
        values = (
            UNAVAILABLE if temp is None else f"{temp:.0f} °C",
            _rpm(sensors.cpu_fan_rpm),
            _rpm(sensors.gpu_fan_rpm),
            _rpm(sensors.mid_fan_rpm),
        )
        for label, value in zip(self._sensor_labels.values(), values, strict=True):
            label.setText(value)

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 (API de Qt)
        super().showEvent(event)
        self.visibility_changed.emit(True)

    def hideEvent(self, event: QHideEvent) -> None:  # noqa: N802 (API de Qt)
        super().hideEvent(event)
        self.visibility_changed.emit(False)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 (API de Qt)
        event.ignore()
        self.hide()


def _fan_status(fans: FanStatus | None) -> str | None:
    if fans is None:
        return UNAVAILABLE
    if fans.mode is None:
        return "Curvas personalizadas activas."
    return None


def _charge_status(limit: int | None) -> str | None:
    if limit is None:
        return UNAVAILABLE
    if limit not in set(ChargeLimit):
        return f"Límite actual: {limit} %"
    return None


def _battery_text(battery: BatteryStatus | None) -> str:
    if battery is None:
        return f"Batería: {UNAVAILABLE}"
    percent = UNAVAILABLE if battery.percent is None else f"{battery.percent} %"
    if battery.ac_online is None:
        power = "Corriente: no disponible"
    else:
        power = "Conectado a corriente" if battery.ac_online else "Con batería"
    parts = [percent, power]
    if battery.charging_state:
        parts.append(_CHARGING_STATES.get(battery.charging_state, battery.charging_state))
    return " · ".join(parts)


def _rpm(value: int | None) -> str:
    return UNAVAILABLE if value is None else f"{value} RPM"
