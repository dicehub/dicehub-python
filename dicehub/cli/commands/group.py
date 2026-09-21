from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any, TypeVar

import typer
from pydantic import BaseModel

from dicehub.cli._runtime import fail, run_with_client
from dicehub.cli.commands.group_avatar import avatar_app
from dicehub.cli.commands.group_members import members_app
from dicehub.cli.output import CLI_SCHEMA_VERSION, OutputFormat, terminal_safe, write_json
from dicehub.client import Client
from dicehub.errors import ConfigurationError
from dicehub.groups.models import GroupOrderField, GroupVisibility
from dicehub.projects.models import SortOrder

_Result = TypeVar("_Result")

group_app = typer.Typer(
    name="group",
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode=None,
)
group_app.add_typer(avatar_app, name="avatar")
group_app.add_typer(members_app, name="members")

_OUTPUT_OPTION = typer.Option("--output", case_sensitive=False, help="Output format.")


def _run(
    action: Callable[[Client], _Result],
    output: OutputFormat,
    *,
    requires_session: bool = False,
) -> _Result:
    return run_with_client(
        action,
        output,
        client_type=Client,
        session_required_message=(
            "This group operation requires DICEHUB_SESSION_COOKIE." if requires_session else None
        ),
    )


def _group_data(group: BaseModel) -> dict[str, Any]:
    return group.model_dump(mode="json")


def _write_success(data: dict[str, Any]) -> None:
    write_json(
        {
            "schema_version": CLI_SCHEMA_VERSION,
            "ok": True,
            "data": data,
            "error": None,
        }
    )


def _write_group_text(group: BaseModel) -> None:
    values = group.model_dump(mode="json")
    typer.echo(
        "\t".join(
            terminal_safe(str(values[field]))
            for field in ("group_id", "route", "name", "visibility")
        )
    )


