from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from types import TracebackType
from typing import Any, ClassVar, cast

import pytest
from typer.testing import CliRunner

from dicehub import (
    MachinePrice,
    MachineType,
    Run,
    RunDetail,
    RunError,
    RunFlag,
    RunOrderField,
    RunPage,
    RunState,
    RunStatus,
    RunType,
    SortOrder,
)
from dicehub import cli as cli_module
from dicehub.cli.commands import run as run_commands

runner = CliRunner()
RUN_ID = "12345678-1234-5678-9234-567812345678"
STUDY_ID = "87654321-4321-6789-a234-567812345678"
CREATED_AT = datetime.fromisoformat("2026-08-11T09:10:11.123").replace(tzinfo=timezone.utc)
UPDATED_AT = datetime.fromisoformat("2026-08-11T10:11:12.456").replace(tzinfo=timezone.utc)


def _run() -> Run:
    return Run(
        run_id=RUN_ID,
        namespace_id="101",
        name="Baseline",
        state=RunState.RUNNING,
        run_type=RunType.REGULAR,
        created_at=CREATED_AT,
        updated_at=UPDATED_AT,
    )


def _detail() -> RunDetail:
    return RunDetail(
        **_run().model_dump(),
        run_internal_id=17,
        machine_type_id="local",
        node_count=2,
        cpu_count=8,
        execution_status=None,
        error=RunError.NONE,
        flags=(RunFlag.NOTIFY,),
        template_version="v13",
        module="solver",
        flow="solve",
        queue="default",
        study_id=STUDY_ID,
        stage=3,
        batch="batch-a",
    )


def _status() -> RunStatus:
    return RunStatus(
        run_id=RUN_ID,
        state=RunState.RUNNING,
        execution_status=None,
        error=RunError.NONE,
        flags=(RunFlag.NOTIFY,),
        updated_at=UPDATED_AT,
    )


def _machine_type() -> MachineType:
    return MachineType(
        machine_type_id="dh1_36x",
        cpu_count=36,
        gpu_count=0,
        ram_gb=192,
        description="36 CPU cores, 192 GB RAM",
        price=MachinePrice(amount=Decimal("5.66"), currency="EUR"),
    )


class _FakeRuns:
    calls: ClassVar[list[tuple[str, dict[str, object]]]] = []
    error: ClassVar[Exception | None] = None

    def list_machine_types(self) -> tuple[MachineType, ...]:
        if self.error is not None:
            raise self.error
        self.calls.append(("list_machine_types", {}))
        return (_machine_type(),)

    def list(
        self,
        *,
        namespace_id: str,
        include_descendants: bool = False,
        app_id: str | None = None,
        run_types: list[RunType] | None = None,
        states: list[RunState] | None = None,
        order_by: RunOrderField = RunOrderField.CREATED_AT,
        order: SortOrder = SortOrder.DESC,
        offset: int = 0,
        limit: int = 20,
        cursor: str | None = None,
    ) -> RunPage:
        if self.error is not None:
            raise self.error
        self.calls.append(
            (
                "list",
                {
                    "namespace_id": namespace_id,
                    "include_descendants": include_descendants,
                    "app_id": app_id,
                    "run_types": run_types,
                    "states": states,
                    "order_by": order_by,
                    "order": order,
                    "offset": offset,
                    "limit": limit,
                    "cursor": cursor,
                },
            )
        )
        return RunPage(runs=(_run(),), offset=offset, count=1, cursor="next")

    def get(self, *, run_id: str) -> RunDetail:
        if self.error is not None:
            raise self.error
        self.calls.append(("get", {"run_id": run_id}))
        return _detail()

    def status(self, *, run_id: str) -> RunStatus:
        if self.error is not None:
            raise self.error
        self.calls.append(("status", {"run_id": run_id}))
        return _status()


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


def test_list_uses_api_key_filters_and_emits_structured_page() -> None:
    result = runner.invoke(
        cli_module.app,
        [
            "run",
            "list",
            "41",
            "--include-descendants",
            "--app-id",
            "101",
            "--type",
            "regular",
            "--type",
            "prediction",
            "--state",
            "running",
            "--state",
            "pending",
            "--order-by",
            "updated_at",
            "--order",
            "asc",
            "--offset",
            "2",
            "--limit",
            "5",
            "--cursor",
            "opaque",
        ],
        env={
            "DICEHUB_API_KEY": "sentinel-api-key",
            "DICEHUB_URL": "https://dicehub.test",
        },
    )

    assert result.exit_code == 0, result.output
    assert _FakeClient.constructions == [
        {
            "base_url": "https://dicehub.test",
            "api_key": "sentinel-api-key",
            "session_cookie": None,
        }
    ]
    assert _FakeRuns.calls == [
        (
            "list",
            {
                "namespace_id": "41",
                "include_descendants": True,
                "app_id": "101",
                "run_types": [RunType.REGULAR, RunType.PREDICTION],
                "states": [RunState.RUNNING, RunState.PENDING],
                "order_by": RunOrderField.UPDATED_AT,
                "order": SortOrder.ASC,
                "offset": 2,
                "limit": 5,
                "cursor": "opaque",
            },
        )
    ]
    assert _json(result) == {
        "schema_version": "dicehub.cli/v1",
        "ok": True,
        "data": {
            "runs": [
                {
                    "run_id": RUN_ID,
                    "namespace_id": "101",
                    "name": "Baseline",
                    "state": "RUNNING",
                    "run_type": "REGULAR",
                    "created_at": "2026-08-11T09:10:11.123000Z",
                    "updated_at": "2026-08-11T10:11:12.456000Z",
                }
            ],
            "page": {"offset": 2, "count": 1, "cursor": "next"},
        },
        "error": None,
    }
    assert "sentinel-api-key" not in result.stdout + result.stderr


