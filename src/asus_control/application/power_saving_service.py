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
from asus_control.domain.power_saving import (
    PowerSavingCheck,
    PowerSavingInspection,
    PowerSavingSession,
)


class PowerSavingService:
    def __init__(
        self,
        device: PowerSavingDevice,
        store: PowerSavingStore,
        lock: FanLock,
        hardware_lock: FanLock = nullcontext,
        retired_keys: tuple[str, ...] = (),
    ) -> None:
        self._device = device
        self._store = store
        self._lock = lock
        self._hardware_lock = hardware_lock
        self._retired_keys = retired_keys

    def status(self) -> PowerSavingSession | None:
        """Read only: displaying the applet must never apply a setting."""
        return self._store.load()

    def inspect(self) -> PowerSavingInspection:
        """Verify real values without writing or trusting yesterday's confirmation."""
        session = self._store.load()
        if session is None:
            return PowerSavingInspection(None)
        checks = []
        for setting in session.settings:
            expected = (
                setting.target
                if session.enabled and setting.key not in self._retired_keys
                else setting.original
            )
            try:
                actual = self._device.read(setting.key)
            except HardwareAccessError as exc:
                checks.append(PowerSavingCheck(setting.key, expected, None, str(exc)))
            else:
                checks.append(PowerSavingCheck(setting.key, expected, actual))
        return PowerSavingInspection(session, tuple(checks))

    def set_enabled(self, enabled: bool) -> None:
        with self._lock(), self._hardware_lock():
            session = self._store.load()
            if session is None:
                if not enabled:
                    return
                capture = self._device.capture()
                session = PowerSavingSession(
                    enabled=True,
                    settings=capture.settings,
                    pending=tuple(
                        setting.key
                        for setting in capture.settings
                        if setting.original != setting.target
                    ),
                    unavailable=capture.unavailable,
                )
            else:
                session = replace(
                    session,
                    enabled=enabled,
                    pending=(
                        session.pending
                        if session.enabled == enabled
                        else tuple(setting.key for setting in session.settings)
                    ),
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
    def manual_control(self, *, unmanaged: bool = False) -> Iterator[None]:
        with self._lock():
            if not unmanaged:
                self.require_manual_control()
            yield

    def _apply(self, session: PowerSavingSession) -> None:
        # Removed settings must be restored last: reloading the desktop policy can
        # otherwise overwrite the restored brightness before its backup is retired.
        session = replace(
            session,
            settings=tuple(s for s in session.settings if s.key not in self._retired_keys)
            + tuple(s for s in session.settings if s.key in self._retired_keys),
        )
        pending = list(session.pending)
        if session.enabled:
            pending = self._unconfirmed_targets(session)
            if not pending:
                retained = tuple(s for s in session.settings if s.key not in self._retired_keys)
                if session.pending or session.errors or retained != session.settings:
                    self._store.save(
                        replace(session, settings=retained, pending=(), errors=())
                        if retained
                        else None
                    )
                return
            session = replace(session, pending=tuple(pending), errors=())
            self._store.save(session)
        errors: list[str] = []
        for setting in session.settings:
            if setting.key not in pending:
                continue
            value = (
                setting.target
                if session.enabled and setting.key not in self._retired_keys
                else setting.original
            )
            try:
                if setting.key in session.pending or self._device.read(setting.key) != value:
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
        session = replace(
            session,
            settings=tuple(
                s for s in session.settings if s.key not in self._retired_keys or s.key in pending
            ),
            pending=tuple(pending),
            errors=tuple(errors),
        )
        self._store.save(session if session.settings else None)
        if not session.enabled and not pending:
            self._store.save(None)
        elif errors:
            raise HardwareAccessError("; ".join(errors))

    def _unconfirmed_targets(self, session: PowerSavingSession) -> list[str]:
        pending = []
        for setting in session.settings:
            if setting.key in session.pending:
                pending.append(setting.key)
                continue
            try:
                expected = (
                    setting.target if setting.key not in self._retired_keys else setting.original
                )
                if self._device.read(setting.key) == expected:
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
                expected = (
                    setting.target
                    if session.enabled and setting.key not in self._retired_keys
                    else setting.original
                )
                if self._device.read(setting.key) != expected:
                    raise HardwareAccessError("Confirmed value changed again")
            except HardwareAccessError as exc:
                pending.append(setting.key)
                errors.append(f"{setting.key}: {exc}")
