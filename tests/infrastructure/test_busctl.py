from __future__ import annotations

import pytest

from asus_control.infrastructure.busctl import Busctl
from asus_control.infrastructure.errors import ParseError
from tests.conftest import FakeRunner


def test_reads_property_value_from_json() -> None:
    runner = FakeRunner(lambda _args: '{"type":"y","data":60}')

    assert Busctl(runner, "svc").get_property("/p", "iface", "Prop") == 60
    assert runner.calls == [
        ["--system", "--json=short", "get-property", "svc", "/p", "iface", "Prop"]
    ]


def test_formats_booleans_and_numbers_for_busctl(fake_runner: FakeRunner) -> None:
    Busctl(fake_runner, "svc").set_property("/p", "iface", "Prop", "(ub)", 2, True)

    assert fake_runner.calls == [
        ["--system", "set-property", "svc", "/p", "iface", "Prop", "(ub)", "2", "true"]
    ]


def test_call_without_return_value(fake_runner: FakeRunner) -> None:
    assert Busctl(fake_runner, "svc").call("/p", "iface", "Method", "ub", 0, False) is None
    assert fake_runner.calls[0][-3:] == ["ub", "0", "false"]


@pytest.mark.parametrize("output", ["no json", '{"type":"u"}', "[]"])
def test_rejects_invalid_json(output: str) -> None:
    with pytest.raises(ParseError):
        Busctl(FakeRunner(lambda _args: output), "svc").get_property("/p", "i", "P")
