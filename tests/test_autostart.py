from __future__ import annotations

from pathlib import Path

from asus_control.autostart import Autostart


def test_enable_and_disable(tmp_path: Path) -> None:
    autostart = Autostart(tmp_path / "autostart", ["/home/u/.local/bin/asus-control"])

    assert not autostart.is_enabled()
    autostart.set_enabled(True)
    assert autostart.is_enabled()
    content = autostart.path.read_text()
    assert "Exec=/home/u/.local/bin/asus-control\n" in content
    assert "Type=Application" in content

    autostart.set_enabled(False)
    assert not autostart.is_enabled()
    autostart.set_enabled(False)


def test_exec_arguments_are_quoted(tmp_path: Path) -> None:
    autostart = Autostart(tmp_path, ["/opt/my app/python", "-m", "asus_control"])

    autostart.set_enabled(True)

    assert 'Exec="/opt/my app/python" -m asus_control\n' in autostart.path.read_text()
