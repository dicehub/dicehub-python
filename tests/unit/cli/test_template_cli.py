from __future__ import annotations

import json
from datetime import datetime, timezone
from types import TracebackType
from typing import Any, ClassVar, cast

import pytest
from typer.testing import CliRunner

from dicehub import APIError, Template, TemplatePage, TemplateTag
from dicehub import cli as cli_module
from dicehub.cli.commands import template as template_commands
from dicehub.projects import SortOrder
from dicehub.templates import TemplateOrderField, TemplateType

runner = CliRunner()


def _template(*, name: str = "Hex mesher") -> Template:
    return Template(
        template_id="12",
        name=name,
        slug="openfoam_snappyhexmesh",
        description="Hexahedral meshing",
        client_type="openfoam",
        route="/templates/openfoam_snappyhexmesh",
        image_path="images/mesh.webp",
        icon_path="icons/mesh.svg",
        tags=(TemplateTag(tag_id="5", tag="snappyHexMesh"),),
        created_at=datetime(2026, 8, 13, 8, tzinfo=timezone.utc),
        updated_at=datetime(2026, 8, 13, 9, tzinfo=timezone.utc),
    )


class _FakeTemplates:
    calls: ClassVar[list[tuple[str, dict[str, object]]]] = []
    error: ClassVar[Exception | None] = None
    result: ClassVar[Template] = _template()

    def _record(self, name: str, values: dict[str, object]) -> None:
        self.calls.append((name, values))
        if self.error is not None:
            raise self.error

    def list(
        self,
        *,
        search_filter: str | None = None,
        template_type: TemplateType | None = TemplateType.APP_TEMPLATE,
        tags: list[str] | None = None,
        order_by: TemplateOrderField = TemplateOrderField.NAME,
        order: SortOrder = SortOrder.ASC,
        offset: int = 0,
        limit: int = 20,
        cursor: str | None = None,
    ) -> TemplatePage:
        self._record(
            "list",
            {
                "search_filter": search_filter,
                "template_type": template_type,
                "tags": tags,
                "order_by": order_by,
                "order": order,
                "offset": offset,
                "limit": limit,
                "cursor": cursor,
            },
        )
        return TemplatePage(templates=(_template(),), offset=offset, count=1, cursor="next")

    def get(self, *, template_id: str) -> Template:
        self._record("get", {"template_id": template_id})
        return self.result

    def get_by_route(self, *, route: str) -> Template:
        self._record("get_by_route", {"route": route})
        return self.result


class _FakeClient:
    templates = _FakeTemplates()
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
    _FakeTemplates.calls = []
    _FakeTemplates.error = None
    _FakeTemplates.result = _template()
    _FakeClient.constructions = []
    monkeypatch.delenv("DICEHUB_API_KEY", raising=False)
    monkeypatch.delenv("DICEHUB_SESSION_COOKIE", raising=False)
    monkeypatch.delenv("DICEHUB_URL", raising=False)
    monkeypatch.setattr(template_commands, "Client", _FakeClient)


def _json(result: Any) -> dict[str, Any]:
    assert result.stderr == ""
    assert result.stdout.count("\n") == 1
    payload = json.loads(result.stdout)
    assert isinstance(payload, dict)
    return cast(dict[str, Any], payload)


def test_list_emits_structured_page_and_passes_filters() -> None:
    result = runner.invoke(
        cli_module.app,
        [
            "template",
            "list",
            "--search-filter",
            "mesh",
            "--type",
            "model_template",
            "--tag",
            "openfoam",
            "--tag",
            "mesher",
            "--order-by",
            "updated_at",
            "--order",
            "desc",
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

    assert result.exit_code == 0
    assert _FakeClient.constructions == [
        {
            "base_url": "https://dicehub.test",
            "api_key": "sentinel-api-key",
            "session_cookie": None,
        }
    ]
    assert _FakeTemplates.calls == [
        (
            "list",
            {
                "search_filter": "mesh",
                "template_type": TemplateType.MODEL_TEMPLATE,
                "tags": ["openfoam", "mesher"],
                "order_by": TemplateOrderField.UPDATED_AT,
                "order": SortOrder.DESC,
                "offset": 2,
                "limit": 5,
                "cursor": "opaque",
            },
        )
    ]
    payload = _json(result)
    assert payload["schema_version"] == "dicehub.cli/v1"
    assert payload["ok"] is True
    assert payload["data"]["page"] == {"offset": 2, "count": 1, "cursor": "next"}
    assert payload["data"]["templates"][0]["template_id"] == "12"
    assert "sentinel-api-key" not in result.stdout


def test_get_by_id_and_route_use_exact_values() -> None:
    env = {
        "DICEHUB_API_KEY": "sentinel-api-key",
        "DICEHUB_URL": "https://dicehub.test",
    }

    by_id = runner.invoke(cli_module.app, ["template", "get", "12"], env=env)
    by_route = runner.invoke(
        cli_module.app,
        ["template", "get-by-route", "/templates/openfoam_snappyhexmesh"],
        env=env,
    )

    assert by_id.exit_code == 0
    assert by_route.exit_code == 0
    assert _FakeTemplates.calls == [
        ("get", {"template_id": "12"}),
        ("get_by_route", {"route": "/templates/openfoam_snappyhexmesh"}),
    ]
    assert _json(by_id)["data"]["template"]["slug"] == "openfoam_snappyhexmesh"
    assert _json(by_route)["data"]["template"]["route"].startswith("/templates/")


def test_text_output_escapes_untrusted_control_characters() -> None:
    _FakeTemplates.result = _template(name="Hex\nmesher\tunsafe")

    result = runner.invoke(
        cli_module.app,
        ["template", "get", "12", "--output", "text"],
        env={
            "DICEHUB_API_KEY": "sentinel-api-key",
            "DICEHUB_URL": "https://dicehub.test",
        },
    )

    assert result.exit_code == 0
    assert result.stdout.count("\n") == 1
    assert "Hex\\nmesher\\tunsafe" in result.stdout


def test_operational_error_uses_stable_json_envelope() -> None:
    _FakeTemplates.error = APIError("dicehub rejected the operation.")

    result = runner.invoke(
        cli_module.app,
        ["template", "list"],
        env={
            "DICEHUB_API_KEY": "sentinel-api-key",
            "DICEHUB_URL": "https://dicehub.test",
        },
    )

    assert result.exit_code == 4
    payload = _json(result)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "API_ERROR"
    assert payload["error"]["retryable"] is False
