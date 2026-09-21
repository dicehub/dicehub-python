from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any, TypeVar

import typer
from pydantic import BaseModel

from dicehub.cli._runtime import fail, run_with_client
from dicehub.cli.output import CLI_SCHEMA_VERSION, OutputFormat, terminal_safe, write_json
from dicehub.client import Client
from dicehub.errors import ConfigurationError
from dicehub.resources.models import Resource, ResourceType

_Result = TypeVar("_Result")

resource_app = typer.Typer(
    name="resource",
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode=None,
)

_OUTPUT_OPTION = typer.Option("--output", case_sensitive=False, help="Output format.")


def _run(action: Callable[[Client], _Result], output: OutputFormat) -> _Result:
    return run_with_client(action, output, client_type=Client, allow_session=True)


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


def _write_resource_text(resource: Resource) -> None:
    values = _model_data(resource)
    typer.echo(
        "\t".join(
            terminal_safe(str(values[field] if values[field] is not None else ""))
            for field in ("resource_id", "namespace_id", "key", "resource_type")
        )
    )


def _write_receipt_text(receipt: BaseModel, byte_field: str) -> None:
    values = _model_data(receipt)
    typer.echo(
        "\t".join(
            terminal_safe(str(values[field] if values[field] is not None else ""))
            for field in ("path", byte_field, "sha256", "server_verified")
        )
    )


@resource_app.command("list")
def list_resources(
    namespace_id: Annotated[str, typer.Argument(help="Exact namespace ID.")],
    path: Annotated[
        str,
        typer.Option("--path", help="Relative path inside the data root."),
    ] = "",
    resource_type: Annotated[
        ResourceType | None,
        typer.Option("--type", case_sensitive=False, help="Resource type filter."),
    ] = None,
    recursive: Annotated[
        bool,
        typer.Option("--recursive", help="Include descendants below the path."),
    ] = False,
    offset: Annotated[int, typer.Option("--offset", min=0, help="Result offset.")] = 0,
    limit: Annotated[int, typer.Option("--limit", min=1, max=50, help="Page size.")] = 20,
    cursor: Annotated[str | None, typer.Option("--cursor", help="Pagination cursor.")] = None,
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """List resource metadata in one namespace."""

    page = _run(
        lambda client: client.resources.list(
            namespace_id=namespace_id,
            path=path,
            resource_type=resource_type,
            recursive=recursive,
            offset=offset,
            limit=limit,
            cursor=cursor,
        ),
        output,
    )
    if output is OutputFormat.JSON:
        _write_success(
            {
                "resources": [_model_data(resource) for resource in page.resources],
                "page": {
                    "offset": page.offset,
                    "count": page.count,
                    "cursor": page.cursor,
                },
            }
        )
    else:
        for resource in page.resources:
            _write_resource_text(resource)


@resource_app.command("get")
def get_resource(
    resource_id: Annotated[str, typer.Argument(help="Exact immutable resource UUID.")],
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """Get resource metadata by immutable ID."""

    resource = _run(lambda client: client.resources.get(resource_id=resource_id), output)
    if output is OutputFormat.JSON:
        _write_success({"resource": _model_data(resource)})
    else:
        _write_resource_text(resource)


@resource_app.command("upload")
def upload_resource(
    namespace_id: Annotated[str, typer.Argument(help="Exact namespace ID.")],
    path: Annotated[str, typer.Argument(help="Relative path inside the data root.")],
    source_path: Annotated[Path, typer.Argument(help="Local binary source file.")],
    max_bytes: Annotated[
        int | None,
        typer.Option("--max-bytes", min=1, help="Maximum upload size in bytes."),
    ] = None,
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """Upload one binary resource from a local file."""

    def action(client: Client) -> BaseModel:
        if max_bytes is None:
            return client.storage.upload_file(
                namespace_id=namespace_id,
                path=path,
                source_path=source_path,
            )
        return client.storage.upload_file(
            namespace_id=namespace_id,
            path=path,
            source_path=source_path,
            max_bytes=max_bytes,
        )

    receipt = _run(action, output)
    if output is OutputFormat.JSON:
        _write_success({"upload": _model_data(receipt)})
    else:
        _write_receipt_text(receipt, "bytes_sent")


@resource_app.command("download")
def download_resource(
    namespace_id: Annotated[str, typer.Argument(help="Exact namespace ID.")],
    path: Annotated[str, typer.Argument(help="Relative path inside the data root.")],
    destination_path: Annotated[Path, typer.Argument(help="Explicit local destination file.")],
    overwrite: Annotated[
        bool,
        typer.Option("--overwrite", help="Replace an existing destination atomically."),
    ] = False,
    max_bytes: Annotated[
        int | None,
        typer.Option("--max-bytes", min=1, help="Maximum download size in bytes."),
    ] = None,
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """Download one binary resource to an explicit local file."""

    def action(client: Client) -> BaseModel:
        if max_bytes is None:
            return client.storage.download_file(
                namespace_id=namespace_id,
                path=path,
                destination_path=destination_path,
                overwrite=overwrite,
            )
        return client.storage.download_file(
            namespace_id=namespace_id,
            path=path,
            destination_path=destination_path,
            overwrite=overwrite,
            max_bytes=max_bytes,
        )

    receipt = _run(action, output)
    if output is OutputFormat.JSON:
        _write_success({"download": _model_data(receipt)})
    else:
        _write_receipt_text(receipt, "bytes_received")


@resource_app.command("delete")
def delete_resource(
    resource_id: Annotated[str, typer.Argument(help="Exact immutable resource UUID.")],
    yes: Annotated[
        bool,
        typer.Option("--yes", help="Confirm permanent deletion."),
    ] = False,
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """Permanently delete one resource by immutable ID."""

    if not yes:
        fail(ConfigurationError("Resource deletion requires --yes."), output)
    _run(lambda client: client.resources.delete(resource_id=resource_id), output)
    if output is OutputFormat.JSON:
        _write_success({"resource_id": resource_id})
    else:
        typer.echo(f"Deleted resource {terminal_safe(resource_id)}.")
