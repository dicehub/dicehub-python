from __future__ import annotations

import json
from types import TracebackType
from typing import Any, ClassVar, cast

import pytest
from typer.testing import CliRunner

from dicehub import Project, ProjectDetail, ProjectPage
from dicehub import cli as cli_module
from dicehub.cli.commands import project as project_commands
from dicehub.projects import ProjectOrderField, ProjectVisibility, SortOrder

runner = CliRunner()


def _exception_chain_text(error: BaseException | None) -> str:
    values: list[str] = []
    seen: set[int] = set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        values.append(repr(error))
        error = error.__cause__ or error.__context__
    return " ".join(values)


def _project(*, name: str = "Demo") -> Project:
    return Project(
        project_id="41",
        group_id="7",
        name=name,
        display_route="group / demo",
        route="/group/demo",
        visibility=ProjectVisibility.PRIVATE,
    )


def _project_detail(*, name: str = "Demo") -> ProjectDetail:
    return ProjectDetail(
        project_id="41",
        group_id="7",
        name=name,
        display_route="group / demo",
        route="/group/demo",
        visibility=ProjectVisibility.PRIVATE,
        description="Description",
        avatar_url=None,
    )


class _FakeProjects:
    calls: ClassVar[list[tuple[str, dict[str, object]]]] = []
    error: ClassVar[Exception | None] = None
    detail: ClassVar[ProjectDetail] = _project_detail()

    def _record(self, name: str, values: dict[str, object]) -> None:
        self.calls.append((name, values))
        if self.error is not None:
            raise self.error

    def list(
        self,
        *,
        user_id: str | None = None,
        group_id: str | None = None,
        search_filter: str | None = None,
        order_by: ProjectOrderField = ProjectOrderField.NAME,
        order: SortOrder = SortOrder.ASC,
        offset: int = 0,
        limit: int = 20,
        cursor: str | None = None,
    ) -> ProjectPage:
        self._record(
            "list",
            {
                "user_id": user_id,
                "group_id": group_id,
                "search_filter": search_filter,
                "order_by": order_by,
                "order": order,
                "offset": offset,
                "limit": limit,
                "cursor": cursor,
            },
        )
        return ProjectPage(projects=(_project(),), offset=offset, count=1, cursor="next")

    def get(self, *, project_id: str) -> ProjectDetail:
        self._record("get", {"project_id": project_id})
        return self.detail

    def get_by_route(self, *, route: str) -> ProjectDetail:
        self._record("get_by_route", {"route": route})
        return self.detail

    def create(
        self,
        *,
        name: str,
        slug: str,
        group_id: str | None = None,
        description: str | None = None,
        visibility: ProjectVisibility = ProjectVisibility.PRIVATE,
    ) -> Project:
        self._record(
            "create",
            {
                "name": name,
                "slug": slug,
                "group_id": group_id,
                "description": description,
                "visibility": visibility,
            },
        )
        return _project(name=name)

    def update(
        self,
        *,
        project_id: str,
        name: str | None = None,
        slug: str | None = None,
        description: str | None = None,
        visibility: ProjectVisibility | None = None,
    ) -> None:
        self._record(
            "update",
            {
                "project_id": project_id,
                "name": name,
                "slug": slug,
                "description": description,
                "visibility": visibility,
            },
        )

    def move(self, *, project_id: str, to_group_id: str) -> None:
        self._record("move", {"project_id": project_id, "to_group_id": to_group_id})

    def delete(self, *, project_id: str) -> None:
        self._record("delete", {"project_id": project_id})


class _FakeClient:
    projects = _FakeProjects()
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
    _FakeProjects.calls = []
    _FakeProjects.error = None
    _FakeProjects.detail = _project_detail()
    _FakeClient.constructions = []
    monkeypatch.delenv("DICEHUB_API_KEY", raising=False)
    monkeypatch.delenv("DICEHUB_SESSION_COOKIE", raising=False)
    monkeypatch.delenv("DICEHUB_URL", raising=False)
    monkeypatch.setattr(project_commands, "Client", _FakeClient)


