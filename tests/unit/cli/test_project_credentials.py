from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from dicehub import cli as cli_module
from dicehub.cli.commands import project as project_commands

runner = CliRunner()


def _exception_chain_text(error: BaseException | None) -> str:
    values: list[str] = []
    seen: set[int] = set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        values.append(repr(error))
        error = error.__cause__ or error.__context__
    return " ".join(values)


class _ForbiddenClient:
    def __init__(self, **kwargs: object) -> None:
        raise AssertionError("Client must not be constructed for invalid credentials.")


@pytest.mark.parametrize(
    ("arguments", "environment", "expected_code"),
    [
        (
            ["project", "list"],
            {
                "DICEHUB_API_KEY": "sentinel-api-key",
                "DICEHUB_SESSION_COOKIE": "sentinel-session-secret",
                "DICEHUB_URL": "https://dicehub.test",
            },
            "CONFIGURATION_ERROR",
        ),
        (
            ["project", "create", "--name", "Demo", "--slug", "demo"],
            {
                "DICEHUB_API_KEY": "sentinel-api-key",
                "DICEHUB_SESSION_COOKIE": "sentinel-session-secret",
                "DICEHUB_URL": "https://dicehub.test",
            },
            "CONFIGURATION_ERROR",
        ),
        (
            ["project", "get", "41"],
            {
                "DICEHUB_API_KEY": "",
                "DICEHUB_SESSION_COOKIE": "sentinel-session-secret",
            },
            "CONFIGURATION_ERROR",
        ),
        (
            ["project", "list"],
            {"DICEHUB_API_KEY": "", "DICEHUB_URL": "https://dicehub.test"},
            "AUTH_REQUIRED",
        ),
        (
            ["project", "get", "41"],
            {"DICEHUB_SESSION_COOKIE": ""},
            "AUTH_REQUIRED",
        ),
    ],
)
def test_project_commands_reject_ambiguous_or_blank_credentials(
    monkeypatch: pytest.MonkeyPatch,
    arguments: list[str],
    environment: dict[str, str],
    expected_code: str,
) -> None:
    monkeypatch.delenv("DICEHUB_API_KEY", raising=False)
    monkeypatch.delenv("DICEHUB_SESSION_COOKIE", raising=False)
    monkeypatch.delenv("DICEHUB_URL", raising=False)
    monkeypatch.setattr(project_commands, "Client", _ForbiddenClient)
    result = runner.invoke(cli_module.app, arguments, env=environment)

    assert result.exit_code in {2, 3}
    payload = json.loads(result.stdout)
    assert payload["error"]["code"] == expected_code
    combined = result.stdout + result.stderr + _exception_chain_text(result.exception)
    assert "sentinel-api-key" not in combined
    assert "sentinel-session-secret" not in combined


def test_normal_command_rejects_session_before_client_construction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DICEHUB_API_KEY", raising=False)
    monkeypatch.delenv("DICEHUB_SESSION_COOKIE", raising=False)
    monkeypatch.delenv("DICEHUB_URL", raising=False)
    monkeypatch.setattr(project_commands, "Client", _ForbiddenClient)

    result = runner.invoke(
        cli_module.app,
        ["project", "get", "41"],
        env={
            "DICEHUB_SESSION_COOKIE": "sentinel-session-secret",
            "DICEHUB_URL": "https://dicehub.test",
        },
    )

    assert result.exit_code == 2
    assert json.loads(result.stdout)["error"] == {
        "code": "CONFIGURATION_ERROR",
        "message": "DICEHUB_SESSION_COOKIE is not supported for this command; use DICEHUB_API_KEY.",
        "retryable": False,
    }
    assert "sentinel-session-secret" not in result.stdout + result.stderr


def test_normal_command_requires_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DICEHUB_API_KEY", raising=False)
    monkeypatch.delenv("DICEHUB_SESSION_COOKIE", raising=False)
    monkeypatch.delenv("DICEHUB_URL", raising=False)
    monkeypatch.setattr(project_commands, "Client", _ForbiddenClient)

    result = runner.invoke(
        cli_module.app,
        ["project", "get", "41"],
        env={"DICEHUB_URL": "https://dicehub.test"},
    )

    assert result.exit_code == 3
    assert json.loads(result.stdout)["error"] == {
        "code": "AUTH_REQUIRED",
        "message": "DICEHUB_API_KEY is required.",
        "retryable": False,
    }
