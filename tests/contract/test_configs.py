from __future__ import annotations

import json

import httpx
import pytest

from dicehub import (
    APIError,
    Client,
    Config,
    ConfigPage,
    ConfigValueUpdate,
    MutationOutcomeUnknownError,
    ProtocolError,
    SortOrder,
)


def _client(handler: httpx.MockTransport) -> Client:
    return Client(
        base_url="https://dicehub.test",
        api_key="test-api-key",
        transport=handler,
    )


def _config() -> dict[str, object]:
    return {
        "configId": "301",
        "appId": "101",
        "configInternalId": "7",
        "name": "Baseline",
        "description": "Reference setup",
        "isDefault": True,
        "templateVersion": "v13",
        "updating": False,
    }


def _list_response(
    *,
    status: dict[str, object] | None = None,
    info: object = ...,
    configs: object = ...,
) -> dict[str, object]:
    if info is ...:
        info = {"offset": 0.0, "count": 1.0, "cursor": "next-cursor"}
    if configs is ...:
        configs = [_config()]
    return {
        "data": {
            "configs": {
                "listConfigs": {
                    "status": status or {"succeeded": True, "error": None},
                    "info": info,
                    "configs": configs,
                }
            }
        }
    }


def _get_response(
    *,
    status: dict[str, object] | None = None,
    config: object = ...,
) -> dict[str, object]:
    if config is ...:
        config = _config()
    return {
        "data": {
            "configs": {
                "getSingleConfigById": {
                    "status": status or {"succeeded": True, "error": None},
                    "config": config,
                }
            }
        }
    }


def _create_response(
    *,
    status: dict[str, object] | None = None,
    config: object = ...,
) -> dict[str, object]:
    if config is ...:
        config = {**_config(), "isDefault": False}
    return {
        "data": {
            "configs": {
                "createConfig": {
                    "status": status or {"succeeded": True, "error": None},
                    "config": config,
                }
            }
        }
    }


def _delete_response(
    *,
    status: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "data": {
            "configs": {
                "deleteConfig": {
                    "status": status or {"succeeded": True, "error": None},
                }
            }
        }
    }


def _set_values_response(
    *,
    status: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "data": {
            "configs": {
                "setConfigValues": {
                    "status": status or {"succeeded": True, "error": None},
                }
            }
        }
    }


def test_list_uses_fixed_operation_and_returns_typed_page() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert request.headers["authorization"] == "Bearer test-api-key"
        assert payload["operationName"] == "ListConfigs"
        assert payload["variables"] == {
            "appId": "101",
            "searchFilter": "base",
            "order": "DESC",
            "offset": 2.0,
            "limit": 10.0,
            "cursor": "cursor-value",
        }
        assert 'orderBy: "config_id"' in payload["query"]
        assert "run {" not in payload["query"]
        return httpx.Response(200, json=_list_response(), request=request)

    with _client(httpx.MockTransport(handler)) as client:
        page = client.configs.list(
            app_id="101",
            search_filter="base",
            order=SortOrder.DESC,
            offset=2,
            limit=10,
            cursor="cursor-value",
        )

    assert page == ConfigPage(
        configs=(
            Config(
                config_id="301",
                app_id="101",
                config_internal_id="7",
                name="Baseline",
                description="Reference setup",
                is_default=True,
                template_version="v13",
                updating=False,
            ),
        ),
        offset=0,
        count=1,
        cursor="next-cursor",
    )


def test_get_uses_fixed_operation_and_returns_typed_config() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["operationName"] == "GetConfig"
        assert payload["variables"] == {"configId": "301"}
        assert "getSingleConfigById" in payload["query"]
        return httpx.Response(200, json=_get_response(), request=request)

    with _client(httpx.MockTransport(handler)) as client:
        config = client.configs.get(config_id="301")

    assert config.config_id == "301"
    assert config.app_id == "101"
    assert config.is_default is True


def test_create_uses_fixed_operation_and_returns_typed_config() -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        payload = json.loads(request.content)
        assert request.headers["authorization"] == "Bearer test-api-key"
        assert payload["operationName"] == "CreateConfig"
        assert payload["variables"] == {
            "appId": "101",
            "sourceConfigId": "301",
            "name": "Agent baseline",
            "description": "Created by automation",
        }
        assert "createConfig" in payload["query"]
        assert "configId: $sourceConfigId" in payload["query"]
        return httpx.Response(200, json=_create_response(), request=request)

    with _client(httpx.MockTransport(handler)) as client:
        config = client.configs.create(
            app_id="101",
            source_config_id="301",
            name="Agent baseline",
            description="Created by automation",
        )

    assert request_count == 1
    assert config.config_id == "301"
    assert config.app_id == "101"
    assert config.is_default is False


def test_create_success_without_config_has_unknown_outcome() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json=_create_response(config=None),
            request=request,
        )
    )

    with (
        _client(transport) as client,
        pytest.raises(MutationOutcomeUnknownError) as captured,
    ):
        client.configs.create(app_id="101")

    assert captured.value.retryable is False
    assert captured.value.__context__ is None


def test_delete_uses_fixed_operation_and_exact_id() -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        payload = json.loads(request.content)
        assert request.headers["authorization"] == "Bearer test-api-key"
        assert payload["operationName"] == "DeleteConfig"
        assert payload["variables"] == {"configId": "301"}
        assert "deleteConfig(configId: $configId)" in payload["query"]
        assert "301" not in payload["query"]
        assert "test-api-key" not in payload["query"]
        return httpx.Response(200, json=_delete_response(), request=request)

    with _client(httpx.MockTransport(handler)) as client:
        client.configs.delete(config_id="301")

    assert request_count == 1


