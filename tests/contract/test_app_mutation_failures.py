from __future__ import annotations

import httpx
import pytest

from dicehub import APIError, MutationOutcomeUnknownError
from tests.contract.test_apps import _client, _mutation_response, _status


@pytest.mark.parametrize("failure", ["transport", "protocol"])
def test_update_ambiguity_is_non_retryable_and_not_retried(failure: str) -> None:
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
        return httpx.Response(200, json={"data": {"apps": {}}}, request=request)

    with (
        _client(httpx.MockTransport(handler)) as client,
        pytest.raises(MutationOutcomeUnknownError) as captured,
    ):
        client.apps.update(app_id="101", description="Updated")

    assert request_count == 1
    assert captured.value.retryable is False
    assert "sentinel" not in str(captured.value)
    assert captured.value.__context__ is None
    assert captured.value.__cause__ is None


def test_update_maps_status_failure_without_server_details() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json=_mutation_response(
                "updateApp",
                status=_status(succeeded=False, error="sentinel-server-secret"),
            ),
            request=request,
        )
    )

    with _client(transport) as client, pytest.raises(APIError) as captured:
        client.apps.update(app_id="101", description="Updated")

    assert "sentinel-server-secret" not in str(captured.value)


@pytest.mark.parametrize("failure", ["transport", "protocol"])
def test_delete_ambiguity_is_non_retryable_and_not_retried(failure: str) -> None:
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
        return httpx.Response(200, json={"data": {"apps": {}}}, request=request)

    with (
        _client(httpx.MockTransport(handler)) as client,
        pytest.raises(MutationOutcomeUnknownError) as captured,
    ):
        client.apps.delete(app_id="101")

    assert request_count == 1
    assert captured.value.retryable is False
    assert "sentinel" not in str(captured.value)
    assert captured.value.__context__ is None
    assert captured.value.__cause__ is None


def test_delete_maps_status_failure_without_server_details() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json=_mutation_response(
                "deleteApp",
                status=_status(succeeded=False, error="sentinel-server-secret"),
            ),
            request=request,
        )
    )

    with _client(transport) as client, pytest.raises(APIError) as captured:
        client.apps.delete(app_id="101")

    assert "sentinel-server-secret" not in str(captured.value)
