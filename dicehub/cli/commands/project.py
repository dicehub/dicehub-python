from __future__ import annotations

import sys
from collections.abc import Callable
from typing import Annotated, Any, NoReturn, TypeVar

import typer
from pydantic import BaseModel

from dicehub.cli._runtime import fail, run_with_client
from dicehub.cli.commands.project_members import members_app
from dicehub.cli.output import (
    CLI_SCHEMA_VERSION,
    OutputFormat,
    terminal_safe,
    write_json,
)
from dicehub.client import Client
from dicehub.errors import ConfigurationError, DiceHubError
from dicehub.projects.models import ProjectOrderField, ProjectVisibility, SortOrder

_Result = TypeVar("_Result")

project_app = typer.Typer(
    name="project",
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode=None,
)
project_app.add_typer(members_app, name="members")

_OUTPUT_OPTION = typer.Option("--output", case_sensitive=False, help="Output format.")


def _fail(error: DiceHubError, output: OutputFormat) -> NoReturn:
    fail(error, output)


def _run(
    action: Callable[[Client], _Result],
    output: OutputFormat,
    *,
    requires_session: bool,
) -> _Result:
    return run_with_client(
        action,
        output,
        client_type=Client,
        session_required_message=(
            "This project operation requires DICEHUB_SESSION_COOKIE." if requires_session else None
        ),
    )


def _project_data(project: BaseModel) -> dict[str, Any]:
    return project.model_dump(mode="json")


def _write_success(data: dict[str, Any]) -> None:
    write_json(
        {
            "schema_version": CLI_SCHEMA_VERSION,
            "ok": True,
            "data": data,
            "error": None,
        }
    )


def _write_project_text(project: BaseModel) -> None:
    values = project.model_dump(mode="json")
    typer.echo(
        "\t".join(
            terminal_safe(str(values[field]))
            for field in ("project_id", "route", "name", "visibility")
        )
    )


def _stdin_is_interactive() -> bool:
    return sys.stdin.isatty() and sys.stderr.isatty()


def _confirm_project_deletion(project_id: str, output: OutputFormat) -> None:
    if not _stdin_is_interactive():
        _fail(ConfigurationError("Project deletion requires --yes."), output)
    typer.echo(
        f"Delete project {terminal_safe(project_id)} and all descendants? [y/N]: ",
        nl=False,
        err=True,
    )
    try:
        answer = sys.stdin.readline()
    except (KeyboardInterrupt, OSError):
        answer = ""
    if answer.strip().casefold() not in {"y", "yes"}:
        _fail(ConfigurationError("Project deletion was canceled."), output)


