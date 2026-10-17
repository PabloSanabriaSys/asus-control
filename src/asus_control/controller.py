"""Coordinación entre la interfaz y ``HardwareService``."""

from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import Future
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QObject, Signal

from asus_control.errors import AsusControlError
from asus_control.hardware import HardwareService
from asus_control.models import Brightness, FanMode, HardwareState, Profile
from asus_control.tasks import TaskRunner

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _ActionOutcome:
    error: str | None
    state: HardwareState


class HardwareController(QObject):
    """Lanza lecturas y acciones en segundo plano y publica los resultados como señales."""

    state_changed = Signal(object)
    """``HardwareState`` tras cada lectura completa."""
    profile_checked = Signal(object)
    """``Profile | None`` tras cada comprobación ligera en segundo plano."""
    busy_changed = Signal(bool)
    notice = Signal(str, bool)
    """Mensaje para el usuario y si se trata de un error."""

    def __init__(
        self, service: HardwareService, tasks: TaskRunner, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._tasks = tasks
        self._refresh_pending = False
        self._busy = False
        self._last_profile: Profile | None = None

    @property
    def busy(self) -> bool:
        return self._busy

    def refresh(self) -> None:
        if self._refresh_pending or self._busy:
            return
        self._refresh_pending = True
        self._tasks.submit(self._service.read_state, self._on_state_read)

    def check_profile(self) -> None:
        if self._busy:
            return
        self._tasks.submit(self._service.read_profile, self._on_profile_read)

    def set_profile(self, profile: Profile) -> None:
        self._perform(lambda: self._service.set_profile(profile), f"Perfil {profile} activo.")

    def set_fan_mode(self, mode: FanMode) -> None:
        self._perform(lambda: self._service.set_fan_mode(mode), f"Ventilación {mode} activa.")

    def set_brightness(self, level: Brightness) -> None:
        self._perform(lambda: self._service.set_brightness(level), f"Iluminación: {level.label}.")

    def set_charge_limit(self, percent: int) -> None:
        self._perform(
            lambda: self._service.set_charge_limit(percent), f"Límite de carga: {percent} %."
        )

    def set_lightbar(self, on: bool) -> None:
        label = "encendida" if on else "apagada"
        self._perform(lambda: self._service.set_lightbar(on), f"Cinta LED {label}.")

    def _perform(self, action: Callable[[], None], success: str) -> None:
        if self._busy:
            return
        self._set_busy(True)

        def job() -> _ActionOutcome:
            try:
                action()
            except AsusControlError as exc:
                return _ActionOutcome(str(exc), self._service.read_state())
            return _ActionOutcome(None, self._service.read_state())

        def done(future: Future[_ActionOutcome]) -> None:
            self._set_busy(False)
            if self._failed(future):
                return
            outcome = future.result()
            self.notice.emit(outcome.error or success, outcome.error is not None)
            self._publish(outcome.state)

        self._tasks.submit(job, done)

    def _on_state_read(self, future: Future[HardwareState]) -> None:
        self._refresh_pending = False
        if not self._failed(future):
            self._publish(future.result())

    def _on_profile_read(self, future: Future[Profile | None]) -> None:
        if self._failed(future):
            return
        profile = future.result()
        self.profile_checked.emit(profile)
        if profile != self._last_profile:
            # Cambio externo (otra herramienta o la conexión a corriente): leer todo.
            self.refresh()

    def _publish(self, state: HardwareState) -> None:
        self._last_profile = state.profile
        self.state_changed.emit(state)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.busy_changed.emit(busy)

    def _failed(self, future: Future[Any]) -> bool:
        """Informa de errores no previstos (fallos de programación) sin cerrar la aplicación."""
        error = future.exception()
        if error is None:
            return False
        logger.error("Error inesperado", exc_info=error)
        self.notice.emit(f"Error inesperado: {error}", True)
        return True
