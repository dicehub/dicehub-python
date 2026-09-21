from __future__ import annotations

import json

import pytest

from dicehub import cli as cli_module
from dicehub.cli.commands import project as project_commands
from dicehub.projects import ProjectVisibility
from tests.unit.cli.test_project_cli import (
    _exception_chain_text,
    _FakeClient,
    _FakeProjects,
    _json,
    _project_detail,
    runner,
)


@pytest.fixture(autouse=True)
def reset_fakes(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeProjects.calls = []
    _FakeProjects.error = None
    _FakeProjects.detail = _project_detail()
    _FakeClient.constructions = []
    monkeypatch.delenv("DICEHUB_API_KEY", raising=False)
    monkeypatch.delenv("DICEHUB_SESSION_COOKIE", raising=False)
    monkeypatch.delenv("DICEHUB_URL", raising=False)
    monkeypatch.setattr(project_commands, "Client", _FakeClient)


def test_update_uses_api_key_without_exposing_it() -> None:
    result = runner.invoke(
        cli_module.app,
        ["project", "update", "41", "--description", "Updated by agent"],
        env={
            "DICEHUB_API_KEY": "sentinel-api-key",
            "DICEHUB_URL": "https://dicehub.test",
        },
    )

    assert result.exit_code == 0
    assert _FakeClient.constructions == [
        {
            "base_url": "https://dicehub.test",
            "api_key": "sentinel-api-key",
            "session_cookie": None,
        }
    ]
    assert _FakeProjects.calls == [
        (
            "update",
            {
                "project_id": "41",
                "name": None,
                "slug": None,
                "description": "Updated by agent",
                "visibility": None,
            },
        )
    ]
    assert _json(result)["data"] == {"project_id": "41"}
    assert "sentinel-api-key" not in result.stdout + result.stderr


def test_delete_uses_api_key_without_exposing_it() -> None:
    result = runner.invoke(
        cli_module.app,
        ["project", "delete", "41", "--yes"],
        env={
            "DICEHUB_API_KEY": "sentinel-api-key",
            "DICEHUB_URL": "https://dicehub.test",
        },
    )

    assert result.exit_code == 0
    assert _FakeClient.constructions == [
        {
            "base_url": "https://dicehub.test",
            "api_key": "sentinel-api-key",
            "session_cookie": None,
        }
    ]
    assert _FakeProjects.calls == [("delete", {"project_id": "41"})]
    assert _json(result)["data"] == {"project_id": "41"}
    assert "sentinel-api-key" not in result.stdout + result.stderr


@pytest.mark.parametrize(
    ("arguments", "expected_call", "expected_data", "requires_session"),
    [
        (
            ["update", "41", "--description", "", "--visibility", "internal", "--yes"],
            (
                "update",
                {
                    "project_id": "41",
                    "name": None,
                    "slug": None,
                    "description": "",
                    "visibility": ProjectVisibility.INTERNAL,
                },
            ),
            {"project_id": "41"},
            False,
        ),
        (
            ["move", "41", "8", "--yes"],
            ("move", {"project_id": "41", "to_group_id": "8"}),
            {"project_id": "41", "to_group_id": "8"},
            True,
        ),
        (
            ["delete", "41", "--yes"],
            ("delete", {"project_id": "41"}),
            {"project_id": "41"},
            False,
        ),
    ],
)
def test_mutations_emit_structured_results(
    arguments: list[str],
    expected_call: tuple[str, dict[str, object]],
    expected_data: dict[str, object],
    requires_session: bool,
) -> None:
    environment = (
        {"DICEHUB_SESSION_COOKIE": "sentinel-session-secret"}
        if requires_session
        else {
            "DICEHUB_API_KEY": "sentinel-api-key",
            "DICEHUB_URL": "https://dicehub.test",
        }
    )
    result = runner.invoke(
        cli_module.app,
        ["project", *arguments],
        env=environment,
    )

    assert result.exit_code == 0
    assert _FakeProjects.calls == [expected_call]
    assert _FakeClient.constructions[0]["api_key"] == (
        None if requires_session else "sentinel-api-key"
    )
    assert _json(result)["data"] == expected_data


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (
            ["update", "41", "--slug", "new-route"],
            "Project slug or visibility update requires --yes.",
        ),
        (
            ["update", "41", "--visibility", "public"],
            "Project slug or visibility update requires --yes.",
        ),
        (["move", "41", "8"], "Project move requires --yes."),
        (["delete", "41"], "Project deletion requires --yes."),
    ],
)
def test_high_impact_command_without_yes_refuses_before_client_construction(
    arguments: list[str],
    message: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(project_commands, "_stdin_is_interactive", lambda: False)
    environment = (
        {"DICEHUB_SESSION_COOKIE": "sentinel-session-secret"}
        if arguments[0] == "move"
        else {
            "DICEHUB_API_KEY": "sentinel-api-key",
            "DICEHUB_URL": "https://dicehub.test",
        }
    )
    result = runner.invoke(
        cli_module.app,
        ["project", *arguments],
        env=environment,
    )

    assert result.exit_code == 2
    assert _FakeClient.constructions == []
    assert _FakeProjects.calls == []
    assert _json(result)["error"] == {
        "code": "CONFIGURATION_ERROR",
        "message": message,
        "retryable": False,
    }


@pytest.mark.parametrize("answer", ["y\n", "Y\n", "yes\n", "Yes\n", "YES\n"])
def test_delete_prompts_in_interactive_terminal_and_accepts_yes(
    answer: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(project_commands, "_stdin_is_interactive", lambda: True)

    result = runner.invoke(
        cli_module.app,
        ["project", "delete", "41"],
        input=answer,
        env={
            "DICEHUB_API_KEY": "sentinel-api-key",
            "DICEHUB_URL": "https://dicehub.test",
        },
    )

    assert result.exit_code == 0
    assert _FakeProjects.calls == [("delete", {"project_id": "41"})]
    assert json.loads(result.stdout)["data"] == {"project_id": "41"}
    assert "Delete project 41 and all descendants?" in result.stderr
    assert "Delete project" not in result.stdout
    assert "sentinel-api-key" not in result.stdout + result.stderr


@pytest.mark.parametrize("answer", ["\n", "n\n", "no\n", "later\n"])
def test_delete_interactive_rejection_cancels_before_client_construction(
    answer: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(project_commands, "_stdin_is_interactive", lambda: True)

    result = runner.invoke(
        cli_module.app,
        ["project", "delete", "41"],
        input=answer,
        env={
            "DICEHUB_API_KEY": "sentinel-api-key",
            "DICEHUB_URL": "https://dicehub.test",
        },
    )

    assert result.exit_code == 2
    assert _FakeClient.constructions == []
    assert _FakeProjects.calls == []
    assert "Delete project 41 and all descendants?" in result.stderr
    assert json.loads(result.stdout)["error"] == {
        "code": "CONFIGURATION_ERROR",
        "message": "Project deletion was canceled.",
        "retryable": False,
    }


def test_delete_does_not_accept_piped_yes() -> None:
    result = runner.invoke(
        cli_module.app,
        ["project", "delete", "41"],
        input="yes\n",
        env={
            "DICEHUB_API_KEY": "sentinel-api-key",
            "DICEHUB_URL": "https://dicehub.test",
        },
    )

    assert result.exit_code == 2
    assert _FakeClient.constructions == []
    assert _FakeProjects.calls == []
    assert _json(result)["error"]["message"] == "Project deletion requires --yes."


def test_delete_escapes_project_id_in_interactive_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_id = "41\x1b[31m"
    monkeypatch.setattr(project_commands, "_stdin_is_interactive", lambda: True)

    result = runner.invoke(
        cli_module.app,
        ["project", "delete", project_id],
        input="yes\n",
        env={
            "DICEHUB_API_KEY": "sentinel-api-key",
            "DICEHUB_URL": "https://dicehub.test",
        },
    )

    assert result.exit_code == 0
    assert _FakeProjects.calls == [("delete", {"project_id": project_id})]
    assert "\x1b" not in result.stderr
    assert r"41\x1b[31m" in result.stderr


def test_session_only_move_rejects_api_key() -> None:
    result = runner.invoke(
        cli_module.app,
        ["project", "move", "41", "8", "--yes"],
        env={
            "DICEHUB_API_KEY": "sentinel-api-key",
            "DICEHUB_URL": "https://dicehub.test",
        },
    )

    assert result.exit_code == 3
    assert _FakeClient.constructions == []
    assert _json(result)["error"] == {
        "code": "AUTH_REQUIRED",
        "message": "This project operation requires DICEHUB_SESSION_COOKIE.",
        "retryable": False,
    }
    assert "sentinel-api-key" not in result.stdout + result.stderr + repr(result.exception)


def test_unexpected_failure_is_generic_and_redacted() -> None:
    _FakeProjects.error = RuntimeError("sentinel-api-key")
    result = runner.invoke(
        cli_module.app,
        ["project", "get", "41"],
        env={
            "DICEHUB_API_KEY": "sentinel-api-key",
            "DICEHUB_URL": "https://dicehub.test",
        },
    )

    assert result.exit_code == 1
    assert _json(result)["error"]["code"] == "DICEHUB_ERROR"
    assert "sentinel-api-key" not in (
        result.stdout + result.stderr + _exception_chain_text(result.exception)
    )


def test_text_output_escapes_terminal_controls() -> None:
    _FakeProjects.detail = _project_detail(name="demo\x1b]8;;spoof\x07")
    result = runner.invoke(
        cli_module.app,
        ["project", "get", "41", "--output", "text"],
        env={
            "DICEHUB_API_KEY": "sentinel-api-key",
            "DICEHUB_URL": "https://dicehub.test",
        },
    )

    assert result.exit_code == 0
    assert result.stdout == "41\t/group/demo\tdemo\\x1b]8;;spoof\\x07\tPRIVATE\n"
    assert "\x1b" not in result.stdout


def test_json_ascii_escapes_bidi_controls() -> None:
    _FakeProjects.detail = _project_detail(name="demo\N{RIGHT-TO-LEFT OVERRIDE}txt")
    result = runner.invoke(
        cli_module.app,
        ["project", "get", "41"],
        env={
            "DICEHUB_API_KEY": "sentinel-api-key",
            "DICEHUB_URL": "https://dicehub.test",
        },
    )

    assert result.exit_code == 0
    assert "\\u202e" in result.stdout
    assert "\N{RIGHT-TO-LEFT OVERRIDE}" not in result.stdout
