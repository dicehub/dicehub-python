from __future__ import annotations

import json
from types import TracebackType
from typing import ClassVar

import pytest
from typer.core import TyperCommand, TyperGroup, TyperOption
from typer.main import get_command
from typer.testing import CliRunner

from dicehub import AuthContext, AuthenticationError, IdentityMode, User
from dicehub import cli as cli_module
from dicehub.cli.commands import auth as auth_commands

runner = CliRunner()


def _exception_chain_text(error: BaseException | None) -> str:
    values: list[str] = []
    seen: set[int] = set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        values.append(repr(error))
        error = error.__cause__ or error.__context__
    return " ".join(values)


class _FakeUsers:
    error: ClassVar[Exception | None] = None
    user: ClassVar[User] = User(user_id="42", username="ros")

    def me(self) -> User:
        if self.error is not None:
            raise self.error
        return self.user


class _FakeAuth:
    error: ClassVar[Exception | None] = None
    context_value: ClassVar[AuthContext] = AuthContext(identity_mode=IdentityMode.API_KEY)

    def context(self) -> AuthContext:
        if self.error is not None:
            raise self.error
        return self.context_value


class _FakeClient:
    users = _FakeUsers()
    auth = _FakeAuth()
    base_urls: ClassVar[list[str]] = []

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None = None,
        session_cookie: str | None = None,
    ) -> None:
        self.base_urls.append(base_url)
        if api_key is not None:
            assert api_key == "sentinel-api-key"
            assert session_cookie is None
        else:
            assert session_cookie == "sentinel-session-secret"

    def __enter__(self) -> _FakeClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None


@pytest.fixture(autouse=True)
def reset_fake_users() -> None:
    _FakeUsers.error = None
    _FakeUsers.user = User(user_id="42", username="ros")
    _FakeAuth.error = None
    _FakeAuth.context_value = AuthContext(identity_mode=IdentityMode.API_KEY)
    _FakeClient.base_urls = []


def test_whoami_emits_one_json_document(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth_commands, "Client", _FakeClient)
    result = runner.invoke(
        cli_module.app,
        ["auth", "whoami", "--output", "json"],
        env={
            "DICEHUB_SESSION_COOKIE": "sentinel-session-secret",
            "DICEHUB_URL": "https://dicehub.test",
        },
    )

    assert result.exit_code == 0
    assert result.stderr == ""
    assert result.stdout.count("\n") == 1
    assert json.loads(result.stdout) == {
        "schema_version": "dicehub.cli/v1",
        "ok": True,
        "data": {"user_id": "42", "username": "ros"},
        "error": None,
    }


def test_missing_cookie_emits_structured_auth_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DICEHUB_SESSION_COOKIE", raising=False)
    monkeypatch.setattr(auth_commands, "Client", _FakeClient)
    result = runner.invoke(
        cli_module.app,
        ["auth", "whoami", "--output", "json"],
        env={"DICEHUB_URL": "https://dicehub.test"},
    )

    assert result.exit_code == 3
    assert result.stderr == ""
    assert json.loads(result.stdout)["error"] == {
        "code": "AUTH_REQUIRED",
        "message": "DICEHUB_SESSION_COOKIE is required.",
        "retryable": False,
    }


def test_whoami_rejects_ambiguous_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth_commands, "Client", _FakeClient)
    result = runner.invoke(
        cli_module.app,
        ["auth", "whoami", "--output", "json"],
        env={
            "DICEHUB_API_KEY": "sentinel-api-key",
            "DICEHUB_SESSION_COOKIE": "sentinel-session-secret",
            "DICEHUB_URL": "https://dicehub.test",
        },
    )

    assert result.exit_code == 2
    assert json.loads(result.stdout)["error"] == {
        "code": "CONFIGURATION_ERROR",
        "message": "DICEHUB_API_KEY and DICEHUB_SESSION_COOKIE are mutually exclusive.",
        "retryable": False,
    }
    assert "sentinel-api-key" not in result.stdout + result.stderr
    assert "sentinel-session-secret" not in result.stdout + result.stderr


