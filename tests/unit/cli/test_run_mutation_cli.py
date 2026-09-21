from __future__ import annotations

import json
from datetime import datetime, timezone
from types import TracebackType
from typing import Any, ClassVar, cast

import pytest
from typer.testing import CliRunner

from dicehub import MutationOutcomeUnknownError, RunError, RunFlag, RunState, RunStatus
from dicehub import cli as cli_module
from dicehub.cli.commands import run as run_commands

runner = CliRunner()
RUN_ID = "12345678-1234-5678-9234-567812345678"
UPDATED_AT = datetime(2026, 8, 11, 10, 11, 12, 456000, tzinfo=timezone.utc)


def _status() -> RunStatus:
    return RunStatus(
        run_id=RUN_ID,
        state=RunState.PREPARING,
        execution_status=None,
        error=RunError.NONE,
        flags=(RunFlag.NOTIFY,),
        updated_at=UPDATED_AT,
    )


class _FakeRuns:
    calls: ClassVar[list[tuple[str, dict[str, object]]]] = []
    error: ClassVar[Exception | None] = None

    def start(
        self,
        *,
        config_id: str,
        machine_type_id: str,
        node_count: int = 1,
        cpu_count: int | None = None,
        notify: bool = False,
    ) -> RunStatus:
        if self.error is not None:
            raise self.error
        self.calls.append(
            (
                "start",
                {
                    "config_id": config_id,
                    "machine_type_id": machine_type_id,
                    "node_count": node_count,
                    "cpu_count": cpu_count,
                    "notify": notify,
                },
            )
        )
        return _status()

    def stop(self, *, run_id: str) -> None:
        if self.error is not None:
            raise self.error
        self.calls.append(("stop", {"run_id": run_id}))


class _FakeClient:
    runs = _FakeRuns()
    constructions: ClassVar[list[dict[str, object]]] = []

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None = None,
        session_cookie: str | None = None,
    ) -> None:
        self.constructions.append(
            {
                "base_url": base_url,
                "api_key": api_key,
                "session_cookie": session_cookie,
            }
        )

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
def reset_fakes(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeRuns.calls = []
    _FakeRuns.error = None
    _FakeClient.constructions = []
    monkeypatch.delenv("DICEHUB_API_KEY", raising=False)
    monkeypatch.delenv("DICEHUB_SESSION_COOKIE", raising=False)
    monkeypatch.delenv("DICEHUB_URL", raising=False)
    monkeypatch.setattr(run_commands, "Client", _FakeClient)


def _json(result: Any) -> dict[str, Any]:
    assert result.stderr == ""
    assert result.stdout.count("\n") == 1
    payload = json.loads(result.stdout)
    assert isinstance(payload, dict)
    return cast(dict[str, Any], payload)


def _environment() -> dict[str, str]:
    return {
        "DICEHUB_API_KEY": "sentinel-api-key",
        "DICEHUB_URL": "https://dicehub.test",
    }


def test_start_passes_explicit_options_and_emits_status_json() -> None:
    result = runner.invoke(
        cli_module.app,
        [
            "run",
            "start",
            "301",
            "--machine-type",
            "dh1_4x",
            "--nodes",
            "2",
            "--cpus",
            "8",
            "--notify",
            "--yes",
            "--output",
            "json",
        ],
        env=_environment(),
    )

    assert result.exit_code == 0, result.output
    assert _FakeRuns.calls == [
        (
            "start",
            {
                "config_id": "301",
                "machine_type_id": "dh1_4x",
                "node_count": 2,
                "cpu_count": 8,
                "notify": True,
            },
        )
    ]
    payload = _json(result)
    assert payload["ok"] is True
    assert payload["data"]["run_status"] == {
        "run_id": RUN_ID,
        "state": "PREPARING",
        "execution_status": None,
        "error": "NONE",
        "flags": ["NOTIFY"],
        "updated_at": "2026-08-11T10:11:12.456000Z",
    }
    assert "sentinel-api-key" not in result.stdout + result.stderr


def test_start_defaults_are_forwarded_explicitly() -> None:
    result = runner.invoke(
        cli_module.app,
        ["run", "start", "301", "--machine-type", "local", "--yes"],
        env=_environment(),
    )

    assert result.exit_code == 0, result.output
    assert _FakeRuns.calls == [
        (
            "start",
            {
                "config_id": "301",
                "machine_type_id": "local",
                "node_count": 1,
                "cpu_count": None,
                "notify": False,
            },
        )
    ]


def test_stop_requires_confirmation_before_client_construction() -> None:
    result = runner.invoke(
        cli_module.app,
        ["run", "stop", RUN_ID, "--output", "json"],
        env=_environment(),
    )

    assert result.exit_code == 2
    assert _FakeClient.constructions == []
    assert _FakeRuns.calls == []
    assert _json(result) == {
        "schema_version": "dicehub.cli/v1",
        "ok": False,
        "data": None,
        "error": {
            "code": "CONFIGURATION_ERROR",
            "message": "Run stop requires --yes.",
            "retryable": False,
        },
    }


def test_start_requires_confirmation_before_client_construction() -> None:
    result = runner.invoke(
        cli_module.app,
        ["run", "start", "301", "--machine-type", "local"],
        env=_environment(),
    )

    assert result.exit_code == 2
    assert _FakeClient.constructions == []
    assert _FakeRuns.calls == []
    assert _json(result)["error"] == {
        "code": "CONFIGURATION_ERROR",
        "message": "Run start requires --yes.",
        "retryable": False,
    }


def test_stop_requests_exact_run_and_emits_stable_json() -> None:
    result = runner.invoke(
        cli_module.app,
        ["run", "stop", RUN_ID, "--yes", "--output", "json"],
        env=_environment(),
    )

    assert result.exit_code == 0, result.output
    assert _FakeRuns.calls == [("stop", {"run_id": RUN_ID})]
    assert _json(result) == {
        "schema_version": "dicehub.cli/v1",
        "ok": True,
        "data": {"run_id": RUN_ID},
        "error": None,
    }


def test_stop_text_reports_request_not_terminal_state() -> None:
    result = runner.invoke(
        cli_module.app,
        ["run", "stop", RUN_ID, "--yes", "--output", "text"],
        env=_environment(),
    )

    assert result.exit_code == 0, result.output
    assert result.stdout == f"Stop requested for run {RUN_ID}.\n"


def test_mutation_unknown_error_is_machine_readable_and_not_retried() -> None:
    _FakeRuns.error = MutationOutcomeUnknownError("Run outcome unknown.")
    result = runner.invoke(
        cli_module.app,
        ["run", "start", "301", "--machine-type", "local", "--yes"],
        env=_environment(),
    )

    assert result.exit_code == 5
    assert _FakeRuns.calls == []
    payload = _json(result)
    assert payload["error"]["code"] == "MUTATION_OUTCOME_UNKNOWN"
    assert payload["error"]["retryable"] is False
    assert "sentinel-api-key" not in result.stdout + result.stderr


@pytest.mark.parametrize(
    "arguments",
    [
        ["run", "start", "301", "--machine-type", "local", "--nodes", "0", "--yes"],
        ["run", "start", "301", "--machine-type", "local", "--cpus", "0", "--yes"],
    ],
)
def test_invalid_counts_fail_before_client_construction(arguments: list[str]) -> None:
    result = runner.invoke(cli_module.app, arguments, env=_environment())

    assert result.exit_code == 2
    assert _FakeClient.constructions == []
    assert _FakeRuns.calls == []
