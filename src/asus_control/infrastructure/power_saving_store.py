"""Versioned snapshot, private permissions, atomic replacement and fsync."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path

from asus_control.domain.errors import HardwareAccessError
from asus_control.domain.power_saving import PowerSavingSession, SavedSetting


def default_state_path() -> Path:
    root = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state")))
    return root / "asus-control" / "power-saving.json"


class FilePowerSavingStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> PowerSavingSession | None:
        try:
            raw = json.loads(self.path.read_text())
            if raw.get("version") != 1:
                raise ValueError("Unsupported snapshot version")
            data = raw["session"]
            if data is None:
                return None
            if type(data["enabled"]) is not bool:
                raise ValueError("Invalid enabled flag")
            settings = tuple(SavedSetting(**item) for item in data["settings"])
            if not settings or any(
                not all(isinstance(value, str) for value in (s.key, s.original, s.target))
                for s in settings
            ):
                raise ValueError("Invalid saved settings")
            keys = [s.key for s in settings]
            if len(keys) != len(set(keys)) or not set(data["pending"]) <= set(keys):
                raise ValueError("Invalid pending settings")
            for name in ("pending", "unavailable", "errors"):
                if not isinstance(data[name], list) or any(
                    not isinstance(item, str) for item in data[name]
                ):
                    raise ValueError(f"Invalid {name}")
            return PowerSavingSession(
                data["enabled"],
                settings,
                tuple(data["pending"]),
                tuple(data["unavailable"]),
                tuple(data["errors"]),
            )
        except FileNotFoundError:
            return None
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            raise HardwareAccessError(f"Cannot read battery-saving backup: {exc}") from exc

    def save(self, session: PowerSavingSession | None) -> None:
        temporary: str | None = None
        try:
            self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w", dir=self.path.parent, prefix=".power-saving-", delete=False
            ) as handle:
                temporary = handle.name
                json.dump({"version": 1, "session": asdict(session) if session else None}, handle)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            Path(temporary).replace(self.path)
            with _directory(self.path.parent) as fd:
                os.fsync(fd)
        except OSError as exc:
            raise HardwareAccessError(f"Cannot save battery-saving backup: {exc}") from exc
        finally:
            if temporary is not None:
                Path(temporary).unlink(missing_ok=True)


@contextmanager
def _directory(path: Path) -> Iterator[int]:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        yield fd
    finally:
        os.close(fd)
