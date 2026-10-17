"""Las traducciones del applet deben estar completas y al día con el código QML."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts" / "update-translations.sh"


@pytest.mark.skipif(shutil.which("xgettext") is None, reason="gettext no está instalado")
def test_translations_are_complete_and_up_to_date() -> None:
    result = subprocess.run(
        [str(SCRIPT), "--check"], capture_output=True, text=True, check=False, timeout=60
    )
    assert result.returncode == 0, result.stderr
