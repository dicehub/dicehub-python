from __future__ import annotations

from collections.abc import Iterator
from typing import BinaryIO, TypeVar
from urllib.parse import quote

from pydantic import BaseModel, ValidationError

from dicehub.configs._graphql import (
    ConfigPayload,
)
from dicehub.configs._validation import (
    validated_content_path,
    validated_id,
)
from dicehub.configs.models import (
    Config,
)
from dicehub.errors import (
    ConfigurationError,
    MutationOutcomeUnknownError,
    ProtocolError,
)
from dicehub.runs._graphql import RunStatusPayload
from dicehub.runs.models import RunError, RunExecutionStatus, RunFlag, RunState, RunStatus

WireModelT = TypeVar("WireModelT", bound=BaseModel)


def _validated_response(
    response_type: type[WireModelT],
    data: dict[str, object],
) -> WireModelT:
    response: WireModelT | None = None
    try:
        response = response_type.model_validate(data)
    except ValidationError:
        pass
    if response is None:
        raise ProtocolError("dicehub returned an incompatible config response.")
    return response


def _config_from_payload(payload: ConfigPayload) -> Config:
    return Config(
        config_id=payload.config_id,
        app_id=payload.app_id,
        config_internal_id=payload.config_internal_id,
        name=payload.name,
        description=payload.description,
        is_default=payload.is_default,
        template_version=payload.template_version,
        updating=payload.updating,
    )


def _run_status_from_payload(payload: RunStatusPayload) -> RunStatus:
    return RunStatus(
        run_id=payload.run_id,
        state=RunState(payload.state),
        execution_status=(
            RunExecutionStatus(payload.execution_status)
            if payload.execution_status is not None
            else None
        ),
        error=RunError(payload.error) if payload.error is not None else None,
        flags=tuple(RunFlag(flag) for flag in payload.flags or ()),
        updated_at=payload.updated_at,
    )


def _unknown_mutation_outcome(*, request_id: str | None = None) -> MutationOutcomeUnknownError:
    return MutationOutcomeUnknownError(
        "The config mutation may have completed, but dicehub did not confirm its outcome.",
        request_id=request_id,
    )


def _file_endpoint(config_id: str, path: str) -> str:
    validated_config_id = validated_id(config_id, "config ID")
    validated_path = validated_content_path(path)
    encoded_path = quote(validated_path, safe="/-._~")
    return f"api/v1/configs/{validated_config_id}/files/{encoded_path}"


def _bounded_file_chunks(source: BinaryIO, max_bytes: int) -> Iterator[bytes]:
    if not callable(getattr(source, "read", None)):
        raise ConfigurationError("Config file source must be readable.")
    total = 0
    while True:
        chunk = source.read(64 * 1024)
        if not isinstance(chunk, bytes):
            raise ConfigurationError("Config file source must return bytes.")
        if not chunk:
            return
        total += len(chunk)
        if total > max_bytes:
            raise ConfigurationError("Config file exceeds the configured upload limit.")
        yield chunk
