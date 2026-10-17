"""Ejecución en segundo plano con entrega del resultado en el hilo de la interfaz."""

from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, TypeVar

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)

T = TypeVar("T")


class TaskRunner(QObject):
    """Ejecuta tareas de una en una para que nunca coincidan dos órdenes de asusctl."""

    _finished = Signal(object, object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="hardware")
        # La señal se emite desde el hilo de trabajo; Qt la entrega en el hilo de este objeto.
        self._finished.connect(self._deliver)

    def submit(self, task: Callable[[], T], on_done: Callable[[Future[T]], None]) -> None:
        future = self._executor.submit(task)
        future.add_done_callback(lambda done: self._finished.emit(on_done, done))

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    @staticmethod
    def _deliver(on_done: Callable[[Future[Any]], None], future: Future[Any]) -> None:
        if future.cancelled():
            return
        on_done(future)
