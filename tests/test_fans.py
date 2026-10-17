from __future__ import annotations

import ast
import multiprocessing
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from asus_control.commands import AsusCtl
from asus_control.errors import FanModeError, LockBusyError
from asus_control.fan_lock import fan_lock
from asus_control.fans import CURVES, TEMPS, FanService, curve_data, detect_mode
from asus_control.models import Fan, FanMode
from asus_control.parsing import parse_fan_curves
from tests.conftest import fixture_text
from tests.fake_asusd import FakeAsusd

SCRIPT = Path.home() / ".local" / "bin" / "alternar-ventilacion"


@contextmanager
def no_lock() -> Iterator[None]:
    yield


def make_service(asusd: FakeAsusd) -> FanService:
    return FanService(AsusCtl(asusd), no_lock)


def script_constants() -> tuple[object, object]:
    tree = ast.parse(SCRIPT.read_text())
    values: dict[str, object] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name in {"TEMPS", "CURVES"}:
                expression = ast.Expression(node.value)
                values[name] = eval(compile(expression, str(SCRIPT), "eval"), {"__builtins__": {}})
    return values["TEMPS"], values["CURVES"]


@pytest.mark.skipif(not SCRIPT.exists(), reason="alternar-ventilacion no está instalado")
def test_curves_are_identical_to_alternar_ventilacion() -> None:
    script_temps, script_curves = script_constants()
    ours = {
        mode.value: {fan.value: pwm for fan, pwm in fans.items()} for mode, fans in CURVES.items()
    }

    assert script_temps == TEMPS
    assert script_curves == ours


def test_real_disabled_curves_are_normal_mode() -> None:
    assert detect_mode(parse_fan_curves(fixture_text("fan_curves_disabled.txt"))) is FanMode.NORMAL


def test_curve_data_uses_raw_pwm_values() -> None:
    assert curve_data(CURVES[FanMode.EXTRA][Fan.MID]) == (
        "40c:26,55c:51,64c:77,68c:97,71c:115,74c:128,77c:140,80c:153"
    )


@pytest.mark.parametrize("mode", list(FanMode))
def test_applies_and_detects_every_mode(mode: FanMode) -> None:
    asusd = FakeAsusd()
    service = make_service(asusd)

    service.apply(mode)

    assert service.read_status().mode is mode


def test_unknown_enabled_curves_are_custom() -> None:
    asusd = FakeAsusd()
    for curve in asusd.curves.values():
        curve.enabled = True
    asusd.curves["CPU"].pwm = (1,) * 8

    assert make_service(asusd).read_status().mode is None


@pytest.mark.parametrize("profile", ["Quiet", "Performance"])
def test_refuses_outside_balanced_without_changing_profile(profile: str) -> None:
    asusd = FakeAsusd(profile=profile)

    with pytest.raises(FanModeError) as error:
        make_service(asusd).apply(FanMode.ULTRA)

    assert error.value.restored is None
    assert asusd.profile == profile
    assert asusd.calls == [["profile", "get"]]


def test_partial_failure_restores_automatic_control() -> None:
    asusd = FakeAsusd(fail_on={("fan-curve", "--mod-profile", "Balanced", "--fan", "gpu")})

    with pytest.raises(FanModeError) as error:
        make_service(asusd).apply(FanMode.EXTRA)

    assert error.value.restored is True
    assert "Se restauró" in str(error.value)
    assert not any(curve.enabled for curve in asusd.curves.values())


def test_reports_when_restoration_also_fails() -> None:
    asusd = FakeAsusd(fail_on={("fan-curve", "--mod-profile", "Balanced", "--enable-fan-curves")})

    with pytest.raises(FanModeError) as error:
        make_service(asusd).apply(FanMode.ULTRA)

    assert error.value.restored is False
    assert "ni restaurar" in str(error.value)


def test_unconfirmed_write_is_reported() -> None:
    asusd = FakeAsusd(ignore_writes=True)

    with pytest.raises(FanModeError) as error:
        make_service(asusd).apply(FanMode.ULTRA_MEGA)

    # Las curvas nunca se activaron: el modo automático sigue vigente.
    assert error.value.restored is True


def _hold_lock(
    path: Path, ready: multiprocessing.synchronize.Event, release: multiprocessing.synchronize.Event
) -> None:
    with fan_lock(path):
        ready.set()
        release.wait(5)


def test_lock_is_shared_across_processes(tmp_path: Path) -> None:
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


def test_busy_lock_prevents_any_command(tmp_path: Path) -> None:
    asusd = FakeAsusd()

    @contextmanager
    def busy() -> Iterator[None]:
        raise LockBusyError("ocupado")
        yield

    with pytest.raises(LockBusyError):
        FanService(AsusCtl(asusd), busy).apply(FanMode.EXTRA)
    assert asusd.calls == []
