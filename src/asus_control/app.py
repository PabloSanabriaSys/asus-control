"""Punto de entrada y composición de la aplicación."""

from __future__ import annotations

import logging
import os
import sys
from importlib.resources import as_file, files
from pathlib import Path

from PySide6.QtCore import QObject, QSettings, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from asus_control.autostart import APP_ID, Autostart, config_home, default_launch_command
from asus_control.commands import ASUSCTL, BUSCTL, AsusCtl, AuraBus, SubprocessRunner
from asus_control.controller import HardwareController
from asus_control.fan_lock import default_lock_path, fan_lock
from asus_control.fans import FanService
from asus_control.hardware import HardwareService
from asus_control.models import HardwareState
from asus_control.panel import Panel
from asus_control.sensors import SysfsSensors
from asus_control.single_instance import SingleInstance, session_key
from asus_control.tasks import TaskRunner
from asus_control.tray import Tray

logger = logging.getLogger(__name__)

PANEL_REFRESH_MS = 2_000
PROFILE_CHECK_MS = 10_000
_AUTOSTART_INITIALIZED = "autostart/initialized"


def build_service() -> HardwareService:
    asusctl = AsusCtl(SubprocessRunner(ASUSCTL))
    lock_path = default_lock_path()
    return HardwareService(
        asusctl,
        AuraBus(SubprocessRunner(BUSCTL)),
        FanService(asusctl, lambda: fan_lock(lock_path)),
        SysfsSensors(),
    )


def load_icon() -> QIcon:
    with as_file(files("asus_control") / "resources" / f"{APP_ID}.svg") as path:
        fallback = QIcon(str(path))
    return QIcon.fromTheme(APP_ID, fallback)


class AsusControlApp(QObject):
    """Conecta controlador, panel, bandeja y temporizadores."""

    def __init__(self, qt_app: QApplication, autostart: Autostart, settings: QSettings) -> None:
        super().__init__(qt_app)
        self._qt_app = qt_app
        self._autostart = autostart
        self._tasks = TaskRunner(self)
        self._controller = HardwareController(build_service(), self._tasks, self)
        icon = load_icon()
        self._panel = Panel(icon)
        self._tray = Tray(icon, autostart.is_enabled(), self)

        self._panel_timer = QTimer(self)
        self._panel_timer.setInterval(PANEL_REFRESH_MS)
        self._panel_timer.timeout.connect(self._controller.refresh)
        self._profile_timer = QTimer(self)
        self._profile_timer.setInterval(PROFILE_CHECK_MS)
        self._profile_timer.timeout.connect(self._check_profile_in_background)

        self._connect_signals()
        self._apply_default_autostart(settings)

    def start(self) -> None:
        """Muestra el icono y lee el estado; no escribe ningún ajuste de hardware."""
        self._tray.show()
        self._profile_timer.start()
        self._controller.refresh()
        if not QSystemTrayIcon.isSystemTrayAvailable():
            logger.warning("No hay bandeja del sistema; se muestra el panel directamente.")
            self.show_panel()

    def show_panel(self) -> None:
        self._panel.show()
        self._panel.raise_()
        self._panel.activateWindow()

    def _connect_signals(self) -> None:
        controller, panel, tray = self._controller, self._panel, self._tray
        controller.state_changed.connect(self._on_state)
        controller.profile_checked.connect(tray.show_profile)
        controller.busy_changed.connect(panel.set_busy)
        controller.notice.connect(self._on_notice)

        panel.visibility_changed.connect(self._on_panel_visibility)
        panel.profile_selected.connect(controller.set_profile)
        panel.fan_mode_selected.connect(controller.set_fan_mode)
        panel.brightness_selected.connect(controller.set_brightness)
        panel.lightbar_selected.connect(controller.set_lightbar)
        panel.charge_limit_selected.connect(controller.set_charge_limit)

        tray.toggle_requested.connect(self._toggle_panel)
        tray.open_requested.connect(self.show_panel)
        tray.autostart_toggled.connect(self._set_autostart)
        tray.quit_requested.connect(self._quit)

    def _apply_default_autostart(self, settings: QSettings) -> None:
        # Activado por defecto solo la primera vez; después se respeta la elección del usuario.
        if settings.value(_AUTOSTART_INITIALIZED, False, type=bool):
            return
        self._set_autostart(True)
        settings.setValue(_AUTOSTART_INITIALIZED, True)

    def _set_autostart(self, enabled: bool) -> None:
        try:
            self._autostart.set_enabled(enabled)
        except OSError as exc:
            logger.error("No se pudo cambiar el inicio automático: %s", exc)
            self._tray.notify("No se pudo cambiar el inicio automático.", is_error=True)
        self._tray.set_autostart_checked(self._autostart.is_enabled())

    def _toggle_panel(self) -> None:
        if self._panel.isVisible():
            self._panel.hide()
        else:
            self.show_panel()

    def _on_panel_visibility(self, visible: bool) -> None:
        if visible:
            self._controller.refresh()
            self._panel_timer.start()
        else:
            self._panel_timer.stop()

    def _check_profile_in_background(self) -> None:
        if not self._panel.isVisible():
            self._controller.check_profile()

    def _on_state(self, state: HardwareState) -> None:
        self._panel.show_state(state)
        self._tray.show_profile(state.profile)

    def _on_notice(self, message: str, is_error: bool) -> None:
        self._panel.show_message(message, is_error=is_error)
        if is_error and not self._panel.isVisible():
            self._tray.notify(message, is_error=True)

    def _quit(self) -> None:
        self._panel_timer.stop()
        self._profile_timer.stop()
        self._tasks.shutdown()
        self._tray.hide()
        self._qt_app.quit()


def main() -> int:
    logging.basicConfig(
        level=logging.DEBUG if os.environ.get("ASUS_CONTROL_DEBUG") else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    qt_app = QApplication(sys.argv)
    qt_app.setApplicationName(APP_ID)
    qt_app.setApplicationDisplayName("ASUS Control")
    qt_app.setDesktopFileName(APP_ID)
    qt_app.setQuitOnLastWindowClosed(False)

    runtime_dir = Path(os.environ.get("XDG_RUNTIME_DIR") or "/tmp")
    instance = SingleInstance(session_key(APP_ID), runtime_dir)
    if not instance.acquire():
        logger.info("ASUS Control ya está en ejecución; se mostró su panel.")
        return 0

    autostart = Autostart(config_home() / "autostart", default_launch_command())
    settings = QSettings(APP_ID, APP_ID)
    application = AsusControlApp(qt_app, autostart, settings)
    instance.show_requested.connect(application.show_panel)
    application.start()
    return qt_app.exec()
