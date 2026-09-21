from __future__ import annotations

import json
from enum import Enum
from typing import Any

import typer

from dicehub.errors import DiceHubError

CLI_SCHEMA_VERSION = "dicehub.cli/v1"


class OutputFormat(str, Enum):
    JSON = "json"
    TEXT = "text"


def write_error(error: DiceHubError, output: OutputFormat) -> None:
    if output is OutputFormat.JSON:
        write_json(
            {
                "schema_version": CLI_SCHEMA_VERSION,
                "ok": False,
                "data": None,
                "error": error.as_dict(),
            }
        )
    else:
        typer.echo(
            f"Error [{terminal_safe(error.code)}]: {terminal_safe(error.message)}",
            err=True,
        )


def write_json(payload: dict[str, Any]) -> None:
    typer.echo(json.dumps(payload, ensure_ascii=True, separators=(",", ":")))


def terminal_safe(value: str) -> str:
    return "".join(
        character if character.isprintable() else ascii(character)[1:-1] for character in value
    )
