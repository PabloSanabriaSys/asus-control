"""Hace cumplir la regla de dependencias: cada capa solo importa capas más internas."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

PACKAGE = Path(__file__).parents[1] / "src" / "asus_control"

ALLOWED = {
    "domain": {"domain"},
    "application": {"domain", "application"},
    "infrastructure": {"domain", "application", "infrastructure"},
    "presentation": {"domain", "application", "presentation"},
}


def imported_layers(module: Path) -> set[str]:
    layers = set()
    for node in ast.walk(ast.parse(module.read_text())):
        names = []
        if isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        elif isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        for name in names:
            parts = name.split(".")
            if parts[0] == "asus_control" and len(parts) > 1:
                layers.add(parts[1])
    return layers


@pytest.mark.parametrize("layer", sorted(ALLOWED))
def test_layer_only_depends_on_inner_layers(layer: str) -> None:
    violations = {
        str(module.relative_to(PACKAGE)): sorted(imported_layers(module) - ALLOWED[layer])
        for module in (PACKAGE / layer).rglob("*.py")
        if imported_layers(module) - ALLOWED[layer]
    }
    assert violations == {}


def test_domain_has_no_io_dependencies() -> None:
    forbidden = {"subprocess", "json", "fcntl", "PySide6"}
    for module in (PACKAGE / "domain").rglob("*.py"):
        tree = ast.parse(module.read_text())
        imported = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        } | {
            node.module.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        assert not imported & forbidden, module.name
