"""Implementación de ``FanLock``: ``flock`` compartido con ``~/.local/bin/alternar-ventilacion``."""

from __future__ import annotations

import fcntl
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from asus_control.domain.errors import LockBusyError

LOCK_NAME = "alternar-ventilacion.lock"


def default_lock_path() -> Path:
    """Misma ruta que usa el script: ``$XDG_RUNTIME_DIR`` o ``/tmp``."""
    return Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / LOCK_NAME


@contextmanager
def fan_lock(path: Path) -> Iterator[None]:
    """Toma el bloqueo sin esperar; lanza ``LockBusyError`` si está ocupado."""
    with path.open("w") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise LockBusyError from exc
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)