def test_auth_failure_is_structured_and_redacted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth_commands, "Client", _FakeClient)
    _FakeUsers.error = AuthenticationError("dicehub authentication failed.")
    result = runner.invoke(
        cli_module.app,
        ["auth", "whoami", "--output", "json"],
        env={
            "DICEHUB_SESSION_COOKIE": "sentinel-session-secret",
            "DICEHUB_URL": "https://dicehub.test",
        },
    )

    assert result.exit_code == 3
    assert json.loads(result.stdout)["error"]["code"] == "AUTH_FAILED"
    combined = result.stdout + result.stderr + repr(result.exception)
    assert "sentinel-session-secret" not in combined


def test_unexpected_error_is_generic_and_redacted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth_commands, "Client", _FakeClient)
    _FakeUsers.error = RuntimeError("sentinel-session-secret")
    result = runner.invoke(
        cli_module.app,
        ["auth", "whoami", "--output", "json"],
        env={
            "DICEHUB_SESSION_COOKIE": "sentinel-session-secret",
            "DICEHUB_URL": "https://dicehub.test",
        },
    )

    assert result.exit_code == 1
    assert json.loads(result.stdout)["error"]["code"] == "DICEHUB_ERROR"
    combined = result.stdout + result.stderr + _exception_chain_text(result.exception)
    assert "sentinel-session-secret" not in combined


def test_text_output_escapes_terminal_controls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth_commands, "Client", _FakeClient)
    _FakeUsers.user = User(user_id="42\n", username="ros\x1b]8;;spoof\x07")
    result = runner.invoke(
        cli_module.app,
        ["auth", "whoami", "--output", "text"],
        env={
            "DICEHUB_SESSION_COOKIE": "sentinel-session-secret",
            "DICEHUB_URL": "https://dicehub.test",
        },
    )

    assert result.exit_code == 0
    assert result.stdout == r"ros\x1b]8;;spoof\x07 (42\n)" + "\n"
    assert "\x1b" not in result.stdout


def test_url_cannot_be_overridden_on_command_line() -> None:
    result = runner.invoke(
        cli_module.app,
        ["auth", "whoami", "--url", "https://attacker.example"],
        env={
            "DICEHUB_SESSION_COOKIE": "sentinel-session-secret",
            "DICEHUB_URL": "https://dicehub.test",
        },
    )

    assert result.exit_code == 2
    assert "sentinel-session-secret" not in result.stdout + result.stderr


def test_auth_status_rejects_ambiguous_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(auth_commands, "Client", _FakeClient)
    result = runner.invoke(
        cli_module.app,
        ["auth", "status", "--output", "json"],
        env={
            "DICEHUB_API_KEY": "sentinel-api-key",
            "DICEHUB_SESSION_COOKIE": "must-not-be-used",
            "DICEHUB_URL": "https://dicehub.test",
        },
    )

    assert result.exit_code == 2
    assert result.stderr == ""
    assert result.stdout.count("\n") == 1
    assert json.loads(result.stdout)["error"] == {
        "code": "CONFIGURATION_ERROR",
        "message": "DICEHUB_API_KEY and DICEHUB_SESSION_COOKIE are mutually exclusive.",
        "retryable": False,
    }
    assert "sentinel-api-key" not in result.stdout + result.stderr
    assert "must-not-be-used" not in result.stdout + result.stderr


@pytest.mark.parametrize(
    ("api_key", "expected_exit_code", "expected_error"),
    [
        (
            None,
            3,
            {
                "code": "AUTH_REQUIRED",
                "message": "DICEHUB_API_KEY is required.",
                "retryable": False,
            },
        ),
        (
            "",
            2,
            {
                "code": "CONFIGURATION_ERROR",
                "message": ("DICEHUB_API_KEY and DICEHUB_SESSION_COOKIE are mutually exclusive."),
                "retryable": False,
            },
        ),
    ],
)
def test_auth_status_requires_api_key_without_session_fallback(
    monkeypatch: pytest.MonkeyPatch,
    api_key: str | None,
    expected_exit_code: int,
    expected_error: dict[str, object],
) -> None:
    monkeypatch.delenv("DICEHUB_API_KEY", raising=False)
    monkeypatch.setattr(auth_commands, "Client", _FakeClient)
    environment = {
        "DICEHUB_SESSION_COOKIE": "sentinel-session-secret",
        "DICEHUB_URL": "https://dicehub.test",
    }
    if api_key is not None:
        environment["DICEHUB_API_KEY"] = api_key
    result = runner.invoke(
        cli_module.app,
        ["auth", "status", "--output", "json"],
        env=environment,
    )

    assert result.exit_code == expected_exit_code
    assert result.stderr == ""
    assert json.loads(result.stdout)["error"] == expected_error
    assert "sentinel-session-secret" not in result.stdout + result.stderr


