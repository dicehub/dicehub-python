from __future__ import annotations

import json

import httpx
import pytest

from dicehub import (
    APIError,
    AuthenticationError,
    Client,
    MutationOutcomeUnknownError,
)
from tests.contract.test_projects import _client, _session_client, _status


def test_create_success_without_project_has_unknown_outcome() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "data": {
                    "projects": {
                        "createProject": {
                            "status": {"succeeded": True, "error": None},
                            "project": None,
                        }
                    }
                }
            },
            request=request,
        )
    )

    with (
        Client(
            base_url="https://dicehub.test",
            session_cookie="test-session-secret",
            transport=transport,
        ) as client,
        pytest.raises(MutationOutcomeUnknownError) as captured,
    ):
        client.projects.create(name="Demo", slug="demo")

    assert captured.value.retryable is False
    assert captured.value.__context__ is None


def test_api_key_create_transport_failure_is_unknown_and_not_retried() -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        raise httpx.ConnectError("sentinel transport details", request=request)

    with (
        Client(
            base_url="https://dicehub.test",
            api_key="sentinel-api-key",
            transport=httpx.MockTransport(handler),
        ) as client,
        pytest.raises(MutationOutcomeUnknownError) as captured,
    ):
        client.projects.create(name="Agent project", slug="agent-project")

    assert request_count == 1
    assert captured.value.retryable is False
    assert "sentinel" not in str(captured.value)
    assert captured.value.__context__ is None


@pytest.mark.parametrize("failure", ["transport", "http", "graphql", "protocol"])
def test_mutation_ambiguity_is_non_retryable_and_not_retried(failure: str) -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        if failure == "transport":
            raise httpx.ConnectError("sentinel transport details", request=request)
        if failure == "http":
            return httpx.Response(503, text="sentinel body", request=request)
        if failure == "graphql":
            return httpx.Response(
                200,
                json={"errors": [{"message": "sentinel GraphQL details"}]},
                request=request,
            )
        return httpx.Response(200, json={"data": {"projects": {}}}, request=request)

    with (
        _client(httpx.MockTransport(handler)) as client,
        pytest.raises(MutationOutcomeUnknownError) as captured,
    ):
        client.projects.delete(project_id="91")

    assert request_count == 1
    assert captured.value.code == "MUTATION_OUTCOME_UNKNOWN"
    assert captured.value.retryable is False
    assert "sentinel" not in str(captured.value)
    assert captured.value.__context__ is None
    assert captured.value.__cause__ is None


@pytest.mark.parametrize(
    ("response", "error_type"),
    [
        (httpx.Response(401), AuthenticationError),
        (
            httpx.Response(
                200,
                json={
                    "data": {
                        "projects": {
                            "deleteProject": {
                                "status": _status(succeeded=False, error="AUTH_ERROR")
                            }
                        }
                    }
                },
            ),
            AuthenticationError,
        ),
        (
            httpx.Response(
                200,
                json={
                    "data": {
                        "projects": {
                            "deleteProject": {"status": _status(succeeded=False, error="SENTINEL")}
                        }
                    }
                },
            ),
            APIError,
        ),
    ],
)
def test_mutation_authentication_and_status_failures_stay_typed(
    response: httpx.Response,
    error_type: type[Exception],
) -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            response.status_code,
            json=json.loads(response.content) if response.content else None,
            request=request,
        )
    )

    with _session_client(transport) as client, pytest.raises(error_type):
        client.projects.delete(project_id="91")
