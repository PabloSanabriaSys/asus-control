"""Implementación de ``FanLock``: ``flock`` compartido con ``~/.local/bin/alternar-ventilacion``."""

from __future__ import annotations

import fcntl
import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from asus_control.domain.errors import LockBusyError

LOCK_NAME = "alternar-ventilacion.lock"


def default_lock_path() -> Path:
    """Misma ruta que usa el script: ``$XDG_RUNTIME_DIR`` o ``/tmp``."""
    return Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / LOCK_NAME


@contextmanager
def fan_lock(path: Path, *, wait_seconds: float = 0.0) -> Iterator[None]:
    """Toma el bloqueo sin esperar; lanza ``LockBusyError`` si está ocupado."""
    with path.open("w") as handle:
        deadline = time.monotonic() + wait_seconds
        while True:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError as exc:
                if time.monotonic() >= deadline:
                    raise LockBusyError from exc
                time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)
