from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Annotated, TypeVar

import typer

from dicehub.cli._runtime import fail, run_with_client
from dicehub.cli.output import CLI_SCHEMA_VERSION, OutputFormat, terminal_safe, write_json
from dicehub.client import Client
from dicehub.errors import ConfigurationError

_Result = TypeVar("_Result")

avatar_app = typer.Typer(
    name="avatar",
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode=None,
)

_OUTPUT_OPTION = typer.Option("--output", case_sensitive=False, help="Output format.")


def _run(action: Callable[[Client], _Result], output: OutputFormat) -> _Result:
    return run_with_client(action, output, client_type=Client)


def _write_success(group_id: str) -> None:
    write_json(
        {
            "schema_version": CLI_SCHEMA_VERSION,
            "ok": True,
            "data": {"group_id": group_id},
            "error": None,
        }
    )


def _require_confirmation(action: str, yes: bool, output: OutputFormat) -> None:
    if not yes:
        fail(ConfigurationError(f"Group avatar {action} requires --yes."), output)


@avatar_app.command("set")
def set_group_avatar(
    group_id: Annotated[str, typer.Argument(help="Exact group ID.")],
    source: Annotated[
        Path,
        typer.Argument(
            help="PNG image file.",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
        ),
    ],
    yes: Annotated[bool, typer.Option("--yes", help="Confirm avatar replacement.")] = False,
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """Replace one group avatar with a bounded PNG image."""

    _require_confirmation("replacement", yes, output)
    open_failed = False
    try:
        with source.open("rb") as stream:
            _run(lambda client: client.groups.set_avatar(group_id=group_id, source=stream), output)
    except OSError:
        open_failed = True
    if open_failed:
        fail(ConfigurationError("Group avatar source could not be read."), output)
    if output is OutputFormat.JSON:
        _write_success(group_id)
    else:
        typer.echo(f"Updated avatar for group {terminal_safe(group_id)}.")


@avatar_app.command("clear")
def clear_group_avatar(
    group_id: Annotated[str, typer.Argument(help="Exact group ID.")],
    yes: Annotated[bool, typer.Option("--yes", help="Confirm avatar removal.")] = False,
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """Remove one group avatar."""

    _require_confirmation("removal", yes, output)
    _run(lambda client: client.groups.clear_avatar(group_id=group_id), output)
    if output is OutputFormat.JSON:
        _write_success(group_id)
    else:
        typer.echo(f"Cleared avatar for group {terminal_safe(group_id)}.")