@group_app.command("create")
def create_group(
    name: Annotated[str, typer.Option("--name", help="Group name.")],
    slug: Annotated[str, typer.Option("--slug", help="Group route slug.")],
    parent_id: Annotated[
        str | None,
        typer.Option("--parent-id", help="Parent group ID for subgroup creation."),
    ] = None,
    description: Annotated[
        str | None,
        typer.Option("--description", help="Group description."),
    ] = None,
    visibility: Annotated[
        GroupVisibility,
        typer.Option("--visibility", case_sensitive=False, help="Group visibility."),
    ] = GroupVisibility.PRIVATE,
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """Create a top-level group or subgroup."""

    group = _run(
        lambda client: client.groups.create(
            name=name,
            slug=slug,
            parent_id=parent_id,
            description=description,
            visibility=visibility,
        ),
        output,
        requires_session=parent_id is None,
    )
    if output is OutputFormat.JSON:
        _write_success({"group": _group_data(group)})
    else:
        _write_group_text(group)


@group_app.command("list")
def list_groups(
    user_id: Annotated[
        str | None,
        typer.Option("--user-id", help="User membership filter ID."),
    ] = None,
    parent_id: Annotated[
        str | None,
        typer.Option("--parent-id", help="Direct parent group ID."),
    ] = None,
    search_filter: Annotated[
        str | None,
        typer.Option("--search", "--search-filter", help="Group-name search filter."),
    ] = None,
    order_by: Annotated[
        GroupOrderField,
        typer.Option("--order-by", case_sensitive=False, help="Sort field."),
    ] = GroupOrderField.NAME,
    order: Annotated[
        SortOrder,
        typer.Option("--order", case_sensitive=False, help="Sort direction."),
    ] = SortOrder.ASC,
    offset: Annotated[int, typer.Option("--offset", min=0, help="Result offset.")] = 0,
    limit: Annotated[int, typer.Option("--limit", min=1, max=50, help="Page size.")] = 20,
    cursor: Annotated[str | None, typer.Option("--cursor", help="Pagination cursor.")] = None,
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """List groups visible to the current API key."""

    page = _run(
        lambda client: client.groups.list(
            user_id=user_id,
            parent_id=parent_id,
            search_filter=search_filter,
            order_by=order_by,
            order=order,
            offset=offset,
            limit=limit,
            cursor=cursor,
        ),
        output,
    )
    if output is OutputFormat.JSON:
        _write_success(
            {
                "groups": [_group_data(group) for group in page.groups],
                "page": {
                    "offset": page.offset,
                    "count": page.count,
                    "cursor": page.cursor,
                },
            }
        )
    else:
        for group in page.groups:
            _write_group_text(group)


@group_app.command("get")
def get_group(
    group_id: Annotated[str, typer.Argument(help="Exact group ID.")],
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """Get a group by its immutable ID."""

    group = _run(lambda client: client.groups.get(group_id=group_id), output)
    if output is OutputFormat.JSON:
        _write_success({"group": _group_data(group)})
    else:
        _write_group_text(group)


@group_app.command("get-by-route")
def get_group_by_route(
    route: Annotated[str, typer.Argument(help="Exact group route.")],
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """Get a group by its exact route."""

    group = _run(lambda client: client.groups.get_by_route(route=route), output)
    if output is OutputFormat.JSON:
        _write_success({"group": _group_data(group)})
    else:
        _write_group_text(group)


@group_app.command("update")
def update_group(
    group_id: Annotated[str, typer.Argument(help="Exact group ID.")],
    name: Annotated[str | None, typer.Option("--name", help="New group name.")] = None,
    slug: Annotated[str | None, typer.Option("--slug", help="New route slug.")] = None,
    description: Annotated[
        str | None,
        typer.Option("--description", help="New description; empty clears it."),
    ] = None,
    visibility: Annotated[
        GroupVisibility | None,
        typer.Option("--visibility", case_sensitive=False, help="New visibility."),
    ] = None,
    yes: Annotated[
        bool,
        typer.Option("--yes", help="Confirm a route or visibility change."),
    ] = False,
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """Update selected group fields using an API key."""

    if (slug is not None or visibility is not None) and not yes:
        fail(
            ConfigurationError("Group slug or visibility update requires --yes."),
            output,
        )
    _run(
        lambda client: client.groups.update(
            group_id=group_id,
            name=name,
            slug=slug,
            description=description,
            visibility=visibility,
        ),
        output,
    )
    if output is OutputFormat.JSON:
        _write_success({"group_id": group_id})
    else:
        typer.echo(f"Updated group {terminal_safe(group_id)}.")


@group_app.command("delete")
def delete_group(
    group_id: Annotated[str, typer.Argument(help="Exact group ID.")],
    yes: Annotated[
        bool,
        typer.Option("--yes", help="Confirm recursive group deletion."),
    ] = False,
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """Recursively delete one group and its descendants."""

    if not yes:
        fail(ConfigurationError("Group deletion requires --yes."), output)
    _run(lambda client: client.groups.delete(group_id=group_id), output)
    if output is OutputFormat.JSON:
        _write_success({"group_id": group_id})
    else:
        typer.echo(f"Deleted group {terminal_safe(group_id)}.")


@group_app.command("move")
def move_group(
    group_id: Annotated[str, typer.Argument(help="Exact subgroup ID.")],
    to_group_id: Annotated[str, typer.Argument(help="Exact target parent group ID.")],
    yes: Annotated[
        bool,
        typer.Option("--yes", help="Confirm subgroup movement."),
    ] = False,
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """Move one subgroup using a session cookie."""

    if not yes:
        fail(ConfigurationError("Group move requires --yes."), output)
    _run(
        lambda client: client.groups.move(group_id=group_id, to_group_id=to_group_id),
        output,
        requires_session=True,
    )
    if output is OutputFormat.JSON:
        _write_success({"group_id": group_id, "to_group_id": to_group_id})
    else:
        typer.echo(f"Moved group {terminal_safe(group_id)} to {terminal_safe(to_group_id)}.")


@group_app.command("roles")
def list_group_roles(
    group_id: Annotated[str, typer.Argument(help="Exact group ID.")],
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """List roles that can be assigned in one group."""

    roles = _run(lambda client: client.groups.list_roles(group_id=group_id), output)
    if output is OutputFormat.JSON:
        _write_success({"roles": [_group_data(role) for role in roles]})
    else:
        for role in roles:
            typer.echo(
                "\t".join(terminal_safe(str(value)) for value in (role.role_id, role.name or ""))
            )
