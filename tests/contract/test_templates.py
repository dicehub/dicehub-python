from __future__ import annotations

import json
from datetime import datetime, timezone

import httpx
import pytest

from dicehub import (
    APIError,
    AuthenticationError,
    Client,
    ProtocolError,
    SortOrder,
    Template,
    TemplateOrderField,
    TemplatePage,
    TemplateTag,
    TemplateType,
)


def _client(handler: httpx.MockTransport) -> Client:
    return Client(
        base_url="https://dicehub.test",
        api_key="test-api-key",
        transport=handler,
    )


def _status(*, succeeded: bool = True, error: str | None = None) -> dict[str, object]:
    return {"succeeded": succeeded, "error": error}


def _template(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "templateId": "91",
        "name": "OpenFOAM snappyHexMesh",
        "slug": "openfoam_snappyhexmesh",
        "description": "A meshing and CFD workflow.",
        "clientType": "openfoam",
        "route": "/templates/openfoam_snappyhexmesh",
        "imagePath": "/assets/openfoam.png",
        "iconPath": "/assets/openfoam.svg",
        "tags": [{"tagId": "12", "tag": "CFD"}],
        "createdAt": "2026-08-13T09:10:11.123",
        "updatedAt": "2026-08-13T10:11:12.456+02:00",
    }
    payload.update(overrides)
    return payload


def _list_response(
    *,
    status: dict[str, object] | None = None,
    info: object = ...,
    templates: object = ...,
) -> dict[str, object]:
    if info is ...:
        info = {"offset": 2.0, "count": 1.0, "cursor": "next-cursor"}
    if templates is ...:
        templates = [_template()]
    return {
        "data": {
            "templates": {
                "listTemplates": {
                    "status": status or _status(),
                    "info": info,
                    "templates": templates,
                }
            }
        }
    }


def _single_response(
    field: str,
    *,
    template: object = ...,
    status: dict[str, object] | None = None,
) -> dict[str, object]:
    if template is ...:
        template = _template()
    return {
        "data": {
            "templates": {
                field: {
                    "status": status or _status(),
                    "template": template,
                }
            }
        }
    }


def _expected_template() -> Template:
    return Template(
        template_id="91",
        name="OpenFOAM snappyHexMesh",
        slug="openfoam_snappyhexmesh",
        description="A meshing and CFD workflow.",
        client_type="openfoam",
        route="/templates/openfoam_snappyhexmesh",
        image_path="/assets/openfoam.png",
        icon_path="/assets/openfoam.svg",
        tags=(TemplateTag(tag_id="12", tag="CFD"),),
        created_at=datetime(2026, 8, 13, 9, 10, 11, 123000, tzinfo=timezone.utc),
        updated_at=datetime(2026, 8, 13, 8, 11, 12, 456000, tzinfo=timezone.utc),
    )


def test_list_uses_fixed_variables_and_returns_typed_page() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert request.headers["authorization"] == "Bearer test-api-key"
        assert payload["operationName"] == "ListTemplates"
        assert payload["variables"] == {
            "searchFilter": "foam",
            "templateType": "MODEL_TEMPLATE",
            "tags": ["CFD", "meshing"],
            "orderBy": "updated_at",
            "order": "DESC",
            "offset": 2.0,
            "limit": 10.0,
            "cursor": "cursor-value",
        }
        query = payload["query"]
        assert "listTemplates" in query
        assert "$searchFilter: String" in query
        assert "$tags: [String]" in query
        assert "template_type" not in query
        return httpx.Response(200, json=_list_response(), request=request)

    with _client(httpx.MockTransport(handler)) as client:
        page = client.templates.list(
            search_filter="foam",
            template_type=TemplateType.MODEL_TEMPLATE,
            tags=["CFD", "meshing"],
            order_by=TemplateOrderField.UPDATED_AT,
            order=SortOrder.DESC,
            offset=2,
            limit=10,
            cursor="cursor-value",
        )

    assert page == TemplatePage(
        templates=(_expected_template(),),
        offset=2,
        count=1,
        cursor="next-cursor",
    )
    assert page.templates[0].created_at is not None
    assert page.templates[0].created_at.tzinfo is timezone.utc
    assert page.templates[0].updated_at is not None
    assert page.templates[0].updated_at.tzinfo is timezone.utc


