from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

import httpx
import pytest

from dicehub import (
    APIError,
    AuthenticationError,
    Client,
    ConfigurationError,
    MutationOutcomeUnknownError,
    RunError,
    RunFlag,
    RunState,
    RunStatus,
)

RUN_ID = "12345678-1234-5678-9234-567812345678"
UPDATED_AT = "2026-08-11T10:11:12.456Z"
START_FIELDS = frozenset({"runId", "state", "executionStatus", "error", "flags", "updatedAt"})
SENSITIVE_FIELDS = frozenset(
    {
        "app",
        "creator",
        "creatorId",
        "environment",
        "estimatedCosts",
        "inputData",
        "outputData",
        "userData",
    }
)


def _client(handler: httpx.MockTransport, *, session: bool = False) -> Client:
    if session:
        return Client(
            base_url="https://dicehub.test",
            session_cookie="test-session",
            transport=handler,
        )
    return Client(
        base_url="https://dicehub.test",
        api_key="test-api-key",
        transport=handler,
    )


def _status(*, succeeded: bool = True, error: str | None = None) -> dict[str, object]:
    return {"succeeded": succeeded, "error": error}


def _run_status() -> dict[str, object]:
    return {
        "runId": RUN_ID,
        "state": "PREPARING",
        "executionStatus": None,
        "error": "NONE",
        "flags": ["NOTIFY"],
        "updatedAt": UPDATED_AT,
    }


def _start_response(
    *,
    status: dict[str, object] | None = None,
    run: object = ...,
) -> dict[str, object]:
    if run is ...:
        run = _run_status()
    return {
        "data": {
            "configs": {
                "startRun": {
                    "status": status or _status(),
                    "run": run,
                }
            }
        }
    }


def _stop_response(*, status: dict[str, object] | None = None) -> dict[str, object]:
    return {
        "data": {
            "runs": {
                "stopRun": {
                    "status": status or _status(),
                }
            }
        }
    }


def _selected_fields(query: str, marker: str) -> frozenset[str]:
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


def test_start_uses_fixed_config_mutation_and_returns_minimal_status() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        payload = json.loads(request.content)
        assert payload["operationName"] == "StartRun"
        assert payload["variables"] == {
            "configId": "301",
            "machineTypeId": "dh1_4x",
            "nodeCount": 2,
            "cpuCount": 8,
            "notify": True,
        }
        query = payload["query"]
        assert "configs" in query
        assert "startRun" in query
        fields = _selected_fields(query, "\n      run ")
        assert fields == START_FIELDS
        assert fields.isdisjoint(SENSITIVE_FIELDS)
        return httpx.Response(200, json=_start_response(), request=request)

    with _client(httpx.MockTransport(handler), session=True) as client:
        status = client.runs.start(
            config_id="301",
            machine_type_id="dh1_4x",
            node_count=2,
            cpu_count=8,
            notify=True,
        )

    assert calls == 1
    assert status == RunStatus(
        run_id=RUN_ID,
        state=RunState.PREPARING,
        execution_status=None,
        error=RunError.NONE,
        flags=(RunFlag.NOTIFY,),
        updated_at=datetime(2026, 8, 11, 10, 11, 12, 456000, tzinfo=timezone.utc),
    )


def test_start_defaults_are_explicit_graphql_variables() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["variables"] == {
            "configId": "301",
            "machineTypeId": "local",
            "nodeCount": 1,
            "cpuCount": None,
            "notify": False,
        }
        return httpx.Response(200, json=_start_response(), request=request)

    with _client(httpx.MockTransport(handler)) as client:
        client.runs.start(config_id="301", machine_type_id="local")


def test_stop_uses_fixed_run_mutation_once() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        payload = json.loads(request.content)
        assert payload["operationName"] == "StopRun"
        assert payload["variables"] == {"runId": RUN_ID}
        query = payload["query"]
        assert "runs" in query
        assert "stopRun(runId: $runId)" in query
        assert "run {" not in query
        return httpx.Response(200, json=_stop_response(), request=request)

    with _client(httpx.MockTransport(handler)) as client:
        client.runs.stop(run_id=RUN_ID.upper())

    assert calls == 1


