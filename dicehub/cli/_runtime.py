from __future__ import annotations

import os
from collections.abc import Callable
from typing import NoReturn, TypeVar

import typer

from dicehub._core.defaults import DEFAULT_BASE_URL, DEFAULT_SESSION_BASE_URL
from dicehub.cli.output import OutputFormat, write_error
from dicehub.client import Client
from dicehub.errors import AuthenticationRequiredError, ConfigurationError, DiceHubError

_Result = TypeVar("_Result")


def fail(error: DiceHubError, output: OutputFormat) -> NoReturn:
    write_error(error, output)
    raise typer.Exit(error.exit_code)


def run_with_client(
    action: Callable[[Client], _Result],
    output: OutputFormat,
    *,
    client_type: type[Client],
    session_required_message: str | None = None,
    allow_session: bool = False,
) -> _Result:
    error: DiceHubError
    try:
        configured_base_url = os.environ.get("DICEHUB_URL")
        api_key = os.environ.get("DICEHUB_API_KEY")
        session_cookie = os.environ.get("DICEHUB_SESSION_COOKIE")
        if api_key is not None and session_cookie is not None:
            raise ConfigurationError(
                "DICEHUB_API_KEY and DICEHUB_SESSION_COOKIE are mutually exclusive."
            )
        if api_key == "":
            raise AuthenticationRequiredError("DICEHUB_API_KEY must not be empty.")
        if session_cookie == "":
            raise AuthenticationRequiredError("DICEHUB_SESSION_COOKIE must not be empty.")

        if session_required_message is not None:
            if session_cookie is None:
                raise AuthenticationRequiredError(session_required_message)
            base_url = (
                configured_base_url if configured_base_url is not None else DEFAULT_SESSION_BASE_URL
            )
            with client_type(base_url=base_url, session_cookie=session_cookie) as client:
                return action(client)

        if session_cookie is not None and not allow_session:
            raise ConfigurationError(
                "DICEHUB_SESSION_COOKIE is not supported for this command; use DICEHUB_API_KEY."
            )
        if session_cookie is not None:
            base_url = (
                configured_base_url if configured_base_url is not None else DEFAULT_SESSION_BASE_URL
            )
            with client_type(base_url=base_url, session_cookie=session_cookie) as client:
                return action(client)
        if api_key is None:
            if allow_session:
                raise AuthenticationRequiredError(
                    "DICEHUB_API_KEY or DICEHUB_SESSION_COOKIE is required."
                )
            raise AuthenticationRequiredError("DICEHUB_API_KEY is required.")
        base_url = configured_base_url if configured_base_url is not None else DEFAULT_BASE_URL
        with client_type(base_url=base_url, api_key=api_key) as client:
            return action(client)
    except DiceHubError as exc:
        error = exc
    except Exception:
        error = DiceHubError("An unexpected internal error occurred.")

    fail(error, output)
