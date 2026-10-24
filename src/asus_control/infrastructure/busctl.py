"""Acceso al bus del sistema mediante ``busctl`` (sin dependencias de Python para D-Bus).

Cada llamada tarda unos milisegundos: mucho menos que ``asusctl``, que arranca un
cliente completo por orden. Las respuestas se leen en JSON (``--json=short``).
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from asus_control.infrastructure.errors import ParseError
from asus_control.infrastructure.process import CommandRunner

DBusArgument = str | int | bool


class Busctl:
    """Lecturas y escrituras sobre un servicio del bus del sistema."""

    def __init__(self, run: CommandRunner, service: str, scope: str = "--system") -> None:
        self._run = run
        self._service = service
        self._scope = scope

    def get_property(self, path: str, interface: str, name: str) -> object:
        return _data(
            self._run(
                [self._scope, "--json=short", "get-property", self._service, path, interface, name]
            )
        )

    def set_property(
        self, path: str, interface: str, name: str, signature: str, *values: DBusArgument
    ) -> None:
        self._run(
            [
                self._scope,
                "set-property",
                self._service,
                path,
                interface,
                name,
                signature,
                *_format(values),
            ]
        )

    def call(
        self, path: str, interface: str, method: str, signature: str = "", *args: DBusArgument
    ) -> object:
        command = [self._scope, "--json=short", "call", self._service, path, interface, method]
        if signature:
            command += [signature, *_format(args)]
        output = self._run(command)
        return _data(output) if output.strip() else None

    def object_paths(self) -> list[str]:
        return [
            line.strip()
            for line in self._run([self._scope, "--list", "tree", self._service]).splitlines()
        ]


def _format(values: Sequence[DBusArgument]) -> list[str]:
    # busctl espera los booleanos como true/false; bool es subclase de int, se comprueba antes.
    return [
        ("true" if value else "false") if isinstance(value, bool) else str(value)
        for value in values
    ]


def _data(output: str) -> object:
    """Valor de una respuesta JSON de busctl.

    En ``call``, los valores de retorno llegan agrupados en una lista.
    """
    try:
        return json.loads(output)["data"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ParseError(f"Invalid busctl JSON response: {output[:80]!r}") from exc
