from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import datetime, timezone
from types import TracebackType
from typing import Any, ClassVar, cast

import pytest
from typer.testing import CliRunner

from dicehub import (
    RunError,
    RunExecutionStatus,
    RunFailedError,
    RunFlag,
    RunState,
    RunStatus,
    RunTimeoutError,
)
from dicehub import cli as cli_module
from dicehub.cli.commands import run as run_commands
from dicehub.cli.output import OutputFormat

runner = CliRunner()
RUN_ID = "12345678-1234-5678-9234-567812345678"
UPDATED_AT = datetime(2026, 8, 11, 10, 11, 12, 456000, tzinfo=timezone.utc)


def _status(
    state: RunState,
    *,
    error: RunError | None = RunError.NONE,
    execution_status: RunExecutionStatus | None = None,
) -> RunStatus:
    return RunStatus(
        run_id=RUN_ID,
        state=state,
        execution_status=execution_status,
        error=error,
        flags=(RunFlag.NOTIFY,),
        updated_at=UPDATED_AT,
    )


class _FakeRuns:
    calls: ClassVar[list[tuple[str, dict[str, object]]]] = []
    wait_result: ClassVar[RunStatus] = _status(RunState.FINISHED)
    wait_error: ClassVar[RunFailedError | RunTimeoutError | None] = None
    watch_statuses: ClassVar[list[RunStatus]] = []
    watch_error: ClassVar[RunTimeoutError | None] = None
    observed_client_open: ClassVar[list[bool]] = []

    def wait(
        self,
        *,
        run_id: str,
        timeout_seconds: float,
        poll_seconds: float = 2.0,
    ) -> RunStatus:
        self.calls.append(
            (
                "wait",
                {
                    "run_id": run_id,
                    "timeout_seconds": timeout_seconds,
                    "poll_seconds": poll_seconds,
                },
            )
        )
        if self.wait_error is not None:
            raise self.wait_error
        return self.wait_result

    def watch(
        self,
        *,
        run_id: str,
        timeout_seconds: float,
        poll_seconds: float = 2.0,
    ) -> Iterator[RunStatus]:
        self.calls.append(
            (
                "watch",
                {
                    "run_id": run_id,
                    "timeout_seconds": timeout_seconds,
                    "poll_seconds": poll_seconds,
                },
            )
        )

        def statuses() -> Iterator[RunStatus]:
            for status in self.watch_statuses:
                self.observed_client_open.append(_FakeClient.open)
                yield status
            if self.watch_error is not None:
                raise self.watch_error

        return statuses()


class _FakeClient:
    runs = _FakeRuns()
    open: ClassVar[bool] = False

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None = None,
        session_cookie: str | None = None,
    ) -> None:
        assert base_url == "https://dicehub.test"
        assert api_key == "sentinel-api-key"
        assert session_cookie is None

    def __enter__(self) -> _FakeClient:
        _FakeClient.open = True
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        _FakeClient.open = False


