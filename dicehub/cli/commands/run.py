from __future__ import annotations

import os
import tempfile
from collections.abc import Callable
from enum import Enum
from pathlib import Path
from typing import Annotated, Any, NoReturn, TypeVar

import typer
from pydantic import BaseModel

from dicehub.cli._runtime import fail, run_with_client
from dicehub.cli.output import CLI_SCHEMA_VERSION, OutputFormat, terminal_safe, write_json
from dicehub.client import Client
from dicehub.errors import ConfigurationError, DiceHubError, RunFailedError
from dicehub.projects.models import SortOrder
from dicehub.runs.models import RunOrderField, RunState, RunType

_Result = TypeVar("_Result")

run_app = typer.Typer(
    name="run",
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode=None,
)

_OUTPUT_OPTION = typer.Option("--output", case_sensitive=False, help="Output format.")


class _WatchOutputFormat(str, Enum):
    """Output formats supported by the streaming watch command."""

    JSONL = "jsonl"
    TEXT = "text"


_WATCH_OUTPUT_OPTION = typer.Option("--output", case_sensitive=False, help="Output format.")
_TERMINAL_FAILURE_STATES = frozenset({RunState.FAILED, RunState.INTERRUPTED, RunState.CANCELED})


def _run(action: Callable[[Client], _Result], output: OutputFormat) -> _Result:
    return run_with_client(action, output, client_type=Client)


def _fail(error: DiceHubError, output: OutputFormat) -> NoReturn:
    fail(error, output)


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


def _write_run_text(run: BaseModel) -> None:
    values = run.model_dump(mode="json")
    typer.echo(
        "\t".join(
            terminal_safe(str(values[field] if values[field] is not None else ""))
            for field in ("run_id", "state", "updated_at")
        )
    )


def _write_machine_type_text(machine_type: BaseModel) -> None:
    values = machine_type.model_dump(mode="json")
    price = values["price"]
    price_text = "" if price is None else f"{price['amount']} {price['currency']}/hour"
    typer.echo(
        "\t".join(
            terminal_safe(str(value if value is not None else ""))
            for value in (
                values["machine_type_id"],
                values["cpu_count"],
                values["gpu_count"],
                values["ram_gb"],
                values["description"],
                price_text,
            )
        )
    )


def _write_run_status(status: BaseModel, output: OutputFormat) -> None:
    if output is OutputFormat.JSON:
        _write_success({"run_status": _model_data(status)})
    else:
        _write_run_text(status)


