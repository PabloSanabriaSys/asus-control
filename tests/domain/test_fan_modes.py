from __future__ import annotations

import ast
from pathlib import Path

import pytest

from asus_control.domain.fan_modes import CURVES, TEMPS, detect_mode, target_curves
from asus_control.domain.models import Fan, FanCurve, FanMode
from tests.fakes import automatic_curves

SCRIPT = Path.home() / ".local" / "bin" / "alternar-ventilacion"


def script_constants() -> dict[str, object]:
    """Evalúa solo las asignaciones ``TEMPS`` y ``CURVES`` del script, sin ejecutarlo."""
    values: dict[str, object] = {}
    for node in ast.parse(SCRIPT.read_text()).body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name in {"TEMPS", "CURVES"}:
                code = compile(ast.Expression(node.value), str(SCRIPT), "eval")
                values[name] = eval(code, {"__builtins__": {}})
    return values


@pytest.mark.skipif(not SCRIPT.exists(), reason="alternar-ventilacion no está instalado")
def test_curves_are_identical_to_alternar_ventilacion() -> None:
    script = script_constants()
    ours = {
        mode.value: {fan.value: pwm for fan, pwm in fans.items()} for mode, fans in CURVES.items()
    }

    assert script["TEMPS"] == TEMPS
    assert script["CURVES"] == ours


def test_normal_mode_has_no_custom_curves() -> None:
    assert target_curves(FanMode.NORMAL) == []


@pytest.mark.parametrize("mode", [FanMode.EXTRA, FanMode.ULTRA, FanMode.ULTRA_MEGA])
def test_target_curves_are_detected_as_their_mode(mode: FanMode) -> None:
    curves = {curve.fan: curve for curve in target_curves(mode)}

    assert set(curves) == set(Fan)
    assert all(curve.enabled and curve.temps == TEMPS for curve in curves.values())
    assert detect_mode(curves) is mode


def test_disabled_curves_are_normal_mode() -> None:
    assert detect_mode(automatic_curves()) is FanMode.NORMAL


def test_unknown_enabled_curves_are_custom() -> None:
    curves = {curve.fan: curve for curve in target_curves(FanMode.EXTRA)}
    curves[Fan.CPU] = FanCurve(Fan.CPU, (1,) * 8, TEMPS, enabled=True)

    assert detect_mode(curves) is None
