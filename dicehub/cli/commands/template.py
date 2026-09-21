from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any, NoReturn, TypeVar

import typer
from pydantic import BaseModel

from dicehub.cli._runtime import fail, run_with_client
from dicehub.cli.output import CLI_SCHEMA_VERSION, OutputFormat, terminal_safe, write_json
from dicehub.client import Client
from dicehub.errors import DiceHubError
from dicehub.projects.models import SortOrder
from dicehub.templates.models import TemplateOrderField, TemplateType

_Result = TypeVar("_Result")

template_app = typer.Typer(
    name="template",
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode=None,
)

_OUTPUT_OPTION = typer.Option("--output", case_sensitive=False, help="Output format.")


def _fail(error: DiceHubError, output: OutputFormat) -> NoReturn:
    fail(error, output)


def _run(action: Callable[[Client], _Result], output: OutputFormat) -> _Result:
    return run_with_client(action, output, client_type=Client)


def _template_data(template: BaseModel) -> dict[str, Any]:
    return template.model_dump(mode="json")


def _write_success(data: dict[str, Any]) -> None:
    write_json(
        {
            "schema_version": CLI_SCHEMA_VERSION,
            "ok": True,
            "data": data,
            "error": None,
        }
    )


def _write_template_text(template: BaseModel) -> None:
    values = template.model_dump(mode="json")
    typer.echo(
        "\t".join(
            terminal_safe(str(values.get(field) or ""))
            for field in ("template_id", "route", "name", "client_type")
        )
    )


@template_app.command("list")
def list_templates(
    search_filter: Annotated[
        str | None,
        typer.Option("--search", "--search-filter", help="Template-name search filter."),
    ] = None,
    template_type: Annotated[
        TemplateType | None,
        typer.Option("--type", case_sensitive=False, help="Template type."),
    ] = TemplateType.APP_TEMPLATE,
    tags: Annotated[
        list[str] | None,
        typer.Option("--tag", help="Required tag; repeat for an AND filter."),
    ] = None,
    order_by: Annotated[
        TemplateOrderField,
        typer.Option("--order-by", case_sensitive=False, help="Sort field."),
    ] = TemplateOrderField.NAME,
    order: Annotated[
        SortOrder,
        typer.Option("--order", case_sensitive=False, help="Sort direction."),
    ] = SortOrder.ASC,
    offset: Annotated[int, typer.Option("--offset", min=0, help="Result offset.")] = 0,
    limit: Annotated[int, typer.Option("--limit", min=1, max=50, help="Page size.")] = 20,
    cursor: Annotated[str | None, typer.Option("--cursor", help="Pagination cursor.")] = None,
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """List template metadata from the server catalog."""

    page = _run(
        lambda client: client.templates.list(
            search_filter=search_filter,
            template_type=template_type,
            tags=tags,
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
                "templates": [_template_data(template) for template in page.templates],
                "page": {
                    "offset": page.offset,
                    "count": page.count,
                    "cursor": page.cursor,
                },
            }
        )
    else:
        for template in page.templates:
            _write_template_text(template)


@template_app.command("get")
def get_template(
    template_id: Annotated[str, typer.Argument(help="Exact template ID.")],
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """Get a template by its immutable ID."""

    template = _run(
        lambda client: client.templates.get(template_id=template_id),
        output,
    )
    if output is OutputFormat.JSON:
        _write_success({"template": _template_data(template)})
    else:
        _write_template_text(template)


@template_app.command("get-by-route")
def get_template_by_route(
    route: Annotated[str, typer.Argument(help="Exact template route.")],
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """Get a template by its exact route."""

    template = _run(
        lambda client: client.templates.get_by_route(route=route),
        output,
    )
    if output is OutputFormat.JSON:
        _write_success({"template": _template_data(template)})
    else:
        _write_template_text(template)
