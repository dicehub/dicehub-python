from __future__ import annotations

import os
import stat
from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Annotated, Any, NoReturn, TypeVar

import typer

from dicehub.api_keys._validation import validated_validity_window
from dicehub.api_keys.models import ApiKey, NamespacePermission
from dicehub.cli._runtime import fail, run_with_client
from dicehub.cli.output import CLI_SCHEMA_VERSION, OutputFormat, terminal_safe, write_json
from dicehub.client import Client
from dicehub.errors import ConfigurationError, DiceHubError

_Result = TypeVar("_Result")

api_key_app = typer.Typer(
    name="api-key",
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode=None,
)

_OUTPUT_OPTION = typer.Option("--output", case_sensitive=False, help="Output format.")
_SESSION_REQUIRED_MESSAGE = "API-key administration requires DICEHUB_SESSION_COOKIE."


def _run(action: Callable[[Client], _Result], output: OutputFormat) -> _Result:
    return run_with_client(
        action,
        output,
        client_type=Client,
        session_required_message=_SESSION_REQUIRED_MESSAGE,
    )


def _fail(error: DiceHubError, output: OutputFormat) -> NoReturn:
    fail(error, output)


def _write_success(data: dict[str, Any]) -> None:
    write_json(
        {
            "schema_version": CLI_SCHEMA_VERSION,
            "ok": True,
            "data": data,
            "error": None,
        }
    )


