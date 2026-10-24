"""Exercise install/uninstall in a temporary HOME, with host commands replaced."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]


@pytest.fixture
def isolated_home(tmp_path: Path) -> dict[str, str]:
    commands = tmp_path / "commands"
    commands.mkdir()
    mocks = {
        "systemctl": '#!/bin/sh\nprintf "%s\\n" "$*" >> "$LIFECYCLE_LOG"\n',
        "kpackagetool6": '#!/bin/sh\ncase "$*" in *--show*) exit 1;; esac\n',
        "pkill": "#!/bin/sh\nexit 0\n",
        "busctl": "#!/bin/sh\nexit 0\n",
        "kbuildsycoca6": "#!/bin/sh\nexit 0\n",
        "update-desktop-database": "#!/bin/sh\nexit 0\n",
    }
    for name, contents in mocks.items():
        script = commands / name
        script.write_text(contents)
        script.chmod(0o755)
    return dict(
        os.environ,
        HOME=str(tmp_path / "home"),
        XDG_CONFIG_HOME=str(tmp_path / "config"),
        XDG_DATA_HOME=str(tmp_path / "data"),
        XDG_STATE_HOME=str(tmp_path / "state"),
        PATH=f"{commands}:{os.environ['PATH']}",
        LIFECYCLE_LOG=str(tmp_path / "commands.log"),
    )


def snapshot(env: dict[str, str], contents: str) -> Path:
    path = Path(env["XDG_STATE_HOME"]) / "asus-control/power-saving.json"
    path.parent.mkdir(parents=True)
    path.write_text(contents)
    return path


def launcher(env: dict[str, str], ok: bool) -> Path:
    path = Path(env["HOME"]) / ".local/bin/asus-control"
    path.parent.mkdir(parents=True)
    path.write_text("#!/bin/sh\nprintf '%s\\n' '" + json.dumps({"ok": ok}) + "'\n")
    path.chmod(0o755)
    return path


def test_upgrade_preserves_preferences_and_backup(isolated_home: dict[str, str]) -> None:
    env = isolated_home
    preferences = Path(env["XDG_CONFIG_HOME"]) / "asus-control/preferences"
    preferences.parent.mkdir(parents=True)
    preferences.write_text("keep")
    backup = snapshot(env, '{"version":1,"session":{"enabled":true}}')
    result = subprocess.run(
        [str(ROOT / "scripts/install.sh"), "--no-restart"],
        check=False,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    assert preferences.read_text() == "keep"
    assert json.loads(backup.read_text())["session"]["enabled"]
    unit = Path(env["XDG_CONFIG_HOME"]) / "systemd/user/asus-control-power-saving.service"
    assert unit.exists()
    assert "After=plasma-powerdevil.service" in unit.read_text()


@pytest.mark.parametrize("state", ["corrupt", '{"version":1,"session":{"enabled":true}}'])
def test_uninstall_retains_backend_when_restore_fails(
    isolated_home: dict[str, str],
    state: str,
) -> None:
    env = isolated_home
    backup = snapshot(env, state)
    backend = launcher(env, False)
    result = subprocess.run(
        [str(ROOT / "scripts/uninstall.sh"), "--no-restart"],
        check=False,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 1
    assert backend.exists()
    assert backup.read_text() == state
    assert "disable" not in Path(env["LIFECYCLE_LOG"]).read_text()


def test_uninstall_without_backup_supports_old_backend(isolated_home: dict[str, str]) -> None:
    env = isolated_home
    backend = launcher(env, False)
    result = subprocess.run(
        [str(ROOT / "scripts/uninstall.sh"), "--no-restart"],
        check=False,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert not backend.exists()
