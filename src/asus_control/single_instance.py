"""Una sola instancia por sesión: las siguientes piden a la primera que muestre el panel."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from PySide6.QtCore import QLockFile, QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

logger = logging.getLogger(__name__)

_SHOW_REQUEST = b"show\n"
_CONNECT_TIMEOUT_MS = 1000


def session_key(app_id: str) -> str:
    session = os.environ.get("XDG_SESSION_ID") or os.environ.get("WAYLAND_DISPLAY") or "default"
    return f"{app_id}-{os.getuid()}-{session}"


class SingleInstance(QObject):
    """Bloqueo de sesión más un socket local para reenviar la petición de mostrar."""

    show_requested = Signal()

    def __init__(self, key: str, runtime_dir: Path, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._key = key
        self._lock = QLockFile(str(runtime_dir / f"{key}.lock"))
        self._lock.setStaleLockTime(0)
        self._server = QLocalServer(self)
        self._server.newConnection.connect(self._accept)

    def acquire(self) -> bool:
        """``True`` si esta es la instancia principal; si no, avisa a la existente."""
        if not self._lock.tryLock(0):
            self._notify_running_instance()
            return False
        QLocalServer.removeServer(self._key)
        if not self._server.listen(self._key):
            logger.warning("No se pudo escuchar en %s: %s", self._key, self._server.errorString())
        return True

    def _notify_running_instance(self) -> None:
        socket = QLocalSocket()
        socket.connectToServer(self._key)
        if socket.waitForConnected(_CONNECT_TIMEOUT_MS):
            socket.write(_SHOW_REQUEST)
            socket.waitForBytesWritten(_CONNECT_TIMEOUT_MS)
            socket.disconnectFromServer()

    def _accept(self) -> None:
        while (connection := self._server.nextPendingConnection()) is not None:
            connection.readyRead.connect(lambda c=connection: self._read(c))
            connection.disconnected.connect(connection.deleteLater)

    def _read(self, connection: QLocalSocket) -> None:
        if _SHOW_REQUEST in bytes(connection.readAll().data()):
            self.show_requested.emit()
