from __future__ import annotations

import pytest

from asus_control.domain.errors import HardwareAccessError
from asus_control.infrastructure.errors import CommandError
from asus_control.infrastructure.process import SubprocessRunner


def test_reports_failures_as_hardware_access_errors() -> None:
    with pytest.raises(CommandError, match="failed"):
        SubprocessRunner("/usr/bin/false")([])
    with pytest.raises(CommandError, match="not found"):
        SubprocessRunner("/nonexistent/asusctl")([])
    with pytest.raises(HardwareAccessError, match="timed out"):
        SubprocessRunner("/usr/bin/sleep", timeout=0.1)(["5"])


def test_passes_arguments_without_shell() -> None:
    assert SubprocessRunner("/usr/bin/echo")(["a b", "$HOME"]) == "a b $HOME\n"
