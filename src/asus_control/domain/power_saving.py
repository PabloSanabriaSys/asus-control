"""Durable, reversible power-saving operations (no hardware or filesystem access)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SavedSetting:
    key: str
    original: str
    target: str


@dataclass(frozen=True)
class PowerSavingSession:
    enabled: bool
    settings: tuple[SavedSetting, ...]
    pending: tuple[str, ...]
    unavailable: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class PowerSavingCapture:
    settings: tuple[SavedSetting, ...]
    unavailable: tuple[str, ...] = ()


@dataclass(frozen=True)
class PowerSavingCheck:
    key: str
    expected: str
    actual: str | None
    error: str | None = None
    restart_required: bool = False

    @property
    def confirmed(self) -> bool:
        return self.actual == self.expected and self.error is None


@dataclass(frozen=True)
class PowerSavingInspection:
    session: PowerSavingSession | None
    checks: tuple[PowerSavingCheck, ...] = ()


@dataclass(frozen=True)
class PowerSavingMigration:
    retired_keys: tuple[str, ...] = ()
    added_keys: tuple[str, ...] = ()
