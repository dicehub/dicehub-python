from __future__ import annotations

import json
import re
from datetime import datetime, timezone

import httpx
import pytest

from dicehub import (
    APIError,
    Client,
    ProtocolError,
    Run,
    RunDetail,
    RunError,
    RunExecutionStatus,
    RunFlag,
    RunOrderField,
    RunPage,
    RunState,
    RunStatus,
    RunType,
    SortOrder,
)

RUN_ID = "12345678-1234-5678-9234-567812345678"
STUDY_ID = "87654321-4321-6789-a234-567812345678"
CREATED_AT = "2026-08-11T09:10:11.123"
UPDATED_AT = "2026-08-11T10:11:12.456"

LIST_RUN_FIELDS = frozenset(
    {
        "runId",
        "namespaceId",
        "name",
        "state",
        "runType",
        "createdAt",
        "updatedAt",
    }
)
GET_RUN_FIELDS = frozenset(
    {
        "runId",
        "runInternalId",
        "namespaceId",
        "machineTypeId",
        "nodeCount",
        "cpuCount",
        "state",
        "createdAt",
        "updatedAt",
        "flags",
        "name",
        "executionStatus",
        "templateVersion",
        "error",
        "runType",
        "module",
        "flow",
        "queue",
        "studyId",
        "stage",
        "batch",
    }
)
STATUS_RUN_FIELDS = frozenset({"runId", "state", "executionStatus", "error", "flags", "updatedAt"})
SENSITIVE_RUN_FIELDS = frozenset(
    {
        "environment",
        "userData",
        "inputData",
        "outputData",
        "estimatedCosts",
        "creator",
        "creatorId",
        "app",
        "updating",
    }
)


def _selected_run_fields(query: str, marker: str) -> frozenset[str]:
    marker_start = query.index(marker)
    opening_brace = query.index("{", marker_start + len(marker))
    depth = 0
    closing_brace: int | None = None
    for index in range(opening_brace, len(query)):
        if query[index] == "{":
            depth += 1
        elif query[index] == "}":
            depth -= 1
            if depth == 0:
                closing_brace = index
                break

    assert closing_brace is not None
    fields = tuple(
        line.strip()
        for line in query[opening_brace + 1 : closing_brace].splitlines()
        if line.strip()
    )
    assert all(re.fullmatch(r"[_A-Za-z][_0-9A-Za-z]*", field) for field in fields)
    assert len(fields) == len(set(fields))
    return frozenset(fields)


def _assert_run_selection(
    query: str,
    *,
    marker: str,
    expected: frozenset[str],
) -> None:
    fields = _selected_run_fields(query, marker)
    assert fields == expected
    assert fields.isdisjoint(SENSITIVE_RUN_FIELDS)


def _client(handler: httpx.MockTransport) -> Client:
    return Client(
        base_url="https://dicehub.test",
        api_key="test-api-key",
        transport=handler,
    )


def _status(*, succeeded: bool = True, error: str | None = None) -> dict[str, object]:
    return {"succeeded": succeeded, "error": error}


def _run() -> dict[str, object]:
    return {
        "runId": RUN_ID,
        "namespaceId": "101",
        "name": "Baseline",
        "state": "RUNNING",
        "runType": "REGULAR",
        "createdAt": CREATED_AT,
        "updatedAt": UPDATED_AT,
    }


def _run_detail() -> dict[str, object]:
    return {
        **_run(),
        "runInternalId": 17,
        "machineTypeId": "local",
        "nodeCount": 2,
        "cpuCount": 8,
        "flags": ["NOTIFY", "ALWAYS_SYNCHRONIZE"],
        "executionStatus": None,
        "templateVersion": "v13",
        "error": "NONE",
        "module": "solver",
        "flow": "solve",
        "queue": "default",
        "studyId": STUDY_ID,
        "stage": 3,
        "batch": "batch-a",
    }


def _run_status() -> dict[str, object]:
    return {
        "runId": RUN_ID,
        "state": "RUNNING",
        "executionStatus": None,
        "error": "NONE",
        "flags": ["NOTIFY"],
        "updatedAt": UPDATED_AT,
    }


def _list_response(
    *,
    status: dict[str, object] | None = None,
    info: object = ...,
    runs: object = ...,
) -> dict[str, object]:
    if info is ...:
        info = {"offset": 2.0, "count": 1.0, "cursor": "next-cursor"}
    if runs is ...:
        runs = [_run()]
    return {
        "data": {
            "runs": {
                "listRunsByNamespaceId": {
                    "status": status or _status(),
                    "info": info,
                    "runs": runs,
                }
            }
        }
    }