def _json(result: Any) -> dict[str, Any]:
    assert result.stderr == ""
    assert result.stdout.count("\n") == 1
    payload = json.loads(result.stdout)
    assert isinstance(payload, dict)
    return cast(dict[str, Any], payload)


def test_list_uses_api_key_and_emits_structured_page() -> None:
    result = runner.invoke(
        cli_module.app,
        [
            "project",
            "list",
            "--user-id",
            "9",
            "--group-id",
            "7",
            "--search-filter",
            "demo",
            "--order-by",
            "UPDATED_AT",
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
    assert _FakeProjects.calls == [
        (
            "list",
            {
                "user_id": "9",
                "group_id": "7",
                "search_filter": "demo",
                "order_by": ProjectOrderField.UPDATED_AT,
                "order": SortOrder.DESC,
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
            "projects": [
                {
                    "project_id": "41",
                    "group_id": "7",
                    "name": "Demo",
                    "display_route": "group / demo",
                    "route": "/group/demo",
                    "visibility": "PRIVATE",
                }
            ],
            "page": {"offset": 2, "count": 1, "cursor": "next"},
        },
        "error": None,
    }
    assert "sentinel-api-key" not in result.stdout + result.stderr


def test_read_uses_api_key() -> None:
    result = runner.invoke(
        cli_module.app,
        ["project", "get", "41"],
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
    assert _FakeProjects.calls == [("get", {"project_id": "41"})]
    payload = _json(result)
    assert payload["data"]["project"]["description"] == "Description"
    assert "sentinel-api-key" not in result.stdout + result.stderr


def test_get_by_route_passes_exact_route() -> None:
    result = runner.invoke(
        cli_module.app,
        ["project", "get-by-route", "/group/demo"],
        env={
            "DICEHUB_API_KEY": "sentinel-api-key",
            "DICEHUB_URL": "https://dicehub.test",
        },
    )

    assert result.exit_code == 0
    assert _FakeProjects.calls == [("get_by_route", {"route": "/group/demo"})]


def test_api_key_read_uses_hosted_origin_by_default_and_redacts_key() -> None:
    result = runner.invoke(
        cli_module.app,
        ["project", "get", "41"],
        env={"DICEHUB_API_KEY": "sentinel-api-key"},
    )

    assert result.exit_code == 0
    assert _FakeClient.constructions == [
        {
            "base_url": "https://dicehub.com",
            "api_key": "sentinel-api-key",
            "session_cookie": None,
        }
    ]
    assert _FakeProjects.calls == [("get", {"project_id": "41"})]
    assert "sentinel-api-key" not in result.stdout + result.stderr + repr(result.exception)


def test_create_passes_all_options_with_api_key() -> None:
    result = runner.invoke(
        cli_module.app,
        [
            "project",
            "create",
            "--name",
            "New project",
            "--slug",
            "new-project",
            "--group-id",
            "7",
            "--description",
            "A project",
            "--visibility",
            "public",
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
    assert _FakeProjects.calls == [
        (
            "create",
            {
                "name": "New project",
                "slug": "new-project",
                "group_id": "7",
                "description": "A project",
                "visibility": ProjectVisibility.PUBLIC,
            },
        )
    ]
    assert _json(result)["data"]["project"]["name"] == "New project"
    assert "sentinel-api-key" not in result.stdout + result.stderr


@pytest.mark.parametrize(
    ("scope_arguments", "expected_group_id"),
    [([], None), (["--group-id", "7"], "7")],
)
def test_create_uses_api_key_without_exposing_it(
    scope_arguments: list[str],
    expected_group_id: str | None,
) -> None:
    result = runner.invoke(
        cli_module.app,
        [
            "project",
            "create",
            "--name",
            "Agent project",
            "--slug",
            "agent-project",
            *scope_arguments,
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
    assert _FakeProjects.calls == [
        (
            "create",
            {
                "name": "Agent project",
                "slug": "agent-project",
                "group_id": expected_group_id,
                "description": None,
                "visibility": ProjectVisibility.PRIVATE,
            },
        )
    ]
    assert _json(result)["data"]["project"]["name"] == "Agent project"
    assert "sentinel-api-key" not in result.stdout + result.stderr
