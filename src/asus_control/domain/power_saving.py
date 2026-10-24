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
