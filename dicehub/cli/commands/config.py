from __future__ import annotations

import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any, TypeVar

import typer
from pydantic import BaseModel

from dicehub.cli._runtime import fail, run_with_client
from dicehub.cli.output import CLI_SCHEMA_VERSION, OutputFormat, terminal_safe, write_json
from dicehub.client import Client
from dicehub.configs.models import ConfigContentArea
from dicehub.errors import ConfigurationError
from dicehub.projects.models import SortOrder

_Result = TypeVar("_Result")

config_app = typer.Typer(
    name="config",
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode=None,
)
content_app = typer.Typer(
    name="content",
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode=None,
)
config_app.add_typer(content_app, name="content")

_OUTPUT_OPTION = typer.Option("--output", case_sensitive=False, help="Output format.")


def _run(action: Callable[[Client], _Result], output: OutputFormat) -> _Result:
    return run_with_client(action, output, client_type=Client)


def _config_data(config: BaseModel) -> dict[str, Any]:
    return config.model_dump(mode="json")


def _write_success(data: dict[str, Any]) -> None:
    write_json(
        {
            "schema_version": CLI_SCHEMA_VERSION,
            "ok": True,
            "data": data,
            "error": None,
        }
    )


def _write_config_text(config: BaseModel) -> None:
    values = config.model_dump(mode="json")
    typer.echo(
        "\t".join(
            terminal_safe(str(values[field] if values[field] is not None else ""))
            for field in ("config_id", "app_id", "name", "is_default")
        )
    )


def _content_entry_data(entry: BaseModel) -> dict[str, Any]:
    return entry.model_dump(mode="json")


def _read_utf8(path: Path) -> str:
    content: str | None = None
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        pass
    if content is None:
        raise ConfigurationError("Could not read the UTF-8 config text source.")
    return content


def _upload_file(client: Client, config_id: str, config_path: str, source: Path) -> int:
    size: int | None = None
    uploaded = False
    try:
        size = source.stat().st_size
        with source.open("rb") as stream:
            client.configs.upload_file(
                config_id=config_id,
                path=config_path,
                source=stream,
            )
        uploaded = True
    except OSError:
        pass
    if size is None or not uploaded:
        raise ConfigurationError("Could not read the config file source.")
    return size


def _download_file(
    client: Client,
    config_id: str,
    config_path: str,
    destination: Path,
    overwrite: bool,
) -> int:
    if not destination.parent.is_dir():
        raise ConfigurationError("Config file destination directory does not exist.")
    if destination.exists() and not overwrite:
        raise ConfigurationError("Config file destination already exists; use --overwrite.")

    temporary_path: Path | None = None
    direct_destination_created = False
    try:
        if overwrite:
            descriptor, name = tempfile.mkstemp(
                prefix=f".{destination.name}.",
                dir=destination.parent,
            )
            temporary_path = Path(name)
            with os.fdopen(descriptor, "wb") as stream:
                count = client.configs.download_file(
                    config_id=config_id,
                    path=config_path,
                    destination=stream,
                )
            os.replace(temporary_path, destination)
            temporary_path = None
            return count

        with destination.open("xb") as stream:
            direct_destination_created = True
            count = client.configs.download_file(
                config_id=config_id,
                path=config_path,
                destination=stream,
            )
        direct_destination_created = False
        return count
    except OSError:
        if direct_destination_created:
            destination.unlink(missing_ok=True)
    except Exception:
        if direct_destination_created:
            destination.unlink(missing_ok=True)
        raise
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    raise ConfigurationError("Could not write the config file destination.")