def test_set_values_uses_fixed_operation_and_serializes_yaml_segments() -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        payload = json.loads(request.content)
        assert payload["operationName"] == "SetConfigValues"
        assert payload["variables"] == {
            "configId": "301",
            "path": "solver/control.YAML",
            "updates": [
                {"path": ["controlDict", "endTime"], "value": 200},
                {"path": ["key/with/slashes"], "value": None},
                {"path": ["controlDict", "writeAscii"], "value": True},
                {"path": ["controlDict", "solver"], "value": "simpleFoam"},
                {"path": ["controlDict", "maxCo"], "value": 0.5},
            ],
        }
        assert "setConfigValues" in payload["query"]
        assert "[ConfigValueUpdateInput!]!" in payload["query"]
        assert "test-api-key" not in payload["query"]
        return httpx.Response(200, json=_set_values_response(), request=request)

    with _client(httpx.MockTransport(handler)) as client:
        client.configs.set_values(
            config_id="301",
            path="solver/control.YAML",
            updates=(
                ConfigValueUpdate(path=("controlDict", "endTime"), value=200),
                ConfigValueUpdate(path=("key/with/slashes",), value=None),
                ConfigValueUpdate(path=("controlDict", "writeAscii"), value=True),
                ConfigValueUpdate(path=("controlDict", "solver"), value="simpleFoam"),
                ConfigValueUpdate(path=("controlDict", "maxCo"), value=0.5),
            ),
        )

    assert request_count == 1


def test_set_values_maps_ambiguous_outcome_without_retry() -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        raise httpx.ConnectError("sentinel transport details", request=request)

    with (
        _client(httpx.MockTransport(handler)) as client,
        pytest.raises(MutationOutcomeUnknownError) as captured,
    ):
        client.configs.set_values(
            config_id="301",
            path="solver/control.yaml",
            updates=(ConfigValueUpdate(path=("settings",), value=1.0),),
        )

    assert request_count == 1
    assert captured.value.retryable is False
    assert "sentinel" not in str(captured.value)
    assert captured.value.__context__ is None
    assert captured.value.__cause__ is None


@pytest.mark.parametrize("failure", ["transport", "http", "graphql", "protocol"])
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
        return httpx.Response(200, json={"data": {"configs": {}}}, request=request)

    with (
        _client(httpx.MockTransport(handler)) as client,
        pytest.raises(MutationOutcomeUnknownError) as captured,
    ):
        client.configs.delete(config_id="301")

    assert request_count == 1
    assert captured.value.retryable is False
    assert "sentinel" not in str(captured.value)
    assert captured.value.__context__ is None
    assert captured.value.__cause__ is None


def test_delete_maps_failed_status_without_server_details() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json=_delete_response(status={"succeeded": False, "error": "sentinel-server-secret"}),
            request=request,
        )
    )

    with _client(transport) as client, pytest.raises(APIError) as captured:
        client.configs.delete(config_id="301")

    assert "sentinel-server-secret" not in str(captured.value)


@pytest.mark.parametrize("failure", ["transport", "protocol"])
def test_create_ambiguity_is_non_retryable_and_not_retried(failure: str) -> None:
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
        return httpx.Response(200, json={"data": {"configs": {}}}, request=request)

    with (
        _client(httpx.MockTransport(handler)) as client,
        pytest.raises(MutationOutcomeUnknownError) as captured,
    ):
        client.configs.create(app_id="101")

    assert request_count == 1
    assert captured.value.retryable is False
    assert "sentinel" not in str(captured.value)
    assert captured.value.__context__ is None
    assert captured.value.__cause__ is None


@pytest.mark.parametrize(
    ("operation", "response"),
    [
        (
            "list",
            _list_response(status={"succeeded": False, "error": "PERMISSIONS_ERROR"}),
        ),
        (
            "get",
            _get_response(status={"succeeded": False, "error": "PERMISSIONS_ERROR"}),
        ),
    ],
)
def test_operations_raise_api_error_for_failed_status(
    operation: str,
    response: dict[str, object],
) -> None:
    handler = httpx.MockTransport(
        lambda request: httpx.Response(200, json=response, request=request)
    )

    with _client(handler) as client, pytest.raises(APIError) as caught:
        if operation == "list":
            client.configs.list(app_id="101")
        else:
            client.configs.get(config_id="301")

    assert caught.value.code == "API_ERROR"
    assert caught.value.message == "dicehub rejected the operation."


@pytest.mark.parametrize(
    ("operation", "response"),
    [
        ("list", _list_response(info=None)),
        ("list", _list_response(configs=None)),
        ("get", _get_response(config=None)),
        ("get", {"data": {"configs": {"unexpected": {}}}}),
    ],
)
def test_successful_but_incomplete_response_is_rejected(
    operation: str,
    response: dict[str, object],
) -> None:
    handler = httpx.MockTransport(
        lambda request: httpx.Response(200, json=response, request=request)
    )

    with _client(handler) as client, pytest.raises(ProtocolError):
        if operation == "list":
            client.configs.list(app_id="101")
        else:
            client.configs.get(config_id="301")


def test_untrusted_config_payload_is_strictly_validated() -> None:
    payload = _config()
    payload["configId"] = "../301"
    handler = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json=_get_response(config=payload),
            request=request,
        )
    )

    with _client(handler) as client, pytest.raises(ProtocolError):
        client.configs.get(config_id="301")
