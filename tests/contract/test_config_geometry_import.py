from __future__ import annotations

import json
import re
from datetime import datetime, timezone

import httpx
import pytest

from dicehub import (
    APIError,
    Client,
    GeometryImportRuns,
    MutationOutcomeUnknownError,
    RunError,
    RunState,
    RunStatus,
)

CONVERSION_RUN_ID = "12345678-1234-5678-9234-567812345678"
SETUP_RUN_ID = "87654321-4321-6789-9234-567812345678"
UPDATED_AT = "2026-08-13T10:11:12.456Z"
RUN_FIELDS = frozenset({"runId", "state", "executionStatus", "error", "flags", "updatedAt"})


def _client(handler: httpx.MockTransport) -> Client:
    return Client(
        base_url="https://dicehub.test",
        api_key="test-api-key",
        transport=handler,
    )


def _response(
    *,
    succeeded: bool = True,
    error: str | None = None,
    conversion_run: object = ...,
    setup_run: object = ...,
) -> dict[str, object]:
    if conversion_run is ...:
        conversion_run = {
            "runId": CONVERSION_RUN_ID,
            "state": "PREPARING",
            "executionStatus": None,
            "error": "NONE",
            "flags": [],
            "updatedAt": UPDATED_AT,
        }
    if setup_run is ...:
        setup_run = {
            "runId": SETUP_RUN_ID,
            "state": "IDLE",
            "executionStatus": None,
            "error": None,
            "flags": [],
            "updatedAt": UPDATED_AT,
        }
    return {
        "data": {
            "configs": {
                "importConfigGeometry": {
                    "status": {"succeeded": succeeded, "error": error},
                    "conversionRun": conversion_run,
                    "setupRun": setup_run,
                }
            }
        }
    }


def _selected_run_fields(query: str, field: str) -> frozenset[str]:
    opening = query.index("{", query.index(f"\n      {field} "))
    closing = query.index("}", opening)
    fields = tuple(
        line.strip() for line in query[opening + 1 : closing].splitlines() if line.strip()
    )
    assert all(re.fullmatch(r"[_A-Za-z][_0-9A-Za-z]*", field) for field in fields)
    return frozenset(fields)


def test_import_geometry_uses_fixed_minimal_mutation_once() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        payload = json.loads(request.content)
        assert payload["operationName"] == "ImportConfigGeometry"
        assert payload["variables"] == {"configId": "301", "filename": "cube.stl"}
        query = payload["query"]
        assert "importConfigGeometry(configId: $configId, filename: $filename)" in query
        assert "createRun" not in query
        assert _selected_run_fields(query, "conversionRun") == RUN_FIELDS
        assert _selected_run_fields(query, "setupRun") == RUN_FIELDS
        for forbidden in ("module", "flow", "environment", "inputData", "outputData"):
            assert forbidden not in query
        return httpx.Response(200, json=_response(), request=request)

    with _client(httpx.MockTransport(handler)) as client:
        runs = client.configs.import_geometry(config_id="301", filename="cube.stl")

    assert calls == 1
    assert runs == GeometryImportRuns(
        conversion_run=RunStatus(
            run_id=CONVERSION_RUN_ID,
            state=RunState.PREPARING,
            execution_status=None,
            error=RunError.NONE,
            flags=(),
            updated_at=datetime(2026, 8, 13, 10, 11, 12, 456000, tzinfo=timezone.utc),
        ),
        setup_run=RunStatus(
            run_id=SETUP_RUN_ID,
            state=RunState.IDLE,
            execution_status=None,
            error=None,
            flags=(),
            updated_at=datetime(2026, 8, 13, 10, 11, 12, 456000, tzinfo=timezone.utc),
        ),
    )


@pytest.mark.parametrize("failure", ["transport", "protocol"])
def test_import_geometry_ambiguity_is_not_retried(failure: str) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if failure == "transport":
            raise httpx.ReadTimeout("sentinel details", request=request)
        if failure == "http":
            return httpx.Response(503, text="sentinel body", request=request)
        if failure == "graphql":
            return httpx.Response(200, json={"errors": [{"message": "sentinel"}]}, request=request)
        return httpx.Response(200, json={"data": {"configs": {}}}, request=request)

    with (
        _client(httpx.MockTransport(handler)) as client,
        pytest.raises(MutationOutcomeUnknownError) as captured,
    ):
        client.configs.import_geometry(config_id="301", filename="cube.stl")

    assert calls == 1
    assert captured.value.retryable is False
    assert "sentinel" not in str(captured.value)
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None


def test_import_geometry_success_without_conversion_run_is_unknown() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json=_response(conversion_run=None),
            request=request,
        )
    )

    with _client(transport) as client, pytest.raises(MutationOutcomeUnknownError):
        client.configs.import_geometry(config_id="301", filename="cube.stl")


def test_import_geometry_allows_no_setup_for_a_later_geometry() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json=_response(setup_run=None),
            request=request,
        )
    )

    with _client(transport) as client:
        runs = client.configs.import_geometry(config_id="301", filename="cube.stl")

    assert runs.conversion_run.run_id == CONVERSION_RUN_ID
    assert runs.setup_run is None


def test_import_geometry_definitive_rejection_remains_api_error() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json=_response(
                succeeded=False,
                error="PERMISSIONS_ERROR",
                conversion_run=None,
                setup_run=None,
            ),
            request=request,
        )
    )

    with _client(transport) as client, pytest.raises(APIError):
        client.configs.import_geometry(config_id="301", filename="cube.stl")
