from __future__ import annotations

import multiprocessing
from multiprocessing.synchronize import Event
from pathlib import Path

import pytest

from asus_control.domain.errors import LockBusyError
from asus_control.infrastructure.fan_lock import default_lock_path, fan_lock


def _hold_lock(path: Path, ready: Event, release: Event) -> None:
    with fan_lock(path):
        ready.set()
        release.wait(5)


def test_lock_is_exclusive_across_processes(tmp_path: Path) -> None:
    path = tmp_path / "alternar-ventilacion.lock"
    context = multiprocessing.get_context("fork")
    ready, release = context.Event(), context.Event()
    holder = context.Process(target=_hold_lock, args=(path, ready, release))
    holder.start()
    try:
        assert ready.wait(5)
        with pytest.raises(LockBusyError), fan_lock(path):
            pass
    finally:
        release.set()
        holder.join(5)

    with fan_lock(path):
        pass


def test_uses_the_same_path_as_alternar_ventilacion(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_RUNTIME_DIR", "/run/user/1000")
    assert default_lock_path() == Path("/run/user/1000/alternar-ventilacion.lock")
