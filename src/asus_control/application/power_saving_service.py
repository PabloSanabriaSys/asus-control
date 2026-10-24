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
    PowerSavingMigration,
    PowerSavingSession,
)


class PowerSavingService:
    def __init__(
        self,
        device: PowerSavingDevice,
        store: PowerSavingStore,
        lock: FanLock,
        hardware_lock: FanLock = nullcontext,
        *,
        migration: PowerSavingMigration | None = None,
    ) -> None:
        self._device = device
        self._store = store
        self._lock = lock
        self._hardware_lock = hardware_lock
        migration = migration or PowerSavingMigration()
        self._retired_keys = migration.retired_keys
        self._added_keys = migration.added_keys

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
                restart = actual != expected and self._device.restart_required(
                    setting.key, expected
                )
            except HardwareAccessError as exc:
                checks.append(PowerSavingCheck(setting.key, expected, None, str(exc)))
            else:
                checks.append(
                    PowerSavingCheck(setting.key, expected, actual, restart_required=restart)
                )
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
                if enabled:
                    session = self._extend_session(session)
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
                if session.enabled:
                    session = self._extend_session(session)
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

    def _extend_session(self, session: PowerSavingSession) -> PowerSavingSession:
        """Add newly managed controls without replacing any existing original values."""
        present = {setting.key for setting in session.settings} | set(session.unavailable)
        missing = set(self._added_keys) - present
        if not missing:
            return session
        capture = self._device.capture()
        additions = tuple(setting for setting in capture.settings if setting.key in missing)
        unavailable = tuple(key for key in session.unavailable if not key.startswith("gpu."))
        unavailable += tuple(key for key in capture.unavailable if key in missing)
        session = replace(
            session,
            settings=session.settings + additions,
            pending=session.pending + tuple(s.key for s in additions if s.original != s.target),
            unavailable=unavailable,
        )
        self._store.save(session)  # Original values must be durable before the first write.
        return session

    def _apply(self, session: PowerSavingSession) -> None:
        had_errors = bool(session.errors)
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
            # A queued GPU transition is successful intent, but not an applied GPU mode.
            if pending and all(
                self._device.restart_required(s.key, s.target)
                for s in session.settings
                if s.key in pending
            ):
                self._clear_deferred_errors(session, had_errors)
                return
            self._store.save(session)
        elif pending and all(
            self._device.restart_required(s.key, s.original)
            for s in session.settings
            if s.key in pending
        ):
            self._clear_deferred_errors(session, had_errors)
            return
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
                if self._write_and_confirm(setting.key, value, setting.key in session.pending):
                    pending.remove(setting.key)
            except HardwareAccessError as exc:
                errors.append(f"{setting.key}: {exc}")
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

    def _clear_deferred_errors(self, session: PowerSavingSession, had_errors: bool) -> None:
        if had_errors:
            self._store.save(replace(session, errors=()))

    def _write_and_confirm(self, key: str, value: str, replay: bool) -> bool:
        if self._device.restart_required(key, value):
            return False
        if replay or self._device.read(key) != value:
            self._device.write(key, value)
        if self._device.read(key) == value:
            return True
        if self._device.restart_required(key, value):
            return False
        raise HardwareAccessError(f"Unconfirmed setting: {key}")

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