def test_machine_types_emits_default_json() -> None:
    result = runner.invoke(
        cli_module.app,
        ["run", "machine-types"],
        env={
            "DICEHUB_API_KEY": "sentinel-api-key",
            "DICEHUB_URL": "https://dicehub.test",
        },
    )

    assert result.exit_code == 0, result.output
    assert _FakeRuns.calls == [("list_machine_types", {})]
    assert _json(result) == {
        "schema_version": "dicehub.cli/v1",
        "ok": True,
        "data": {
            "machine_types": [
                {
                    "machine_type_id": "dh1_36x",
                    "cpu_count": 36,
                    "gpu_count": 0,
                    "ram_gb": 192,
                    "description": "36 CPU cores, 192 GB RAM",
                    "price": {"amount": "5.66", "currency": "EUR"},
                }
            ]
        },
        "error": None,
    }


@pytest.mark.parametrize(
    ("command", "expected_method", "data_key"),
    [("get", "get", "run"), ("status", "status", "run_status")],
)
def test_single_run_commands_emit_one_json_document(
    command: str,
    expected_method: str,
    data_key: str,
) -> None:
    result = runner.invoke(
        cli_module.app,
        ["run", command, RUN_ID, "--output", "json"],
        env={
            "DICEHUB_API_KEY": "sentinel-api-key",
            "DICEHUB_URL": "https://dicehub.test",
        },
    )

    assert result.exit_code == 0, result.output
    assert _FakeRuns.calls == [(expected_method, {"run_id": RUN_ID})]
    payload = _json(result)
    assert payload["ok"] is True
    assert payload["error"] is None
    assert payload["data"][data_key]["run_id"] == RUN_ID
    assert "sentinel-api-key" not in result.stdout + result.stderr


def test_text_status_is_tab_separated_and_terminal_safe() -> None:
    result = runner.invoke(
        cli_module.app,
        ["run", "status", RUN_ID, "--output", "text"],
        env={
            "DICEHUB_API_KEY": "sentinel-api-key",
            "DICEHUB_URL": "https://dicehub.test",
        },
    )

    assert result.exit_code == 0
    assert result.stdout == f"{RUN_ID}\tRUNNING\t2026-08-11T10:11:12.456000Z\n"


def test_default_list_is_exact_scope_and_newest_first() -> None:
    result = runner.invoke(
        cli_module.app,
        ["run", "list", "41"],
        env={
            "DICEHUB_API_KEY": "sentinel-api-key",
            "DICEHUB_URL": "https://dicehub.test",
        },
    )

    assert result.exit_code == 0
    _, arguments = _FakeRuns.calls[0]
    assert arguments["include_descendants"] is False
    assert arguments["order_by"] is RunOrderField.CREATED_AT
    assert arguments["order"] is SortOrder.DESC


def test_unexpected_failure_is_generic_and_redacts_credentials() -> None:
    _FakeRuns.error = RuntimeError("sentinel-api-key")
    result = runner.invoke(
        cli_module.app,
        ["run", "get", RUN_ID],
        env={
            "DICEHUB_API_KEY": "sentinel-api-key",
            "DICEHUB_URL": "https://dicehub.test",
        },
    )

    assert result.exit_code == 1
    payload = _json(result)
    assert payload["error"]["code"] == "DICEHUB_ERROR"
    assert "sentinel-api-key" not in result.stdout + result.stderr


def test_url_and_api_key_cannot_be_passed_as_options() -> None:
    result = runner.invoke(
        cli_module.app,
        ["run", "status", RUN_ID, "--url", "https://attacker.test", "--api-key", "secret"],
        env={
            "DICEHUB_API_KEY": "sentinel-api-key",
            "DICEHUB_URL": "https://dicehub.test",
        },
    )

    assert result.exit_code == 2
    assert _FakeClient.constructions == []
    assert "sentinel-api-key" not in result.stdout + result.stderr