def _invoke(client: Client, operation: str) -> object:
    if operation == "start":
        return client.runs.start(config_id="301", machine_type_id="local")
    client.runs.stop(run_id=RUN_ID)
    return None


@pytest.mark.parametrize(
    ("operation", "failure"),
    [
        ("start", "timeout"),
        ("start", "http"),
        ("start", "graphql"),
        ("start", "protocol"),
        ("stop", "timeout"),
        ("stop", "protocol"),
    ],
)
def test_mutation_ambiguity_is_mapped_and_never_retried(
    operation: str,
    failure: str,
) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if failure == "timeout":
            raise httpx.ReadTimeout("secret response", request=request)
        if failure == "http":
            return httpx.Response(502, content=b"secret response", request=request)
        if failure == "graphql":
            return httpx.Response(
                200,
                json={"errors": [{"message": "secret response"}]},
                request=request,
            )
        return httpx.Response(200, content=b"not-json secret response", request=request)

    with (
        _client(httpx.MockTransport(handler)) as client,
        pytest.raises(MutationOutcomeUnknownError) as captured,
    ):
        _invoke(client, operation)

    assert calls == 1
    assert captured.value.retryable is False
    assert "secret response" not in str(captured.value)
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None


def test_success_without_started_run_is_an_unknown_outcome() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_start_response(run=None), request=request)

    with (
        _client(httpx.MockTransport(handler)) as client,
        pytest.raises(MutationOutcomeUnknownError),
    ):
        client.runs.start(config_id="301", machine_type_id="local")


@pytest.mark.parametrize("operation", ["start", "stop"])
def test_server_status_failure_remains_a_definitive_api_error(operation: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        status = _status(succeeded=False, error="PERMISSIONS_ERROR")
        response = _start_response(status=status, run=None)
        if operation == "stop":
            response = _stop_response(status=status)
        return httpx.Response(200, json=response, request=request)

    with _client(httpx.MockTransport(handler)) as client, pytest.raises(APIError):
        _invoke(client, operation)


@pytest.mark.parametrize("operation", ["start", "stop"])
def test_mutation_authentication_failure_is_not_reported_as_ambiguous(operation: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, request=request)

    with _client(httpx.MockTransport(handler)) as client, pytest.raises(AuthenticationError):
        _invoke(client, operation)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"config_id": "0", "machine_type_id": "local"}, "Config id is invalid"),
        ({"config_id": "301", "machine_type_id": ""}, "Machine type ID is invalid"),
        ({"config_id": "301", "machine_type_id": "dh-4x"}, "Machine type ID is invalid"),
        (
            {"config_id": "301", "machine_type_id": "local", "node_count": 0},
            "Node count must be a positive",
        ),
        (
            {"config_id": "301", "machine_type_id": "local", "node_count": None},
            "Node count must be a positive",
        ),
        (
            {"config_id": "301", "machine_type_id": "local", "cpu_count": True},
            "Cpu count must be a positive",
        ),
        (
            {"config_id": "301", "machine_type_id": "local", "notify": 1},
            "Notify flag is invalid",
        ),
    ],
)
def test_start_rejects_invalid_inputs_before_transport(
    kwargs: dict[str, Any],
    message: str,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        pytest.fail("invalid input reached the transport")

    with (
        _client(httpx.MockTransport(handler)) as client,
        pytest.raises(ConfigurationError, match=message),
    ):
        client.runs.start(**kwargs)


def test_stop_rejects_invalid_run_id_before_transport() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        pytest.fail("invalid input reached the transport")

    with (
        _client(httpx.MockTransport(handler)) as client,
        pytest.raises(ConfigurationError, match="Run id is invalid"),
    ):
        client.runs.stop(run_id="not-a-run-id")
