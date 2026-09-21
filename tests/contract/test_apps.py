from __future__ import annotations

import json

import httpx
import pytest

from dicehub import (
    APIError,
    App,
    AppDetail,
    AppOrderField,
    AppPage,
    AppType,
    AppVisibility,
    AuthenticationError,
    Client,
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


def _status(*, succeeded: bool = True, error: str | None = None) -> dict[str, object]:
    return {"succeeded": succeeded, "error": error}


def _app() -> dict[str, object]:
    return {
        "appId": "101",
        "projectId": "41",
        "name": "Wind tunnel",
        "displayRoute": "engineering / airfoil / Wind tunnel",
        "route": "/engineering/airfoil/101",
        "visibility": "PRIVATE",
        "appType": "REGULAR",
    }


def _app_detail() -> dict[str, object]:
    return {
        **_app(),
        "description": "Transient CFD study",
        "templateId": "9",
        "templateName": "OpenFOAM",
        "templateVersion": "v13",
        "templateSlug": "openfoam",
        "iconPath": "/assets/openfoam.svg",
        "previewUrl": None,
    }


def _list_response(
    *,
    status: dict[str, object] | None = None,
    info: object = ...,
    apps: object = ...,
) -> dict[str, object]:
    if info is ...:
        info = {"offset": 0.0, "count": 1.0, "cursor": "next-cursor"}
    if apps is ...:
        apps = [_app()]
    return {
        "data": {
            "apps": {
                "listApps": {
                    "status": status or _status(),
                    "info": info,
                    "apps": apps,
                }
            }
        }
    }


def _single_response(field: str) -> dict[str, object]:
    return {
        "data": {
            "apps": {
                field: {
                    "status": _status(),
                    "app": _app_detail(),
                }
            }
        }
    }


def _mutation_response(
    field: str,
    *,
    status: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "data": {
            "apps": {
                field: {
                    "status": status or _status(),
                }
            }
        }
    }


def test_list_uses_fixed_operation_and_returns_typed_page() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert request.headers["authorization"] == "Bearer test-api-key"
        assert payload["operationName"] == "ListApps"
        assert payload["variables"] == {
            "projectId": "41",
            "searchFilter": "wind",
            "orderBy": "updated_at",
            "order": "DESC",
            "offset": 2.0,
            "limit": 10.0,
            "cursor": "cursor-value",
            "isPublished": None,
        }
        assert "listApps" in payload["query"]
        assert "description" not in payload["query"]
        assert "defaultConfigId" not in payload["query"]
        return httpx.Response(200, json=_list_response(), request=request)

    with _client(httpx.MockTransport(handler)) as client:
        page = client.apps.list(
            project_id="41",
            search_filter="wind",
            order_by=AppOrderField.UPDATED_AT,
            order=SortOrder.DESC,
            offset=2,
            limit=10,
            cursor="cursor-value",
        )

    assert page == AppPage(
        apps=(
            App(
                app_id="101",
                project_id="41",
                name="Wind tunnel",
                display_route="engineering / airfoil / Wind tunnel",
                route="/engineering/airfoil/101",
                visibility=AppVisibility.PRIVATE,
                app_type=AppType.REGULAR,
            ),
        ),
        offset=0,
        count=1,
        cursor="next-cursor",
    )


@pytest.mark.parametrize(
    ("method", "argument", "operation_name", "field"),
    [
        ("get", {"app_id": "101"}, "GetApp", "getAppById"),
        (
            "get_by_route",
            {"route": "/engineering/airfoil/101"},
            "GetAppByRoute",
            "getAppByRoute",
        ),
    ],
)
def test_get_operations_return_typed_detail(
    method: str,
    argument: dict[str, str],
    operation_name: str,
    field: str,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["operationName"] == operation_name
        if method == "get":
            assert payload["variables"] == {"appId": "101"}
        else:
            assert payload["variables"] == {"route": "/engineering/airfoil/101"}
        return httpx.Response(200, json=_single_response(field), request=request)

    with _client(httpx.MockTransport(handler)) as client:
        detail = getattr(client.apps, method)(**argument)

    assert detail == AppDetail(
        app_id="101",
        project_id="41",
        name="Wind tunnel",
        display_route="engineering / airfoil / Wind tunnel",
        route="/engineering/airfoil/101",
        visibility=AppVisibility.PRIVATE,
        app_type=AppType.REGULAR,
        description="Transient CFD study",
        template_id="9",
        template_name="OpenFOAM",
        template_version="v13",
        template_slug="openfoam",
        icon_path="/assets/openfoam.svg",
        preview_url=None,
    )


def test_create_uses_fixed_operation_and_returns_typed_detail() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert request.headers["authorization"] == "Bearer test-api-key"
        assert payload["operationName"] == "CreateApp"
        assert payload["variables"] == {
            "projectId": "41",
            "templateId": "9",
            "name": "Agent wind tunnel",
            "description": "Created by automation",
        }
        assert "createApp" in payload["query"]
        assert "$projectId: String!" in payload["query"]
        assert "$templateId: String!" in payload["query"]
        return httpx.Response(200, json=_single_response("createApp"), request=request)

    with _client(httpx.MockTransport(handler)) as client:
        detail = client.apps.create(
            project_id="41",
            template_id="9",
            name="Agent wind tunnel",
            description="Created by automation",
        )

    assert detail == AppDetail(
        app_id="101",
        project_id="41",
        name="Wind tunnel",
        display_route="engineering / airfoil / Wind tunnel",
        route="/engineering/airfoil/101",
        visibility=AppVisibility.PRIVATE,
        app_type=AppType.REGULAR,
        description="Transient CFD study",
        template_id="9",
        template_name="OpenFOAM",
        template_version="v13",
        template_slug="openfoam",
        icon_path="/assets/openfoam.svg",
        preview_url=None,
    )


def test_update_uses_fixed_operation_without_follow_up_read() -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        payload = json.loads(request.content)
        assert request.headers["authorization"] == "Bearer test-api-key"
        assert payload["operationName"] == "UpdateApp"
        assert payload["variables"] == {
            "appId": "101",
            "name": "Updated wind tunnel",
            "description": "Updated by automation",
        }
        assert "updateApp" in payload["query"]
        return httpx.Response(
            200,
            json=_mutation_response("updateApp"),
            request=request,
        )

    with _client(httpx.MockTransport(handler)) as client:
        client.apps.update(
            app_id="101",
            name="Updated wind tunnel",
            description="Updated by automation",
        )

    assert request_count == 1


def test_delete_uses_fixed_operation_without_follow_up_read() -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        payload = json.loads(request.content)
        assert request.headers["authorization"] == "Bearer test-api-key"
        assert payload["operationName"] == "DeleteApp"
        assert payload["variables"] == {"appId": "101"}
        assert "deleteApp" in payload["query"]
        return httpx.Response(
            200,
            json=_mutation_response("deleteApp"),
            request=request,
        )

    with _client(httpx.MockTransport(handler)) as client:
        client.apps.delete(app_id="101")

    assert request_count == 1


def test_list_forwards_explicit_publication_filter() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["variables"]["isPublished"] is True
        return httpx.Response(200, json=_list_response(), request=request)

    with _client(httpx.MockTransport(handler)) as client:
        client.apps.list(project_id="41", is_published=True)


@pytest.mark.parametrize(
    ("server_error", "error_type"),
    [("AUTH_ERROR", AuthenticationError), ("sentinel-server-secret", APIError)],
)
def test_list_maps_status_failure_without_server_details(
    server_error: str,
    error_type: type[Exception],
) -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json=_list_response(
                status=_status(succeeded=False, error=server_error),
                info=None,
                apps=None,
            ),
            request=request,
        )
    )

    with _client(transport) as client, pytest.raises(error_type) as captured:
        client.apps.list(project_id="41")

    assert server_error not in str(captured.value)