def test_list_defaults_to_app_templates() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["variables"] == {
            "searchFilter": None,
            "templateType": "APP_TEMPLATE",
            "tags": None,
            "orderBy": "name",
            "order": "ASC",
            "offset": 0.0,
            "limit": 20.0,
            "cursor": None,
        }
        return httpx.Response(200, json=_list_response(), request=request)

    with _client(httpx.MockTransport(handler)) as client:
        client.templates.list()


def test_list_can_request_all_template_types() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["variables"]["templateType"] is None
        return httpx.Response(200, json=_list_response(), request=request)

    with _client(httpx.MockTransport(handler)) as client:
        client.templates.list(template_type=None)


def test_template_tags_are_canonicalized_by_numeric_id() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json=_list_response(
                templates=[
                    _template(
                        tags=[
                            {"tagId": "12", "tag": "CFD"},
                            {"tagId": "2", "tag": "meshing"},
                        ]
                    )
                ]
            ),
            request=request,
        )
    )

    with _client(transport) as client:
        template = client.templates.list().templates[0]

    assert template.tags == (
        TemplateTag(tag_id="2", tag="meshing"),
        TemplateTag(tag_id="12", tag="CFD"),
    )


@pytest.mark.parametrize(
    ("method", "argument", "operation_name", "field", "variables"),
    [
        ("get", {"template_id": "91"}, "GetTemplate", "getTemplateById", {"templateId": "91"}),
        (
            "get_by_route",
            {"route": "/templates/openfoam_snappyhexmesh"},
            "GetTemplateByRoute",
            "getTemplateByRoute",
            {"route": "/templates/openfoam_snappyhexmesh"},
        ),
    ],
)
def test_get_operations_use_fixed_variables_and_return_template(
    method: str,
    argument: dict[str, str],
    operation_name: str,
    field: str,
    variables: dict[str, str],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["operationName"] == operation_name
        assert payload["variables"] == variables
        assert field in payload["query"]
        assert str(next(iter(variables.values()))) not in payload["query"]
        return httpx.Response(200, json=_single_response(field), request=request)

    with _client(httpx.MockTransport(handler)) as client:
        template = getattr(client.templates, method)(**argument)

    assert template == _expected_template()


@pytest.mark.parametrize("operation", ["list", "get", "get_by_route"])
@pytest.mark.parametrize(
    ("server_error", "error_type"),
    [("AUTH_ERROR", AuthenticationError), ("sentinel-server-secret", APIError)],
)
def test_status_failures_are_generic(
    operation: str,
    server_error: str,
    error_type: type[Exception],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if operation == "list":
            response = _list_response(
                status=_status(succeeded=False, error=server_error),
                info=None,
                templates=None,
            )
        else:
            field = "getTemplateById" if operation == "get" else "getTemplateByRoute"
            response = _single_response(
                field,
                template=None,
                status=_status(succeeded=False, error=server_error),
            )
        return httpx.Response(200, json=response, request=request)

    with _client(httpx.MockTransport(handler)) as client, pytest.raises(error_type) as captured:
        if operation == "list":
            client.templates.list()
        elif operation == "get":
            client.templates.get(template_id="91")
        else:
            client.templates.get_by_route(route="/templates/missing")

    assert server_error not in str(captured.value)


@pytest.mark.parametrize(
    "response",
    [
        _list_response(info=None),
        _list_response(templates=None),
        _list_response(info={"offset": 0.5, "count": 1.0, "cursor": "next"}),
        _list_response(templates=[_template(templateId="01")]),
        _list_response(templates=[_template(createdAt="not-a-timestamp")]),
        _list_response(templates=[_template(secret="must-not-be-accepted")]),
    ],
)
def test_malformed_list_response_fails_closed(response: dict[str, object]) -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=response, request=request)
    )
    with _client(transport) as client, pytest.raises(ProtocolError) as captured:
        client.templates.list()

    assert "must-not-be-accepted" not in str(captured.value)
    assert captured.value.__context__ is None


@pytest.mark.parametrize("operation", ["get", "get_by_route"])
def test_success_without_template_fails_closed(operation: str) -> None:
    field = "getTemplateById" if operation == "get" else "getTemplateByRoute"
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json=_single_response(field, template=None),
            request=request,
        )
    )

    with _client(transport) as client, pytest.raises(ProtocolError):
        if operation == "get":
            client.templates.get(template_id="91")
        else:
            client.templates.get_by_route(route="/templates/missing")
