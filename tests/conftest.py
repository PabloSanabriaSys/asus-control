from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

import pytest

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
