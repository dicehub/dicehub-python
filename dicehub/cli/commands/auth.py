from __future__ import annotations

import os
from typing import Annotated

import typer

from dicehub._core.defaults import DEFAULT_BASE_URL, DEFAULT_SESSION_BASE_URL
from dicehub.cli.output import (
    CLI_SCHEMA_VERSION,
    OutputFormat,
    terminal_safe,
    write_error,
    write_json,
)
from dicehub.client import Client
from dicehub.errors import AuthenticationRequiredError, ConfigurationError, DiceHubError

auth_app = typer.Typer(
    name="auth",
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode=None,
)


@auth_app.command("whoami")
def whoami(
    output: Annotated[
        OutputFormat,
        typer.Option("--output", case_sensitive=False, help="Output format."),
    ] = OutputFormat.JSON,
) -> None:
    """Return the authenticated dicehub user."""

    error: DiceHubError | None = None
    try:
        base_url = os.environ.get("DICEHUB_URL", DEFAULT_SESSION_BASE_URL)
        api_key = os.environ.get("DICEHUB_API_KEY")
        cookie = os.environ.get("DICEHUB_SESSION_COOKIE")
        if api_key is not None and cookie is not None:
            raise ConfigurationError(
                "DICEHUB_API_KEY and DICEHUB_SESSION_COOKIE are mutually exclusive."
            )
        if cookie is None:
            raise AuthenticationRequiredError("DICEHUB_SESSION_COOKIE is required.")
        with Client(base_url=base_url, session_cookie=cookie) as client:
            user = client.users.me()
    except DiceHubError as exc:
        error = exc
    except Exception:
        error = DiceHubError("An unexpected internal error occurred.")

    if error is not None:
        write_error(error, output)
        raise typer.Exit(error.exit_code)

    if output is OutputFormat.JSON:
        write_json(
            {
                "schema_version": CLI_SCHEMA_VERSION,
                "ok": True,
                "data": {"user_id": user.user_id, "username": user.username},
                "error": None,
            }
        )
    else:
        typer.echo(f"{terminal_safe(user.username)} ({terminal_safe(user.user_id)})")


@auth_app.command("status")
def auth_status(
    output: Annotated[
        OutputFormat,
        typer.Option("--output", case_sensitive=False, help="Output format."),
    ] = OutputFormat.JSON,
) -> None:
    """Verify API-key authentication and return its identity mode."""

    error: DiceHubError | None = None
    try:
        api_key = os.environ.get("DICEHUB_API_KEY")
        session_cookie = os.environ.get("DICEHUB_SESSION_COOKIE")
        if api_key is not None and session_cookie is not None:
            raise ConfigurationError(
                "DICEHUB_API_KEY and DICEHUB_SESSION_COOKIE are mutually exclusive."
            )
        if not api_key:
            raise AuthenticationRequiredError("DICEHUB_API_KEY is required.")
        base_url = os.environ.get("DICEHUB_URL", DEFAULT_BASE_URL)
        with Client(base_url=base_url, api_key=api_key) as client:
            context = client.auth.context()
    except DiceHubError as exc:
        error = exc
    except Exception:
        error = DiceHubError("An unexpected internal error occurred.")

    if error is not None:
        write_error(error, output)
        raise typer.Exit(error.exit_code)

    if output is OutputFormat.JSON:
        write_json(
            {
                "schema_version": CLI_SCHEMA_VERSION,
                "ok": True,
                "data": {"identity_mode": context.identity_mode.value},
                "error": None,
            }
        )
    else:
        typer.echo(context.identity_mode.value)