def test_auth_status_uses_hosted_origin_by_default_and_redacts_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DICEHUB_URL", raising=False)
    monkeypatch.setattr(auth_commands, "Client", _FakeClient)
    result = runner.invoke(
        cli_module.app,
        ["auth", "status", "--output", "json"],
        env={"DICEHUB_API_KEY": "sentinel-api-key"},
    )

    assert result.exit_code == 0
    assert result.stderr == ""
    assert _FakeClient.base_urls == ["https://dicehub.com"]
    assert json.loads(result.stdout)["data"] == {"identity_mode": "API_KEY"}
    assert "sentinel-api-key" not in result.stdout + result.stderr + repr(result.exception)


def test_auth_status_failure_is_structured_and_redacted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(auth_commands, "Client", _FakeClient)
    _FakeAuth.error = AuthenticationError("dicehub authentication failed.")
    result = runner.invoke(
        cli_module.app,
        ["auth", "status", "--output", "json"],
        env={
            "DICEHUB_API_KEY": "sentinel-api-key",
            "DICEHUB_URL": "https://dicehub.test",
        },
    )

    assert result.exit_code == 3
    assert result.stderr == ""
    assert json.loads(result.stdout)["error"]["code"] == "AUTH_FAILED"
    assert "sentinel-api-key" not in result.stdout + result.stderr + repr(result.exception)


def test_auth_status_unexpected_error_is_generic_and_redacted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(auth_commands, "Client", _FakeClient)
    _FakeAuth.error = RuntimeError("sentinel-api-key")
    result = runner.invoke(
        cli_module.app,
        ["auth", "status", "--output", "json"],
        env={
            "DICEHUB_API_KEY": "sentinel-api-key",
            "DICEHUB_URL": "https://dicehub.test",
        },
    )

    assert result.exit_code == 1
    assert result.stderr == ""
    assert json.loads(result.stdout)["error"]["code"] == "DICEHUB_ERROR"
    assert "sentinel-api-key" not in (
        result.stdout + result.stderr + _exception_chain_text(result.exception)
    )


def test_api_key_cannot_be_supplied_on_command_line() -> None:
    result = runner.invoke(
        cli_module.app,
        ["auth", "status", "--api-key", "sentinel-api-key"],
        env={"DICEHUB_URL": "https://dicehub.test"},
    )

    assert result.exit_code == 2
    assert "sentinel-api-key" not in result.stdout + result.stderr


def test_auth_status_url_cannot_be_overridden_on_command_line() -> None:
    result = runner.invoke(
        cli_module.app,
        ["auth", "status", "--url", "https://attacker.example"],
        env={
            "DICEHUB_API_KEY": "sentinel-api-key",
            "DICEHUB_URL": "https://dicehub.test",
        },
    )

    assert result.exit_code == 2
    assert "sentinel-api-key" not in result.stdout + result.stderr


def test_auth_status_help_exposes_no_credential_or_url_options() -> None:
    result = runner.invoke(cli_module.app, ["auth", "status", "--help"])

    assert result.exit_code == 0
    assert "--api-key" not in result.stdout
    assert "--url" not in result.stdout


def test_registered_commands_have_no_credential_or_url_options() -> None:
    command = get_command(cli_module.app)
    assert isinstance(command, TyperGroup)

    expected_commands = {
        "app": {"create", "update", "delete", "list", "get", "get-by-route"},
        "group": {"list", "get", "get-by-route", "update"},
        "project": {"list", "get", "get-by-route", "create", "update", "move", "delete"},
        "template": {"list", "get", "get-by-route"},
    }
    for group_name, names in expected_commands.items():
        group = command.commands[group_name]
        assert isinstance(group, TyperGroup)
        assert names <= set(group.commands)

    pending: list[TyperCommand | TyperGroup] = [command]
    forbidden = {"--api-key", "--session-cookie", "--url"}
    while pending:
        current = pending.pop()
        for parameter in current.params:
            if isinstance(parameter, TyperOption):
                assert not forbidden.intersection((*parameter.opts, *parameter.secondary_opts)), (
                    current.name
                )
        if isinstance(current, TyperGroup):
            for child in current.commands.values():
                assert isinstance(child, (TyperCommand, TyperGroup))
                pending.append(child)
