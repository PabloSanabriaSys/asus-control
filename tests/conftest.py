from __future__ import annotations

import os

# Las pruebas de interfaz no necesitan una sesión gráfica.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from collections.abc import Callable, Sequence
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

FIXTURES = Path(__file__).parent / "fixtures"

Handler = Callable[[Sequence[str]], str]


def fixture_text(name: str) -> str:
    return (FIXTURES / name).read_text()


class FakeRunner:
    """Simula un ``CommandRunner`` registrando cada llamada."""

    def __init__(self, handler: Handler | None = None) -> None:
        self.calls: list[list[str]] = []
        self._handler = handler or (lambda _args: "")

    def __call__(self, args: Sequence[str]) -> str:
        self.calls.append(list(args))
        return self._handler(args)


@pytest.fixture
def fake_runner() -> FakeRunner:
    return FakeRunner()


@pytest.fixture(scope="session")
def qt_app() -> QApplication:
    app = QApplication.instance()
    return app if isinstance(app, QApplication) else QApplication([])
