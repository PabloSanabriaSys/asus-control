"""Ejecución de órdenes externas: sin shell, con argumentos separados y tiempo límite."""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Sequence
from typing import Protocol

from asus_control.infrastructure.errors import CommandError

logger = logging.getLogger(__name__)

BUSCTL = "/usr/bin/busctl"
COMMAND_TIMEOUT_SECONDS = 10.0


class CommandRunner(Protocol):
    """Ejecuta una orden con argumentos separados y devuelve su salida estándar."""

    def __call__(self, args: Sequence[str]) -> str: ...


class SubprocessRunner:
    """Ejecuta un programa fijo; cualquier fallo se convierte en ``CommandError``."""

    def __init__(self, executable: str, timeout: float = COMMAND_TIMEOUT_SECONDS) -> None:
        self._executable = executable
        self._timeout = timeout

    def __call__(self, args: Sequence[str]) -> str:
        command = [self._executable, *args]
        logger.debug("Running %s", command)
        try:
            completed = subprocess.run(
                command, check=True, capture_output=True, text=True, timeout=self._timeout
            )
        except FileNotFoundError as exc:
            raise CommandError(f"{self._executable} not found.") from exc
        except subprocess.TimeoutExpired as exc:
            raise CommandError(f"{' '.join(command)} timed out.") from exc
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or "").strip()
            raise CommandError(f"{' '.join(command)} failed: {detail}") from exc
        return completed.stdout
