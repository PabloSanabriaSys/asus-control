"""Persist intent before writing; retain the original snapshot until restoration succeeds."""

from collections.abc import Iterator
from contextlib import contextmanager, nullcontext
from dataclasses import replace

from asus_control.application.ports import (
    FanLock,
    PowerSavingDevice,
    PowerSavingStore,
)
from asus_control.domain.errors import HardwareAccessError
from asus_control.domain.power_saving import PowerSavingSession


class PowerSavingService:
    def __init__(
        self,
        device: PowerSavingDevice,
        store: PowerSavingStore,
        lock: FanLock,
        hardware_lock: FanLock = nullcontext,
    ) -> None:
        self._device = device
        self._store = store
        self._lock = lock
        self._hardware_lock = hardware_lock

    def status(self) -> PowerSavingSession | None:
        """Read only: displaying the applet must never apply a setting."""
        return self._store.load()

    def set_enabled(self, enabled: bool, brightness_percent: int = 30) -> None:
        with self._lock(), self._hardware_lock():
            session = self._store.load()
            if session is None:
                if not enabled:
                    return
                capture = self._device.capture(brightness_percent)
                session = PowerSavingSession(
                    enabled=True,
                    settings=capture.settings,
                    pending=tuple(setting.key for setting in capture.settings),
                    unavailable=capture.unavailable,
                )
            else:
                session = replace(
                    session,
                    enabled=enabled,
                    pending=tuple(setting.key for setting in session.settings),
                    errors=(),
                )
            # This must succeed BEFORE the first hardware write, including when disabling.
            self._store.save(session)
            self._apply(session)

    def reconcile(self) -> None:
        """Resume a saved operation after login, wakeup, AC changes or a crash."""
        with self._lock(), self._hardware_lock():
            session = self._store.load()
            if session is not None:
                self._apply(session)

    def require_manual_control(self) -> None:
        if self._store.load() is not None:
            raise HardwareAccessError(
                "Turn off battery saving and finish restoring settings first."
            )

    @contextmanager
    def manual_control(self) -> Iterator[None]:
        with self._lock():
            self.require_manual_control()
            yield

    def _apply(self, session: PowerSavingSession) -> None:
        pending = list(session.pending)
        if session.enabled:
            pending = self._unconfirmed_targets(session)
            if not pending:
                if session.pending or session.errors:
                    self._store.save(replace(session, pending=(), errors=()))
                return
            session = replace(session, pending=tuple(pending), errors=())
            self._store.save(session)
        errors: list[str] = []
        for setting in session.settings:
            if setting.key not in pending:
                continue
            value = setting.target if session.enabled else setting.original
            try:
                if self._device.read(setting.key) != value:
                    self._device.write(setting.key, value)
                if self._device.read(setting.key) != value:
                    raise HardwareAccessError(f"Unconfirmed setting: {setting.key}")
            except HardwareAccessError as exc:
                errors.append(f"{setting.key}: {exc}")
            else:
                pending.remove(setting.key)
            session = replace(session, pending=tuple(pending), errors=tuple(errors))
            self._store.save(session)
        self._verify_configuration(session, pending, errors)
        self._store.save(replace(session, pending=tuple(pending), errors=tuple(errors)))
        if not session.enabled and not pending:
            self._store.save(None)
        elif errors:
            raise HardwareAccessError("; ".join(errors))

    def _unconfirmed_targets(self, session: PowerSavingSession) -> list[str]:
        pending = []
        for setting in session.settings:
            try:
                if self._device.read(setting.key) == setting.target:
                    continue
            except HardwareAccessError:
                pass
            pending.append(setting.key)
        return pending

    def _verify_configuration(
        self, session: PowerSavingSession, pending: list[str], errors: list[str]
    ) -> None:
        # Policy reloads can affect settings restored by an earlier attempt. Never
        # discard the snapshot until the complete original configuration is confirmed.
        for setting in session.settings:
            if setting.key in pending:
                continue
            try:
                expected = setting.target if session.enabled else setting.original
                if self._device.read(setting.key) != expected:
                    raise HardwareAccessError("Confirmed value changed again")
            except HardwareAccessError as exc:
                pending.append(setting.key)
                errors.append(f"{setting.key}: {exc}")
