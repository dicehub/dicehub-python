from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any, TypeVar

import typer
from pydantic import BaseModel

from dicehub.cli._runtime import fail, run_with_client
from dicehub.cli.commands._membership_selectors import (
    MemberAddSelectors,
    ResolvedMemberAdd,
    member_add_data,
    resolve_member_add,
    validated_member_add_selectors,
)
from dicehub.cli.output import CLI_SCHEMA_VERSION, OutputFormat, terminal_safe, write_json
from dicehub.client import Client
from dicehub.errors import ConfigurationError
from dicehub.projects.models import MembershipVisibility

_Result = TypeVar("_Result")

members_app = typer.Typer(
    name="members",
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode=None,
)

_OUTPUT_OPTION = typer.Option("--output", case_sensitive=False, help="Output format.")


def _run(action: Callable[[Client], _Result], output: OutputFormat) -> _Result:
    return run_with_client(action, output, client_type=Client)


def _model_data(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json")


def _write_success(data: dict[str, Any]) -> None:
    write_json(
        {
            "schema_version": CLI_SCHEMA_VERSION,
            "ok": True,
            "data": data,
            "error": None,
        }
    )


def _require_confirmation(action: str, yes: bool, output: OutputFormat) -> None:
    if not yes:
        fail(ConfigurationError(f"Project member {action} requires --yes."), output)


def _resolve_and_add_project_member(
    client: Client,
    selectors: MemberAddSelectors,
    visibility: MembershipVisibility,
) -> ResolvedMemberAdd:
    resolved = resolve_member_add(
        client=client,
        selectors=selectors,
        resolve_namespace=lambda current, route: _project_by_route(current, route),
        resolve_role=lambda current, project_id, name: _project_role_by_name(
            current,
            project_id,
            name,
        ),
    )
    client.projects.add_member(
        project_id=resolved.namespace_id,
        member_id=resolved.member_id,
        role_id=resolved.role_id,
        visibility=visibility,
    )
    return resolved


def _project_by_route(client: Client, route: str) -> tuple[str, str]:
    project = client.projects.get_by_route(route=route)
    return project.project_id, project.route


def _project_role_by_name(client: Client, project_id: str, name: str) -> tuple[str, str]:
    role = client.projects.get_role_by_name(project_id=project_id, name=name)
    if role.name is None:
        raise ConfigurationError("The resolved project role has no name.")
    return role.role_id, role.name


@members_app.command("list-users")
def list_project_user_members(
    project_id: Annotated[str, typer.Argument(help="Exact project ID.")],
    include_inherited: Annotated[
        bool,
        typer.Option(
            "--include-inherited/--direct-only",
            help="Include inherited memberships.",
        ),
    ] = True,
    search_filter: Annotated[
        str | None,
        typer.Option("--search", "--search-filter", help="User search filter."),
    ] = None,
    offset: Annotated[int, typer.Option("--offset", min=0, help="Result offset.")] = 0,
    limit: Annotated[int, typer.Option("--limit", min=1, max=50, help="Page size.")] = 20,
    cursor: Annotated[str | None, typer.Option("--cursor", help="Pagination cursor.")] = None,
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """List user memberships visible in one project."""

    page = _run(
        lambda client: client.projects.list_user_members(
            project_id=project_id,
            include_inherited=include_inherited,
            search_filter=search_filter,
            offset=offset,
            limit=limit,
            cursor=cursor,
        ),
        output,
    )
    if output is OutputFormat.JSON:
        _write_success(
            {
                "memberships": [_model_data(item) for item in page.memberships],
                "page": {"offset": page.offset, "count": page.count, "cursor": page.cursor},
            }
        )
    else:
        for item in page.memberships:
            typer.echo(
                "\t".join(
                    terminal_safe(str(value))
                    for value in (
                        item.member_id,
                        item.user.username,
                        item.role_id,
                        item.visibility.value,
                        item.inherited,
                    )
                )
            )


@members_app.command("list-teams")
def list_project_team_members(
    project_id: Annotated[str, typer.Argument(help="Exact project ID.")],
    include_inherited: Annotated[
        bool,
        typer.Option(
            "--include-inherited/--direct-only",
            help="Include inherited memberships.",
        ),
    ] = True,
    deduplicate: Annotated[
        bool,
        typer.Option("--deduplicate", help="Return one effective membership per team."),
    ] = False,
    search_filter: Annotated[
        str | None,
        typer.Option("--search", "--search-filter", help="Team search filter."),
    ] = None,
    offset: Annotated[int, typer.Option("--offset", min=0, help="Result offset.")] = 0,
    limit: Annotated[int, typer.Option("--limit", min=1, max=50, help="Page size.")] = 20,
    cursor: Annotated[str | None, typer.Option("--cursor", help="Pagination cursor.")] = None,
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """List team memberships visible in one project."""

    page = _run(
        lambda client: client.projects.list_team_members(
            project_id=project_id,
            include_inherited=include_inherited,
            deduplicate=deduplicate,
            search_filter=search_filter,
            offset=offset,
            limit=limit,
            cursor=cursor,
        ),
        output,
    )
    if output is OutputFormat.JSON:
        _write_success(
            {
                "memberships": [_model_data(item) for item in page.memberships],
                "page": {"offset": page.offset, "count": page.count, "cursor": page.cursor},
            }
        )
    else:
        for item in page.memberships:
            typer.echo(
                "\t".join(
                    terminal_safe(str(value))
                    for value in (
                        item.member_id,
                        item.team.route,
                        item.role_id,
                        item.visibility.value,
                        item.inherited,
                    )
                )
            )


@members_app.command("add")
def add_project_member(
    project_id: Annotated[str | None, typer.Argument(help="Exact project ID.")] = None,
    member_id: Annotated[
        str | None,
        typer.Argument(help="Exact user or team namespace ID."),
    ] = None,
    project_route: Annotated[
        str | None,
        typer.Option("--project-route", help="Exact canonical project route."),
    ] = None,
    username: Annotated[
        str | None,
        typer.Option("--username", help="Exact eligible username."),
    ] = None,
    team_route: Annotated[
        str | None,
        typer.Option("--team-route", help="Exact canonical team route."),
    ] = None,
    role_id: Annotated[
        str | None,
        typer.Option("--role-id", help="Exact role ID."),
    ] = None,
    role_name: Annotated[
        str | None,
        typer.Option("--role", "--role-name", help="Exact role name."),
    ] = None,
    visibility: Annotated[
        MembershipVisibility,
        typer.Option("--visibility", case_sensitive=False, help="Membership visibility."),
    ] = MembershipVisibility.PRIVATE,
    yes: Annotated[bool, typer.Option("--yes", help="Confirm membership creation.")] = False,
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """Add one user or team to a project."""

    try:
        selectors = validated_member_add_selectors(
            namespace_label="Project",
            namespace_id=project_id,
            namespace_route=project_route,
            member_id=member_id,
            username=username,
            team_route=team_route,
            role_id=role_id,
            role_name=role_name,
        )
    except ConfigurationError as error:
        fail(error, output)
    _require_confirmation("creation", yes, output)
    resolved = _run(
        lambda client: _resolve_and_add_project_member(client, selectors, visibility),
        output,
    )
    if output is OutputFormat.JSON:
        _write_success(member_add_data("project_id", resolved))
    else:
        typer.echo(
            f"Added member {terminal_safe(resolved.member_id)} to project "
            f"{terminal_safe(resolved.namespace_id)}."
        )


@members_app.command("update")
def update_project_member(
    project_id: Annotated[str, typer.Argument(help="Exact project ID.")],
    member_id: Annotated[str, typer.Argument(help="Exact user or team namespace ID.")],
    role_id: Annotated[str | None, typer.Option("--role-id", help="New role ID.")] = None,
    visibility: Annotated[
        MembershipVisibility | None,
        typer.Option("--visibility", case_sensitive=False, help="New membership visibility."),
    ] = None,
    yes: Annotated[bool, typer.Option("--yes", help="Confirm membership update.")] = False,
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """Update one direct project membership."""

    _require_confirmation("update", yes, output)
    _run(
        lambda client: client.projects.update_member(
            project_id=project_id,
            member_id=member_id,
            role_id=role_id,
            visibility=visibility,
        ),
        output,
    )
    if output is OutputFormat.JSON:
        _write_success({"project_id": project_id, "member_id": member_id})
    else:
        typer.echo(
            f"Updated member {terminal_safe(member_id)} in project {terminal_safe(project_id)}."
        )


@members_app.command("remove")
def remove_project_member(
    project_id: Annotated[str, typer.Argument(help="Exact project ID.")],
    member_id: Annotated[str, typer.Argument(help="Exact user or team namespace ID.")],
    yes: Annotated[bool, typer.Option("--yes", help="Confirm membership removal.")] = False,
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """Remove one direct user or team membership."""

    _require_confirmation("removal", yes, output)
    _run(
        lambda client: client.projects.remove_member(
            project_id=project_id,
            member_id=member_id,
        ),
        output,
    )
    if output is OutputFormat.JSON:
        _write_success({"project_id": project_id, "member_id": member_id})
    else:
        typer.echo(
            f"Removed member {terminal_safe(member_id)} from project {terminal_safe(project_id)}."
        )
