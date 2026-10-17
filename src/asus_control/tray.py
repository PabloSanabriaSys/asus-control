"""Icono de bandeja y su menú contextual."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from asus_control.models import Profile

APP_NAME = "ASUS Control"


class Tray(QObject):
    """Un clic alterna el panel; el menú ofrece abrir, inicio automático y salir."""

    toggle_requested = Signal()
    open_requested = Signal()
    autostart_toggled = Signal(bool)
    quit_requested = Signal()

    def __init__(self, icon: QIcon, autostart_enabled: bool, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._menu = QMenu()
        open_action = self._menu.addAction("Abrir")
        open_action.triggered.connect(self.open_requested)
        self._autostart = QAction("Inicio automático", self._menu)
        self._autostart.setCheckable(True)
        self._autostart.setChecked(autostart_enabled)
        self._autostart.toggled.connect(self.autostart_toggled)
        self._menu.addAction(self._autostart)
        self._menu.addSeparator()
        quit_action = self._menu.addAction("Salir")
        quit_action.triggered.connect(self.quit_requested)

        self._icon = QSystemTrayIcon(icon, self)
        self._icon.setContextMenu(self._menu)
        self._icon.activated.connect(self._on_activated)
        self.show_profile(None)

    def show(self) -> None:
        self._icon.show()

    def hide(self) -> None:
        self._icon.hide()

    def set_autostart_checked(self, enabled: bool) -> None:
        self._autostart.blockSignals(True)
        self._autostart.setChecked(enabled)
        self._autostart.blockSignals(False)

    def show_profile(self, profile: Profile | None) -> None:
        detail = f"Perfil {profile.value}" if profile else "asusd no disponible"
        self._icon.setToolTip(f"{APP_NAME} · {detail}")

    def notify(self, message: str, *, is_error: bool) -> None:
        kind = (
            QSystemTrayIcon.MessageIcon.Warning
            if is_error
            else QSystemTrayIcon.MessageIcon.Information
        )
        self._icon.showMessage(APP_NAME, message, kind)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason is QSystemTrayIcon.ActivationReason.Trigger:
            self.toggle_requested.emit()