def _download_results(
    client: Client,
    run_id: str,
    destination: Path,
    overwrite: bool,
) -> int:
    if not destination.parent.is_dir():
        raise ConfigurationError("Run result destination directory does not exist.")
    if destination.exists() and not overwrite:
        raise ConfigurationError("Run result destination already exists; use --overwrite.")

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
                count = client.runs.download_results(
                    run_id=run_id,
                    destination=stream,
                )
            os.replace(temporary_path, destination)
            temporary_path = None
            return count

        with destination.open("xb") as stream:
            direct_destination_created = True
            count = client.runs.download_results(
                run_id=run_id,
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
    raise ConfigurationError("Could not write the run result destination.")


@run_app.command("machine-types")
def list_machine_types(
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """List available machine types and net hourly prices."""

    machine_types = _run(lambda client: client.runs.list_machine_types(), output)
    if output is OutputFormat.JSON:
        _write_success(
            {"machine_types": [_model_data(machine_type) for machine_type in machine_types]}
        )
    else:
        for machine_type in machine_types:
            _write_machine_type_text(machine_type)


@run_app.command("list")
def list_runs(
    namespace_id: Annotated[str, typer.Argument(help="Exact namespace ID.")],
    include_descendants: Annotated[
        bool,
        typer.Option(
            "--include-descendants",
            help="Include runs in descendant namespaces.",
        ),
    ] = False,
    app_id: Annotated[
        str | None,
        typer.Option("--app-id", help="Restrict results to one exact app ID."),
    ] = None,
    run_types: Annotated[
        list[RunType] | None,
        typer.Option("--type", case_sensitive=False, help="Repeatable run-type filter."),
    ] = None,
    states: Annotated[
        list[RunState] | None,
        typer.Option("--state", case_sensitive=False, help="Repeatable run-state filter."),
    ] = None,
    order_by: Annotated[
        RunOrderField,
        typer.Option("--order-by", case_sensitive=False, help="Sort field."),
    ] = RunOrderField.CREATED_AT,
    order: Annotated[
        SortOrder,
        typer.Option("--order", case_sensitive=False, help="Sort direction."),
    ] = SortOrder.DESC,
    offset: Annotated[int, typer.Option("--offset", min=0, help="Result offset.")] = 0,
    limit: Annotated[int, typer.Option("--limit", min=1, max=50, help="Page size.")] = 20,
    cursor: Annotated[str | None, typer.Option("--cursor", help="Pagination cursor.")] = None,
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """List permission-scoped run metadata."""

    page = _run(
        lambda client: client.runs.list(
            namespace_id=namespace_id,
            include_descendants=include_descendants,
            app_id=app_id,
            run_types=run_types,
            states=states,
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
                "runs": [_model_data(run) for run in page.runs],
                "page": {
                    "offset": page.offset,
                    "count": page.count,
                    "cursor": page.cursor,
                },
            }
        )
    else:
        for run in page.runs:
            _write_run_text(run)


@run_app.command("get")
def get_run(
    run_id: Annotated[str, typer.Argument(help="Exact immutable run UUID.")],
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """Get safe operational metadata for one run."""

    run = _run(lambda client: client.runs.get(run_id=run_id), output)
    if output is OutputFormat.JSON:
        _write_success({"run": _model_data(run)})
    else:
        _write_run_text(run)


@run_app.command("status")
def get_run_status(
    run_id: Annotated[str, typer.Argument(help="Exact immutable run UUID.")],
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """Read one run-state snapshot without polling."""

    status = _run(lambda client: client.runs.status(run_id=run_id), output)
    if output is OutputFormat.JSON:
        _write_success({"run_status": _model_data(status)})
    else:
        _write_run_text(status)


@run_app.command("wait")
def wait_run(
    run_id: Annotated[str, typer.Argument(help="Exact immutable run UUID.")],
    timeout: Annotated[
        float,
        typer.Option("--timeout", help="Maximum number of seconds to wait."),
    ],
    poll: Annotated[
        float,
        typer.Option("--poll", help="Seconds between status checks."),
    ] = 2.0,
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """Wait for one run to reach a terminal state."""

    status = _run(
        lambda client: client.runs.wait(
            run_id=run_id,
            timeout_seconds=timeout,
            poll_seconds=poll,
        ),
        output,
    )
    _write_run_status(status, output)


@run_app.command("watch")
def watch_run(
    run_id: Annotated[str, typer.Argument(help="Exact immutable run UUID.")],
    timeout: Annotated[
        float,
        typer.Option("--timeout", help="Maximum number of seconds to watch."),
    ],
    poll: Annotated[
        float,
        typer.Option("--poll", help="Seconds between status checks."),
    ] = 2.0,
    output: Annotated[_WatchOutputFormat, _WATCH_OUTPUT_OPTION] = _WatchOutputFormat.JSONL,
) -> None:
    """Stream changed run-state snapshots until the run is terminal."""

    stream_output = OutputFormat.JSON if output is _WatchOutputFormat.JSONL else OutputFormat.TEXT

    def stream(client: Client) -> None:
        for status in client.runs.watch(
            run_id=run_id,
            timeout_seconds=timeout,
            poll_seconds=poll,
        ):
            _write_run_status(status, stream_output)
            if status.state in _TERMINAL_FAILURE_STATES:
                raise RunFailedError(status)

    _run(stream, stream_output)


@run_app.command("download-results")
def download_run_results(
    run_id: Annotated[str, typer.Argument(help="Exact immutable run UUID.")],
    destination: Annotated[Path, typer.Argument(help="Explicit local destination ZIP file.")],
    overwrite: Annotated[
        bool,
        typer.Option("--overwrite", help="Replace an existing destination atomically."),
    ] = False,
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """Download one run's results as a bounded ZIP archive."""

    count = _run(
        lambda client: _download_results(client, run_id, destination, overwrite),
        output,
    )
    if output is OutputFormat.JSON:
        _write_success(
            {
                "run_id": run_id,
                "destination": str(destination),
                "bytes": count,
            }
        )
    else:
        typer.echo(f"{terminal_safe(str(destination))}\t{count}")


@run_app.command("start")
def start_run(
    config_id: Annotated[str, typer.Argument(help="Exact configuration ID.")],
    machine_type_id: Annotated[
        str,
        typer.Option("--machine-type", help="Exact machine type ID."),
    ],
    node_count: Annotated[
        int,
        typer.Option("--nodes", min=1, max=2**31 - 1, help="Number of nodes."),
    ] = 1,
    cpu_count: Annotated[
        int | None,
        typer.Option("--cpus", min=1, max=2**31 - 1, help="Optional CPU count."),
    ] = None,
    notify: Annotated[
        bool,
        typer.Option(
            "--notify",
            help="Request notification; unavailable to managed API-key identities.",
        ),
    ] = False,
    yes: Annotated[
        bool,
        typer.Option(
            "--yes",
            help="Confirm quota use and replacement of the config's prior run.",
        ),
    ] = False,
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """Start a configuration run using an API key."""

    if not yes:
        _fail(ConfigurationError("Run start requires --yes."), output)
    status = _run(
        lambda client: client.runs.start(
            config_id=config_id,
            machine_type_id=machine_type_id,
            node_count=node_count,
            cpu_count=cpu_count,
            notify=notify,
        ),
        output,
    )
    if output is OutputFormat.JSON:
        _write_success({"run_status": _model_data(status)})
    else:
        _write_run_text(status)


@run_app.command("stop")
def stop_run(
    run_id: Annotated[str, typer.Argument(help="Exact immutable run UUID.")],
    yes: Annotated[
        bool,
        typer.Option("--yes", help="Confirm interruption of the run."),
    ] = False,
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """Stop a run using an API key."""

    if not yes:
        _fail(ConfigurationError("Run stop requires --yes."), output)
    _run(lambda client: client.runs.stop(run_id=run_id), output)
    if output is OutputFormat.JSON:
        _write_success({"run_id": run_id})
    else:
        typer.echo(f"Stop requested for run {terminal_safe(run_id)}.")