@config_app.command("create")
def create_config(
    app_id: Annotated[str, typer.Argument(help="Exact destination app ID.")],
    source_config_id: Annotated[
        str | None,
        typer.Option(
            "--source-config-id",
            help="Existing config ID in the same app; defaults to the app default.",
        ),
    ] = None,
    name: Annotated[
        str | None,
        typer.Option("--name", help="New config name; defaults to the source name."),
    ] = None,
    description: Annotated[
        str | None,
        typer.Option("--description", help="New config description."),
    ] = None,
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """Create a configuration using an API key."""

    config = _run(
        lambda client: client.configs.create(
            app_id=app_id,
            source_config_id=source_config_id,
            name=name,
            description=description,
        ),
        output,
    )
    if output is OutputFormat.JSON:
        _write_success({"config": _config_data(config)})
    else:
        _write_config_text(config)


@config_app.command("update")
def update_config(
    config_id: Annotated[str, typer.Argument(help="Exact config ID.")],
    name: Annotated[
        str | None,
        typer.Option("--name", help="New config name."),
    ] = None,
    description: Annotated[
        str | None,
        typer.Option("--description", help="New config description."),
    ] = None,
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """Update configuration name or description."""

    _run(
        lambda client: client.configs.update(
            config_id=config_id,
            name=name,
            description=description,
        ),
        output,
    )
    if output is OutputFormat.JSON:
        _write_success({"config_id": config_id, "updated": True})
    else:
        typer.echo(terminal_safe(config_id))


@config_app.command("delete")
def delete_config(
    config_id: Annotated[str, typer.Argument(help="Exact config ID.")],
    yes: Annotated[
        bool,
        typer.Option("--yes", help="Confirm permanent deletion of the entire configuration."),
    ] = False,
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """Permanently delete an entire configuration using an API key."""

    if not yes:
        fail(ConfigurationError("Config deletion requires --yes."), output)
    _run(lambda client: client.configs.delete(config_id=config_id), output)
    if output is OutputFormat.JSON:
        _write_success({"config_id": config_id})
    else:
        typer.echo(f"Deleted config {terminal_safe(config_id)}.")


@content_app.command("list")
def list_config_content(
    config_id: Annotated[str, typer.Argument(help="Exact config ID.")],
    area: Annotated[
        ConfigContentArea,
        typer.Option("--area", case_sensitive=False, help="Content area."),
    ],
    path: Annotated[
        str,
        typer.Option("--path", help="Relative directory inside the selected area."),
    ] = "",
    recursive: Annotated[
        bool,
        typer.Option("--recursive", help="Include all descendants."),
    ] = False,
    offset: Annotated[int, typer.Option("--offset", min=0, help="Result offset.")] = 0,
    limit: Annotated[int, typer.Option("--limit", min=1, max=50, help="Page size.")] = 20,
    cursor: Annotated[str | None, typer.Option("--cursor", help="Pagination cursor.")] = None,
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """List text or file entries inside one configuration."""

    page = _run(
        lambda client: client.configs.list_content(
            config_id=config_id,
            area=area,
            path=path,
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
                "entries": [_content_entry_data(entry) for entry in page.entries],
                "page": {
                    "offset": page.offset,
                    "count": page.count,
                    "cursor": page.cursor,
                },
            }
        )
    else:
        for entry in page.entries:
            typer.echo(f"{terminal_safe(entry.path)}\t{terminal_safe(entry.resource_type.value)}")


@content_app.command("get-text")
def get_config_text(
    config_id: Annotated[str, typer.Argument(help="Exact config ID.")],
    path: Annotated[str, typer.Argument(help="Relative path inside config texts.")],
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """Read one configuration text resource."""

    content = _run(
        lambda client: client.configs.get_text(config_id=config_id, path=path),
        output,
    )
    if output is OutputFormat.JSON:
        _write_success({"config_id": config_id, "path": path, "content": content})
    else:
        typer.echo(terminal_safe(content))


@content_app.command("set-text")
def set_config_text(
    config_id: Annotated[str, typer.Argument(help="Exact config ID.")],
    path: Annotated[str, typer.Argument(help="Relative path inside config texts.")],
    source: Annotated[
        Path,
        typer.Argument(help="Local UTF-8 source file."),
    ],
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """Create or replace one configuration text resource."""

    def action(client: Client) -> None:
        client.configs.set_text(
            config_id=config_id,
            path=path,
            content=_read_utf8(source),
        )

    _run(action, output)
    if output is OutputFormat.JSON:
        _write_success({"config_id": config_id, "path": path, "updated": True})
    else:
        typer.echo(terminal_safe(path))


@content_app.command("delete")
def delete_config_content(
    config_id: Annotated[str, typer.Argument(help="Exact config ID.")],
    path: Annotated[str, typer.Argument(help="Relative content path.")],
    area: Annotated[
        ConfigContentArea,
        typer.Option("--area", case_sensitive=False, help="Content area."),
    ],
    yes: Annotated[
        bool,
        typer.Option("--yes", help="Confirm permanent deletion."),
    ] = False,
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """Delete one configuration content entry or subtree."""

    if not yes:
        fail(ConfigurationError("Config content deletion requires --yes."), output)
    _run(
        lambda client: client.configs.delete_content(
            config_id=config_id,
            area=area,
            path=path,
        ),
        output,
    )
    if output is OutputFormat.JSON:
        _write_success({"config_id": config_id, "path": path, "deleted": True})
    else:
        typer.echo(terminal_safe(path))


@content_app.command("upload")
def upload_config_file(
    config_id: Annotated[str, typer.Argument(help="Exact config ID.")],
    path: Annotated[str, typer.Argument(help="Relative path inside config files.")],
    source: Annotated[Path, typer.Argument(help="Local binary source file.")],
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """Upload or replace one configuration file."""

    count = _run(
        lambda client: _upload_file(client, config_id, path, source),
        output,
    )
    if output is OutputFormat.JSON:
        _write_success({"config_id": config_id, "path": path, "bytes": count})
    else:
        typer.echo(f"{terminal_safe(path)}\t{count}")


@content_app.command("download")
def download_config_file(
    config_id: Annotated[str, typer.Argument(help="Exact config ID.")],
    path: Annotated[str, typer.Argument(help="Relative path inside config files.")],
    destination: Annotated[Path, typer.Argument(help="Explicit local destination file.")],
    overwrite: Annotated[
        bool,
        typer.Option("--overwrite", help="Replace an existing destination atomically."),
    ] = False,
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """Download one configuration file to an explicit local path."""

    count = _run(
        lambda client: _download_file(
            client,
            config_id,
            path,
            destination,
            overwrite,
        ),
        output,
    )
    if output is OutputFormat.JSON:
        _write_success(
            {
                "config_id": config_id,
                "path": path,
                "destination": str(destination),
                "bytes": count,
            }
        )
    else:
        typer.echo(f"{terminal_safe(str(destination))}\t{count}")


@config_app.command("list")
def list_configs(
    app_id: Annotated[str, typer.Argument(help="Exact parent app ID.")],
    search_filter: Annotated[
        str | None,
        typer.Option("--search", "--search-filter", help="Config-name search filter."),
    ] = None,
    order: Annotated[
        SortOrder,
        typer.Option("--order", case_sensitive=False, help="Config-ID sort direction."),
    ] = SortOrder.ASC,
    offset: Annotated[int, typer.Option("--offset", min=0, help="Result offset.")] = 0,
    limit: Annotated[int, typer.Option("--limit", min=1, max=50, help="Page size.")] = 20,
    cursor: Annotated[str | None, typer.Option("--cursor", help="Pagination cursor.")] = None,
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """List configuration metadata visible inside one app."""

    page = _run(
        lambda client: client.configs.list(
            app_id=app_id,
            search_filter=search_filter,
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
                "configs": [_config_data(config) for config in page.configs],
                "page": {
                    "offset": page.offset,
                    "count": page.count,
                    "cursor": page.cursor,
                },
            }
        )
    else:
        for config in page.configs:
            _write_config_text(config)


@config_app.command("get")
def get_config(
    config_id: Annotated[str, typer.Argument(help="Exact config ID.")],
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """Get configuration metadata by immutable ID."""

    config = _run(lambda client: client.configs.get(config_id=config_id), output)
    if output is OutputFormat.JSON:
        _write_success({"config": _config_data(config)})
    else:
        _write_config_text(config)