def _single_response(run: object, *, status: dict[str, object] | None = None) -> dict[str, object]:
    return {
        "data": {
            "runs": {
                "getSingleRunById": {
                    "status": status or _status(),
                    "run": run,
                }
            }
        }
    }


def test_list_uses_fixed_operation_and_returns_typed_page() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert request.headers["authorization"] == "Bearer test-api-key"
        assert payload["operationName"] == "ListRuns"
        assert payload["variables"] == {
            "namespaceId": "41",
            "includeDescendants": True,
            "appId": "101",
            "runTypes": ["REGULAR", "PREDICTION"],
            "states": ["RUNNING", "PENDING"],
            "orderBy": "updated_at",
            "order": "ASC",
            "offset": 2,
            "limit": 10,
            "cursor": "cursor-value",
        }
        query = payload["query"]
        assert "listRunsByNamespaceId" in query
        _assert_run_selection(
            query,
            marker="\n      runs ",
            expected=LIST_RUN_FIELDS,
        )
        return httpx.Response(200, json=_list_response(), request=request)

    with _client(httpx.MockTransport(handler)) as client:
        page = client.runs.list(
            namespace_id="41",
            include_descendants=True,
            app_id="101",
            run_types=[RunType.REGULAR, RunType.PREDICTION],
            states=[RunState.RUNNING, RunState.PENDING],
            order_by=RunOrderField.UPDATED_AT,
            order=SortOrder.ASC,
            offset=2,
            limit=10,
            cursor="cursor-value",
        )

    assert page == RunPage(
        runs=(
            Run(
                run_id=RUN_ID,
                namespace_id="101",
                name="Baseline",
                state=RunState.RUNNING,
                run_type=RunType.REGULAR,
                created_at=datetime.fromisoformat(CREATED_AT).replace(tzinfo=timezone.utc),
                updated_at=datetime.fromisoformat(UPDATED_AT).replace(tzinfo=timezone.utc),
            ),
        ),
        offset=2,
        count=1,
        cursor="next-cursor",
    )


def test_get_uses_safe_fixed_selection_and_returns_typed_detail() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["operationName"] == "GetRun"
        assert payload["variables"] == {"runId": RUN_ID}
        query = payload["query"]
        _assert_run_selection(
            query,
            marker="\n      run ",
            expected=GET_RUN_FIELDS,
        )
        return httpx.Response(200, json=_single_response(_run_detail()), request=request)

    with _client(httpx.MockTransport(handler)) as client:
        detail = client.runs.get(run_id=RUN_ID.upper())

    assert detail == RunDetail(
        run_id=RUN_ID,
        namespace_id="101",
        name="Baseline",
        state=RunState.RUNNING,
        run_type=RunType.REGULAR,
        created_at=datetime.fromisoformat(CREATED_AT).replace(tzinfo=timezone.utc),
        updated_at=datetime.fromisoformat(UPDATED_AT).replace(tzinfo=timezone.utc),
        run_internal_id=17,
        machine_type_id="local",
        node_count=2,
        cpu_count=8,
        flags=(RunFlag.NOTIFY, RunFlag.ALWAYS_SYNCHRONIZE),
        execution_status=None,
        template_version="v13",
        error=RunError.NONE,
        module="solver",
        flow="solve",
        queue="default",
        study_id=STUDY_ID,
        stage=3,
        batch="batch-a",
    )


def test_get_accepts_server_unbounded_metadata_strings() -> None:
    metadata = "x" * 2048
    response = {
        **_run_detail(),
        "name": metadata,
        "machineTypeId": metadata,
        "templateVersion": metadata,
        "module": metadata,
        "flow": metadata,
        "queue": metadata,
        "batch": metadata,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_single_response(response), request=request)

    with _client(httpx.MockTransport(handler)) as client:
        detail = client.runs.get(run_id=RUN_ID)

    assert detail.name == metadata
    assert detail.machine_type_id == metadata
    assert detail.template_version == metadata
    assert detail.module == metadata
    assert detail.flow == metadata
    assert detail.queue == metadata
    assert detail.batch == metadata