@project_app.command("list")
def list_projects(
    user_id: Annotated[
        str | None,
        typer.Option("--user-id", help="User membership filter ID."),
    ] = None,
    group_id: Annotated[str | None, typer.Option("--group-id", help="Parent group ID.")] = None,
    search_filter: Annotated[
        str | None,
        typer.Option("--search", "--search-filter", help="Project-name search filter."),
    ] = None,
    order_by: Annotated[
        ProjectOrderField,
        typer.Option("--order-by", case_sensitive=False, help="Sort field."),
    ] = ProjectOrderField.NAME,
    order: Annotated[
        SortOrder,
        typer.Option("--order", case_sensitive=False, help="Sort direction."),
    ] = SortOrder.ASC,
    offset: Annotated[int, typer.Option("--offset", min=0, help="Result offset.")] = 0,
    limit: Annotated[int, typer.Option("--limit", min=1, max=50, help="Page size.")] = 20,
    cursor: Annotated[str | None, typer.Option("--cursor", help="Pagination cursor.")] = None,
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """List projects visible to the current credential."""

    page = _run(
        lambda client: client.projects.list(
            user_id=user_id,
            group_id=group_id,
            search_filter=search_filter,
            order_by=order_by,
            order=order,
            offset=offset,
            limit=limit,
            cursor=cursor,
        ),
        output,
        requires_session=False,
    )
    if output is OutputFormat.JSON:
        _write_success(
            {
                "projects": [_project_data(project) for project in page.projects],
                "page": {
                    "offset": page.offset,
                    "count": page.count,
                    "cursor": page.cursor,
                },
            }
        )
    else:
        for project in page.projects:
            _write_project_text(project)


@project_app.command("get")
def get_project(
    project_id: Annotated[str, typer.Argument(help="Exact project ID.")],
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """Get a project by its immutable ID."""

    project = _run(
        lambda client: client.projects.get(project_id=project_id),
        output,
        requires_session=False,
    )
    if output is OutputFormat.JSON:
        _write_success({"project": _project_data(project)})
    else:
        _write_project_text(project)


@project_app.command("get-by-route")
def get_project_by_route(
    route: Annotated[str, typer.Argument(help="Exact project route.")],
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """Get a project by its exact route."""

    project = _run(
        lambda client: client.projects.get_by_route(route=route),
        output,
        requires_session=False,
    )
    if output is OutputFormat.JSON:
        _write_success({"project": _project_data(project)})
    else:
        _write_project_text(project)


@project_app.command("roles")
def list_project_roles(
    project_id: Annotated[str, typer.Argument(help="Exact project ID.")],
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """List roles that can be assigned in one project."""

    roles = _run(
        lambda client: client.projects.list_roles(project_id=project_id),
        output,
        requires_session=False,
    )
    if output is OutputFormat.JSON:
        _write_success({"roles": [_project_data(role) for role in roles]})
    else:
        for role in roles:
            typer.echo(
                "\t".join(
                    terminal_safe(str(value if value is not None else ""))
                    for value in (role.role_id, role.name)
                )
            )


@project_app.command("create")
def create_project(
    name: Annotated[str, typer.Option("--name", help="Project name.")],
    slug: Annotated[str, typer.Option("--slug", help="Project route slug.")],
    group_id: Annotated[
        str | None,
        typer.Option("--group-id", help="Exact parent group ID; omit for personal scope."),
    ] = None,
    description: Annotated[
        str | None,
        typer.Option("--description", help="Project description."),
    ] = None,
    visibility: Annotated[
        ProjectVisibility,
        typer.Option("--visibility", case_sensitive=False, help="Project visibility."),
    ] = ProjectVisibility.PRIVATE,
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """Create a project using an API key."""

    project = _run(
        lambda client: client.projects.create(
            name=name,
            slug=slug,
            group_id=group_id,
            description=description,
            visibility=visibility,
        ),
        output,
        requires_session=False,
    )
    if output is OutputFormat.JSON:
        _write_success({"project": _project_data(project)})
    else:
        _write_project_text(project)


@project_app.command("update")
def update_project(
    project_id: Annotated[str, typer.Argument(help="Exact project ID.")],
    name: Annotated[str | None, typer.Option("--name", help="New project name.")] = None,
    slug: Annotated[str | None, typer.Option("--slug", help="New route slug.")] = None,
    description: Annotated[
        str | None,
        typer.Option("--description", help="New description; empty clears it."),
    ] = None,
    visibility: Annotated[
        ProjectVisibility | None,
        typer.Option("--visibility", case_sensitive=False, help="New visibility."),
    ] = None,
    yes: Annotated[
        bool,
        typer.Option("--yes", help="Confirm a route or visibility change."),
    ] = False,
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """Update selected project fields using an API key."""

    if (slug is not None or visibility is not None) and not yes:
        _fail(
            ConfigurationError("Project slug or visibility update requires --yes."),
            output,
        )
    _run(
        lambda client: client.projects.update(
            project_id=project_id,
            name=name,
            slug=slug,
            description=description,
            visibility=visibility,
        ),
        output,
        requires_session=False,
    )
    if output is OutputFormat.JSON:
        _write_success({"project_id": project_id})
    else:
        typer.echo(f"Updated project {terminal_safe(project_id)}.")


@project_app.command("move")
def move_project(
    project_id: Annotated[str, typer.Argument(help="Exact project ID.")],
    to_group_id: Annotated[str, typer.Argument(help="Exact destination group ID.")],
    yes: Annotated[
        bool,
        typer.Option(
            "--yes",
            help="Confirm moving the project subtree and changing inherited access.",
        ),
    ] = False,
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """Move a project to a group using session authentication."""

    if not yes:
        _fail(ConfigurationError("Project move requires --yes."), output)
    _run(
        lambda client: client.projects.move(
            project_id=project_id,
            to_group_id=to_group_id,
        ),
        output,
        requires_session=True,
    )
    if output is OutputFormat.JSON:
        _write_success({"project_id": project_id, "to_group_id": to_group_id})
    else:
        typer.echo(
            f"Moved project {terminal_safe(project_id)} to group {terminal_safe(to_group_id)}."
        )


@project_app.command("delete")
def delete_project(
    project_id: Annotated[str, typer.Argument(help="Exact project ID.")],
    yes: Annotated[
        bool,
        typer.Option("--yes", help="Skip the interactive recursive-deletion confirmation."),
    ] = False,
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """Recursively delete a project using an API key."""

    if not yes:
        _confirm_project_deletion(project_id, output)
    _run(
        lambda client: client.projects.delete(project_id=project_id),
        output,
        requires_session=False,
    )
    if output is OutputFormat.JSON:
        _write_success({"project_id": project_id})
    else:
        typer.echo(f"Deleted project {terminal_safe(project_id)}.")