def _timestamp_data(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat().replace("+00:00", "Z")


def _api_key_data(api_key: ApiKey) -> dict[str, Any]:
    return {
        "api_key_id": api_key.api_key_id,
        "name": api_key.name,
        "prefix": api_key.prefix,
        "permissions": [permission.value for permission in api_key.permissions],
        "created_at": _timestamp_data(api_key.created_at),
        "updated_at": _timestamp_data(api_key.updated_at),
        "last_used_at": _timestamp_data(api_key.last_used_at),
        "status": api_key.status.value,
        "not_before": _timestamp_data(api_key.not_before),
        "expires_at": _timestamp_data(api_key.expires_at),
        "validity_status": api_key.validity_status.value,
    }


def _write_api_key_text(api_key: ApiKey) -> None:
    _write_api_key_text_data(_api_key_data(api_key))


def _write_api_key_text_data(values: dict[str, Any]) -> None:
    permissions = values.get("permissions", [])
    permission_text = ",".join(str(permission) for permission in permissions)
    typer.echo(
        "\t".join(
            terminal_safe(str(value if value is not None else ""))
            for value in (
                values["api_key_id"],
                values["status"],
                values["prefix"],
                values["name"],
                permission_text,
                values["created_at"],
                values["updated_at"],
                values["last_used_at"],
                values["not_before"],
                values["expires_at"],
                values["validity_status"],
            )
        )
    )


def _validate_secret_fd(secret_fd: int, output: OutputFormat) -> None:
    try:
        descriptor = os.fstat(secret_fd)
        if os.isatty(secret_fd) or not (
            stat.S_ISFIFO(descriptor.st_mode) or stat.S_ISSOCK(descriptor.st_mode)
        ):
            raise OSError("unsupported secret descriptor type")
        for standard_fd in (0, 1, 2):
            try:
                standard_descriptor = os.fstat(standard_fd)
            except (OSError, ValueError):
                continue
            if os.path.samestat(descriptor, standard_descriptor):
                raise OSError("secret descriptor aliases a standard stream")
        os.write(secret_fd, b"")
    except (OSError, ValueError):
        _fail(
            ConfigurationError(
                "--secret-fd must reference an open writable non-stdio pipe or socket."
            ),
            output,
        )


def _deliver_secret(secret_fd: int, secret: str) -> bool:
    try:
        remaining = memoryview((secret + "\n").encode("ascii"))
        while remaining:
            written = os.write(secret_fd, remaining)
            if written <= 0:
                return False
            remaining = remaining[written:]
    except Exception:
        return False
    return True


def _validated_permissions(
    permissions: Sequence[NamespacePermission] | None,
    *,
    required: bool,
    output: OutputFormat,
) -> list[NamespacePermission] | None:
    if permissions is None:
        if required:
            _fail(ConfigurationError("At least one --permission is required."), output)
        return None
    if not permissions:
        _fail(ConfigurationError("At least one --permission is required."), output)
    if len(set(permissions)) != len(permissions):
        _fail(ConfigurationError("--permission values must be unique."), output)
    return list(permissions)


def _parsed_timestamp_option(
    value: str | None,
    *,
    option: str,
    output: OutputFormat,
) -> datetime | None:
    if value is None:
        return None
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        _fail(
            ConfigurationError(f"{option} must be an ISO 8601 timestamp with a timezone."),
            output,
        )


@api_key_app.command("list")
def list_api_keys(
    namespace_id: Annotated[str, typer.Argument(help="Exact scope namespace ID.")],
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """List managed API-key metadata inside one namespace."""

    api_keys = _run(
        lambda client: client.api_keys.list(namespace_id=namespace_id),
        output,
    )
    if output is OutputFormat.JSON:
        _write_success({"api_keys": [_api_key_data(api_key) for api_key in api_keys]})
    else:
        for api_key in api_keys:
            _write_api_key_text(api_key)


@api_key_app.command("get")
def get_api_key(
    namespace_id: Annotated[str, typer.Argument(help="Exact scope namespace ID.")],
    api_key_id: Annotated[str, typer.Argument(help="Exact API-key ID.")],
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """Get managed API-key metadata by immutable ID."""

    api_key = _run(
        lambda client: client.api_keys.get(
            namespace_id=namespace_id,
            api_key_id=api_key_id,
        ),
        output,
    )
    if output is OutputFormat.JSON:
        _write_success({"api_key": _api_key_data(api_key) if api_key is not None else None})
    elif api_key is None:
        typer.echo("No API key found.")
    else:
        _write_api_key_text(api_key)


@api_key_app.command("permissions")
def list_api_key_permissions(
    namespace_id: Annotated[str, typer.Argument(help="Exact scope namespace ID.")],
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """List permissions the current session may assign in one namespace."""

    permissions = _run(
        lambda client: client.api_keys.list_permissions(namespace_id=namespace_id),
        output,
    )
    values = [permission.value for permission in permissions]
    if output is OutputFormat.JSON:
        _write_success({"permissions": values})
    else:
        for value in values:
            typer.echo(value)


@api_key_app.command("create")
def create_api_key(
    namespace_id: Annotated[str, typer.Argument(help="Exact scope namespace ID.")],
    name: Annotated[str, typer.Option("--name", help="API-key name.")],
    secret_fd: Annotated[
        int,
        typer.Option(
            "--secret-fd",
            min=3,
            help="Open writable pipe/socket for the one-time secret (must be at least 3).",
        ),
    ],
    permissions: Annotated[
        list[NamespacePermission] | None,
        typer.Option(
            "--permission",
            case_sensitive=False,
            help="Permission to grant; repeat for each permission.",
        ),
    ] = None,
    not_before: Annotated[
        str | None,
        typer.Option(
            "--not-before",
            help="Optional ISO 8601 activation timestamp with timezone.",
        ),
    ] = None,
    expires_at: Annotated[
        str | None,
        typer.Option(
            "--expires-at",
            help="Optional ISO 8601 expiration timestamp with timezone.",
        ),
    ] = None,
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """Create a scoped API key and deliver its secret to a secure descriptor."""

    validated_permissions = _validated_permissions(
        permissions,
        required=True,
        output=output,
    )
    assert validated_permissions is not None
    parsed_not_before = _parsed_timestamp_option(
        not_before,
        option="--not-before",
        output=output,
    )
    parsed_expires_at = _parsed_timestamp_option(
        expires_at,
        option="--expires-at",
        output=output,
    )
    try:
        parsed_not_before, parsed_expires_at = validated_validity_window(
            parsed_not_before,
            parsed_expires_at,
        )
    except ConfigurationError as error:
        _fail(error, output)
    _validate_secret_fd(secret_fd, output)
    api_key = _run(
        lambda client: client.api_keys.create(
            namespace_id=namespace_id,
            name=name,
            permissions=validated_permissions,
            not_before=parsed_not_before,
            expires_at=parsed_expires_at,
        ),
        output,
    )
    metadata = _api_key_data(api_key)
    api_key_id = api_key.api_key_id
    delivered = _deliver_secret(secret_fd, api_key.value.get_secret_value())
    del api_key
    if not delivered:
        _fail(
            DiceHubError(
                "API key "
                f"{api_key_id} was created, but its secret could not be delivered. "
                f"Revoke API key {api_key_id} before retrying."
            ),
            output,
        )
    if output is OutputFormat.JSON:
        _write_success({"api_key": metadata})
    else:
        _write_api_key_text_data(metadata)


@api_key_app.command("update")
def update_api_key(
    namespace_id: Annotated[str, typer.Argument(help="Exact scope namespace ID.")],
    api_key_id: Annotated[str, typer.Argument(help="Exact API-key ID.")],
    name: Annotated[str, typer.Option("--name", help="Replacement API-key name.")],
    permissions: Annotated[
        list[NamespacePermission] | None,
        typer.Option(
            "--permission",
            case_sensitive=False,
            help="Replacement permission set; repeat. Omit to preserve permissions.",
        ),
    ] = None,
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """Replace an API-key name and, optionally, its complete permission set."""

    validated_permissions = _validated_permissions(
        permissions,
        required=False,
        output=output,
    )
    api_key = _run(
        lambda client: client.api_keys.update(
            namespace_id=namespace_id,
            api_key_id=api_key_id,
            name=name,
            permissions=validated_permissions,
        ),
        output,
    )
    if output is OutputFormat.JSON:
        _write_success({"api_key": _api_key_data(api_key)})
    else:
        _write_api_key_text(api_key)


@api_key_app.command("revoke")
def revoke_api_key(
    api_key_id: Annotated[str, typer.Argument(help="Exact API-key ID.")],
    yes: Annotated[
        bool,
        typer.Option("--yes", help="Confirm permanent API-key revocation."),
    ] = False,
    output: Annotated[OutputFormat, _OUTPUT_OPTION] = OutputFormat.JSON,
) -> None:
    """Permanently revoke one API key using its immutable ID."""

    if not yes:
        _fail(ConfigurationError("API-key revocation requires --yes."), output)
    _run(lambda client: client.api_keys.delete(api_key_id=api_key_id), output)
    if output is OutputFormat.JSON:
        _write_success({"api_key_id": api_key_id})
    else:
        typer.echo(f"Revoked API key {terminal_safe(api_key_id)}.")