@pytest.fixture(autouse=True)
def reset_fakes(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeRuns.calls = []
    _FakeRuns.wait_result = _status(RunState.FINISHED)
    _FakeRuns.wait_error = None
    _FakeRuns.watch_statuses = []
    _FakeRuns.watch_error = None
    _FakeRuns.observed_client_open = []
    _FakeClient.open = False
    monkeypatch.setattr(run_commands, "Client", _FakeClient)
    monkeypatch.setenv("DICEHUB_API_KEY", "sentinel-api-key")
    monkeypatch.setenv("DICEHUB_URL", "https://dicehub.test")
    monkeypatch.delenv("DICEHUB_SESSION_COOKIE", raising=False)


def _environment() -> dict[str, str]:
    return {
        "DICEHUB_API_KEY": "sentinel-api-key",
        "DICEHUB_URL": "https://dicehub.test",
    }


def _lines(result: Any) -> list[dict[str, Any]]:
    assert result.stderr == ""
    lines = [line for line in result.stdout.splitlines() if line]
    return [cast(dict[str, Any], json.loads(line)) for line in lines]


def test_wait_forwards_timeout_and_poll_and_emits_one_json_status() -> None:
    result = runner.invoke(
        cli_module.app,
        [
            "run",
            "wait",
            RUN_ID,
            "--timeout",
            "12.5",
            "--poll",
            "0.25",
            "--output",
            "json",
        ],
        env=_environment(),
    )

    assert result.exit_code == 0, result.output
    assert _FakeRuns.calls == [
        (
            "wait",
            {"run_id": RUN_ID, "timeout_seconds": 12.5, "poll_seconds": 0.25},
        )
    ]
    assert _lines(result) == [
        {
            "schema_version": "dicehub.cli/v1",
            "ok": True,
            "data": {
                "run_status": {
                    "run_id": RUN_ID,
                    "state": "FINISHED",
                    "execution_status": None,
                    "error": "NONE",
                    "flags": ["NOTIFY"],
                    "updated_at": "2026-08-11T10:11:12.456000Z",
                }
            },
            "error": None,
        }
    ]


def test_wait_text_uses_existing_status_columns() -> None:
    result = runner.invoke(
        cli_module.app,
        ["run", "wait", RUN_ID, "--timeout", "12.5", "--output", "text"],
        env=_environment(),
    )

    assert result.exit_code == 0, result.output
    assert result.stdout == f"{RUN_ID}\tFINISHED\t2026-08-11T10:11:12.456000Z\n"


def test_watch_jsonl_streams_statuses_and_keeps_client_open() -> None:
    _FakeRuns.watch_statuses = [_status(RunState.RUNNING), _status(RunState.FINISHED)]
    result = runner.invoke(
        cli_module.app,
        [
            "run",
            "watch",
            RUN_ID,
            "--timeout",
            "30",
            "--poll",
            "1.5",
            "--output",
            "jsonl",
        ],
        env=_environment(),
    )

    assert result.exit_code == 0, result.output
    assert _FakeRuns.calls == [
        (
            "watch",
            {"run_id": RUN_ID, "timeout_seconds": 30.0, "poll_seconds": 1.5},
        )
    ]
    assert _FakeRuns.observed_client_open == [True, True]
    lines = _lines(result)
    assert len(lines) == 2
    assert [line["ok"] for line in lines] == [True, True]
    assert [line["data"]["run_status"]["state"] for line in lines] == [
        "RUNNING",
        "FINISHED",
    ]


def test_watch_text_streams_tab_separated_statuses() -> None:
    _FakeRuns.watch_statuses = [_status(RunState.RUNNING), _status(RunState.FINISHED)]
    result = runner.invoke(
        cli_module.app,
        ["run", "watch", RUN_ID, "--timeout", "30", "--output", "text"],
        env=_environment(),
    )

    assert result.exit_code == 0, result.output
    assert result.stdout == (
        f"{RUN_ID}\tRUNNING\t2026-08-11T10:11:12.456000Z\n"
        f"{RUN_ID}\tFINISHED\t2026-08-11T10:11:12.456000Z\n"
    )


def test_watch_failure_emits_terminal_status_then_one_json_error() -> None:
    failed = _status(
        RunState.FAILED,
        error=RunError.PROCESSING_FAILED,
        execution_status=RunExecutionStatus.FAILED,
    )
    _FakeRuns.watch_statuses = [_status(RunState.RUNNING), failed]

    result = runner.invoke(
        cli_module.app,
        ["run", "watch", RUN_ID, "--timeout", "30", "--output", "jsonl"],
        env=_environment(),
    )

    assert result.exit_code == 4, result.output
    lines = _lines(result)
    assert len(lines) == 3
    assert [line["ok"] for line in lines] == [True, True, False]
    assert lines[1]["data"]["run_status"]["state"] == "FAILED"
    assert lines[2]["data"] is None
    assert lines[2]["error"]["code"] == "RUN_FAILED"


def test_watch_timeout_emits_one_json_error_and_exit_six() -> None:
    _FakeRuns.watch_error = RunTimeoutError(
        run_id=RUN_ID,
        timeout_seconds=0.5,
        last_status=_status(RunState.RUNNING),
    )

    result = runner.invoke(
        cli_module.app,
        ["run", "watch", RUN_ID, "--timeout", "0.5", "--output", "jsonl"],
        env=_environment(),
    )

    assert result.exit_code == 6, result.output
    lines = _lines(result)
    assert len(lines) == 1
    assert lines[0]["ok"] is False
    assert lines[0]["data"] is None
    assert lines[0]["error"]["code"] == "RUN_TIMEOUT"


def test_wait_failure_emits_one_normal_json_error() -> None:
    _FakeRuns.wait_error = RunFailedError(_status(RunState.FAILED))

    result = runner.invoke(
        cli_module.app,
        ["run", "wait", RUN_ID, "--timeout", "30", "--output", "json"],
        env=_environment(),
    )

    assert result.exit_code == 4, result.output
    lines = _lines(result)
    assert len(lines) == 1
    assert lines[0]["ok"] is False
    assert lines[0]["data"] is None
    assert lines[0]["error"]["code"] == "RUN_FAILED"


def test_watch_does_not_add_jsonl_to_global_output_format() -> None:
    assert not hasattr(OutputFormat, "JSONL")
