"""Entrada de inicio automático XDG (``~/.config/autostart``)."""

from __future__ import annotations

import os
import sys
from collections.abc import Sequence
from pathlib import Path

APP_ID = "asus-control"
DESKTOP_FILE = f"{APP_ID}.desktop"
_DESKTOP_RESERVED = ('"', "`", "$", "\\")


def config_home() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")


def default_launch_command() -> list[str]:
    """Lanzador instalado si existe; si no, el intérprete actual (modo desarrollo)."""
    launcher = Path.home() / ".local" / "bin" / APP_ID
    if launcher.is_file():
        return [str(launcher)]
    return [sys.executable, "-m", "asus_control"]


class Autostart:
    """Crea o elimina la entrada de autostart; su existencia es el estado."""

    def __init__(self, autostart_dir: Path, command: Sequence[str]) -> None:
        self._path = autostart_dir / DESKTOP_FILE
        self._command = list(command)

    @property
    def path(self) -> Path:
        return self._path

    def is_enabled(self) -> bool:
        return self._path.is_file()

    def set_enabled(self, enabled: bool) -> None:
        if enabled:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(self._render())
        else:
            self._path.unlink(missing_ok=True)

    def _render(self) -> str:
        return (
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Name=ASUS Control\n"
            "Comment=Controles de hardware ASUS en la bandeja del sistema\n"
            f"Exec={_desktop_exec(self._command)}\n"
            f"Icon={APP_ID}\n"
            "Terminal=false\n"
            "X-GNOME-Autostart-enabled=true\n"
            "X-KDE-autostart-phase=2\n"
        )


def _desktop_exec(command: Sequence[str]) -> str:
    """Cita los argumentos según la especificación Desktop Entry."""
    return " ".join(_quote(argument) for argument in command)


def _quote(argument: str) -> str:
    if argument and not any(char in argument for char in " \t\n\"'\\><~|&;$*?#()`"):
        return argument
    escaped = "".join(f"\\{char}" if char in _DESKTOP_RESERVED else char for char in argument)
    return f'"{escaped}"'
