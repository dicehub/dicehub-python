from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any, NoReturn, TypeVar

import typer
from pydantic import BaseModel

from dicehub.apps.models import AppOrderField
from dicehub.cli._runtime import fail, run_with_client
from dicehub.cli.commands.app_members import members_app
from dicehub.cli.output import CLI_SCHEMA_VERSION, OutputFormat, terminal_safe, write_json
from dicehub.client import Client
from dicehub.errors import ConfigurationError, DiceHubError
from dicehub.projects.models import SortOrder

_Result = TypeVar("_Result")

app_app = typer.Typer(
    name="app",
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode=None,
)
app_app.add_typer(members_app, name="members")

_OUTPUT_OPTION = typer.Option("--output", case_sensitive=False, help="Output format.")


def _run(action: Callable[[Client], _Result], output: OutputFormat) -> _Result:
    return run_with_client(action, output, client_type=Client)


def _fail(error: DiceHubError, output: OutputFormat) -> NoReturn:
    fail(error, output)


def _app_data(app: BaseModel) -> dict[str, Any]:
    return app.model_dump(mode="json")


def _write_success(data: dict[str, Any]) -> None:
    write_json(
        {
            "schema_version": CLI_SCHEMA_VERSION,
            "ok": True,
            "data": data,
            "error": None,
        }
    )


def _write_app_text(app: BaseModel) -> None:
    values = app.model_dump(mode="json")
    typer.echo(
        "\t".join(
            terminal_safe(str(values[field] if values[field] is not None else ""))
            for field in ("app_id", "route", "name", "visibility")
        )
    )


@app_app.command("create")
def create_app(
    project_id: Annotated[str, typer.Argument(help="Exact parent project ID.")],
    template_id: Annotated[
        str,
        typer.Option("--template-id", help="Exact source template ID."),
    ],
    name: Annotated[str, typer.Option("--name", help="App name.")],
    description: Annotated[
        str | None,
        typer.Option("--description", help="App description."),
    ] = None,
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """Create an app using an API key."""

    app = _run(
        lambda client: client.apps.create(
            project_id=project_id,
            template_id=template_id,
            name=name,
            description=description,
        ),
        output,
    )
    if output is OutputFormat.JSON:
        _write_success({"app": _app_data(app)})
    else:
        _write_app_text(app)


@app_app.command("update")
def update_app(
    app_id: Annotated[str, typer.Argument(help="Exact app ID.")],
    name: Annotated[str | None, typer.Option("--name", help="New app name.")] = None,
    description: Annotated[
        str | None,
        typer.Option("--description", help="New description; empty clears it."),
    ] = None,
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """Update app metadata using an API key."""

    _run(
        lambda client: client.apps.update(
            app_id=app_id,
            name=name,
            description=description,
        ),
        output,
    )
    if output is OutputFormat.JSON:
        _write_success({"app_id": app_id})
    else:
        typer.echo(f"Updated app {terminal_safe(app_id)}.")


@app_app.command("delete")
def delete_app(
    app_id: Annotated[str, typer.Argument(help="Exact app ID.")],
    yes: Annotated[
        bool,
        typer.Option(
            "--yes",
            help="Confirm recursive deletion of the app and all of its data.",
        ),
    ] = False,
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """Recursively delete an app using an API key."""

    if not yes:
        _fail(ConfigurationError("App deletion requires --yes."), output)
    _run(lambda client: client.apps.delete(app_id=app_id), output)
    if output is OutputFormat.JSON:
        _write_success({"app_id": app_id})
    else:
        typer.echo(f"Deleted app {terminal_safe(app_id)}.")


@app_app.command("list")
def list_apps(
    project_id: Annotated[str, typer.Argument(help="Exact parent project ID.")],
    search_filter: Annotated[
        str | None,
        typer.Option("--search", "--search-filter", help="App-name search filter."),
    ] = None,
    order_by: Annotated[
        AppOrderField,
        typer.Option("--order-by", case_sensitive=False, help="Sort field."),
    ] = AppOrderField.NAME,
    order: Annotated[
        SortOrder,
        typer.Option("--order", case_sensitive=False, help="Sort direction."),
    ] = SortOrder.ASC,
    offset: Annotated[int, typer.Option("--offset", min=0, help="Result offset.")] = 0,
    limit: Annotated[int, typer.Option("--limit", min=1, max=50, help="Page size.")] = 20,
    cursor: Annotated[str | None, typer.Option("--cursor", help="Pagination cursor.")] = None,
    is_published: Annotated[
        bool | None,
        typer.Option(
            "--published/--unpublished",
            help="Filter by publication state; omit for both.",
        ),
    ] = None,
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """List app metadata visible inside one project."""

    page = _run(
        lambda client: client.apps.list(
            project_id=project_id,
            search_filter=search_filter,
            order_by=order_by,
            order=order,
            offset=offset,
            limit=limit,
            cursor=cursor,
            is_published=is_published,
        ),
        output,
    )
    if output is OutputFormat.JSON:
        _write_success(
            {
                "apps": [_app_data(app) for app in page.apps],
                "page": {
                    "offset": page.offset,
                    "count": page.count,
                    "cursor": page.cursor,
                },
            }
        )
    else:
        for app in page.apps:
            _write_app_text(app)


@app_app.command("get")
def get_app(
    app_id: Annotated[str, typer.Argument(help="Exact app ID.")],
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """Get app metadata by immutable ID."""

    app = _run(lambda client: client.apps.get(app_id=app_id), output)
    if output is OutputFormat.JSON:
        _write_success({"app": _app_data(app)})
    else:
        _write_app_text(app)


@app_app.command("get-by-route")
def get_app_by_route(
    route: Annotated[str, typer.Argument(help="Exact app route.")],
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """Get app metadata by exact route."""

    app = _run(lambda client: client.apps.get_by_route(route=route), output)
    if output is OutputFormat.JSON:
        _write_success({"app": _app_data(app)})
    else:
        _write_app_text(app)


@app_app.command("roles")
def list_app_roles(
    app_id: Annotated[str, typer.Argument(help="Exact app ID.")],
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """List roles that can be assigned in one app."""

    roles = _run(lambda client: client.apps.list_roles(app_id=app_id), output)
    if output is OutputFormat.JSON:
        _write_success({"roles": [_app_data(role) for role in roles]})
    else:
        for role in roles:
            typer.echo(
                "\t".join(
                    terminal_safe(str(value if value is not None else ""))
                    for value in (role.role_id, role.name)
                )
            )