@pytest.mark.parametrize(
    ("info", "apps"),
    [
        (None, []),
        ({"offset": 0.5, "count": 1.0, "cursor": "cursor"}, []),
        ({"offset": 0.0, "count": 1.0, "cursor": "cursor"}, None),
        (
            {"offset": 0.0, "count": 1.0, "cursor": "cursor"},
            [{**_app(), "appId": "01"}],
        ),
    ],
)
def test_list_rejects_incompatible_success_payload(info: object, apps: object) -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json=_list_response(info=info, apps=apps),
            request=request,
        )
    )

    with _client(transport) as client, pytest.raises(ProtocolError) as captured:
        client.apps.list(project_id="41")

    assert captured.value.__context__ is None


def test_get_rejects_success_without_app() -> None:
    response = _single_response("getAppById")
    response["data"]["apps"]["getAppById"]["app"] = None  # type: ignore[index]
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=response, request=request)
    )

    with _client(transport) as client, pytest.raises(ProtocolError):
        client.apps.get(app_id="101")


def test_create_success_without_app_has_unknown_outcome() -> None:
    response = _single_response("createApp")
    response["data"]["apps"]["createApp"]["app"] = None  # type: ignore[index]
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=response, request=request)
    )

    with (
        _client(transport) as client,
        pytest.raises(MutationOutcomeUnknownError) as captured,
    ):
        client.apps.create(project_id="41", template_id="9", name="Agent app")

    assert captured.value.retryable is False
    assert captured.value.__context__ is None


@pytest.mark.parametrize("failure", ["transport", "http", "graphql", "protocol"])
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
        return httpx.Response(200, json={"data": {"apps": {}}}, request=request)

    with (
        _client(httpx.MockTransport(handler)) as client,
        pytest.raises(MutationOutcomeUnknownError) as captured,
    ):
        client.apps.create(project_id="41", template_id="9", name="Agent app")

    assert request_count == 1
    assert captured.value.retryable is False
    assert "sentinel" not in str(captured.value)
    assert captured.value.__context__ is None
    assert captured.value.__cause__ is None


@pytest.mark.parametrize(
    ("server_error", "error_type"),
    [("AUTH_ERROR", AuthenticationError), ("sentinel-server-secret", APIError)],
)
def test_create_maps_status_failure_without_server_details(
    server_error: str,
    error_type: type[Exception],
) -> None:
    response = _single_response("createApp")
    operation = response["data"]["apps"]["createApp"]  # type: ignore[index]
    operation["status"] = _status(succeeded=False, error=server_error)
    operation["app"] = None
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=response, request=request)
    )

    with _client(transport) as client, pytest.raises(error_type) as captured:
        client.apps.create(project_id="41", template_id="9", name="Agent app")

    assert server_error not in str(captured.value)