def test_status_uses_a_distinct_minimal_operation() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["operationName"] == "GetRunStatus"
        assert payload["variables"] == {"runId": RUN_ID}
        query = payload["query"]
        _assert_run_selection(
            query,
            marker="\n      run ",
            expected=STATUS_RUN_FIELDS,
        )
        return httpx.Response(200, json=_single_response(_run_status()), request=request)

    with _client(httpx.MockTransport(handler)) as client:
        status = client.runs.status(run_id=RUN_ID)

    assert status == RunStatus(
        run_id=RUN_ID,
        state=RunState.RUNNING,
        execution_status=None,
        error=RunError.NONE,
        flags=(RunFlag.NOTIFY,),
        updated_at=datetime.fromisoformat(UPDATED_AT).replace(tzinfo=timezone.utc),
    )


def test_terminal_execution_status_is_preserved_separately_from_state() -> None:
    response = _run_status()
    response.update(
        {
            "state": "SYNCHRONIZING",
            "executionStatus": "FINISHED",
            "error": None,
            "flags": None,
        }
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_single_response(response), request=request)

    with _client(httpx.MockTransport(handler)) as client:
        status = client.runs.status(run_id=RUN_ID)

    assert status.state is RunState.SYNCHRONIZING
    assert status.execution_status is RunExecutionStatus.FINISHED
    assert status.flags == ()


@pytest.mark.parametrize(
    ("timestamp", "expected"),
    [
        (
            "2026-08-11T10:11:12.456",
            datetime(2026, 8, 11, 10, 11, 12, 456000, tzinfo=timezone.utc),
        ),
        (
            "2026-08-11T10:11:12.456Z",
            datetime(2026, 8, 11, 10, 11, 12, 456000, tzinfo=timezone.utc),
        ),
        (
            "2026-08-11T12:11:12.456+02:00",
            datetime(2026, 8, 11, 10, 11, 12, 456000, tzinfo=timezone.utc),
        ),
    ],
)
def test_status_normalizes_server_timestamps_to_aware_utc(
    timestamp: str,
    expected: datetime,
) -> None:
    response = {**_run_status(), "updatedAt": timestamp}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_single_response(response), request=request)

    with _client(httpx.MockTransport(handler)) as client:
        status = client.runs.status(run_id=RUN_ID)

    assert status.updated_at == expected
    assert status.updated_at.tzinfo is timezone.utc


@pytest.mark.parametrize("operation", ["list", "get", "status"])
def test_server_status_failure_is_mapped(operation: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if operation == "list":
            response = _list_response(status=_status(succeeded=False, error="PERMISSIONS_ERROR"))
        else:
            response = _single_response(
                None,
                status=_status(succeeded=False, error="PERMISSIONS_ERROR"),
            )
        return httpx.Response(200, json=response, request=request)

    with _client(httpx.MockTransport(handler)) as client, pytest.raises(APIError):
        if operation == "list":
            client.runs.list(namespace_id="41")
        else:
            getattr(client.runs, operation)(run_id=RUN_ID)


@pytest.mark.parametrize(
    "response",
    [
        _list_response(info=None),
        _list_response(runs=None),
        _list_response(runs=[{**_run(), "state": "UNKNOWN"}]),
        _list_response(runs=[{**_run(), "createdAt": "not-a-timestamp"}]),
        _list_response(info={"offset": 0.5, "count": 1.0, "cursor": "next"}),
    ],
)
def test_malformed_list_response_fails_closed(response: dict[str, object]) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=response, request=request)

    with _client(httpx.MockTransport(handler)) as client, pytest.raises(ProtocolError):
        client.runs.list(namespace_id="41")


@pytest.mark.parametrize("operation", ["get", "status"])
def test_success_without_run_fails_closed(operation: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_single_response(None), request=request)

    with _client(httpx.MockTransport(handler)) as client, pytest.raises(ProtocolError):
        getattr(client.runs, operation)(run_id=RUN_ID)


@pytest.mark.parametrize(
    ("operation", "run"),
    [
        ("get", {**_run_detail(), "inputData": ["private-input"]}),
        ("status", {**_run_status(), "machineTypeId": "not-in-status-contract"}),
    ],
)
def test_single_run_responses_reject_fields_outside_the_fixed_contract(
    operation: str,
    run: dict[str, object],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_single_response(run), request=request)

    with _client(httpx.MockTransport(handler)) as client, pytest.raises(ProtocolError):
        getattr(client.runs, operation)(run_id=RUN_ID)
