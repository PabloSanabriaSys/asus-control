from pathlib import Path

import pytest

from asus_control.domain.errors import HardwareAccessError
from asus_control.domain.power_saving import PowerSavingSession, SavedSetting
from asus_control.infrastructure.power_saving_store import FilePowerSavingStore


def test_atomic_private_snapshot_round_trip(tmp_path: Path) -> None:
    store = FilePowerSavingStore(tmp_path / "private/state.json")
    original = PowerSavingSession(
        True, (SavedSetting("profile", "Balanced", "Quiet"),), ("profile",), ("gpu.manual",), ()
    )
    store.save(original)
    assert store.load() == original
    assert store.path.stat().st_mode & 0o777 == 0o600
    assert store.path.parent.stat().st_mode & 0o777 == 0o700
    assert not list(store.path.parent.glob(".power-saving-*"))
    store.save(None)
    assert store.load() is None


@pytest.mark.parametrize(
    "text", ["", "{}", "null", '{"version":1,"session":{}}', '{"version":2,"session":null}']
)
def test_malformed_state_fails_closed(tmp_path: Path, text: str) -> None:
    path = tmp_path / "state.json"
    path.write_text(text)
    with pytest.raises(HardwareAccessError):
        FilePowerSavingStore(path).load()
