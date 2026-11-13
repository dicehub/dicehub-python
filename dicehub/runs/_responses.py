from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel, ValidationError

from dicehub.errors import (
    MutationOutcomeUnknownError,
    ProtocolError,
    RunTimeoutError,
)
from dicehub.runs._graphql import (
    RunDetailPayload,
    RunPayload,
    RunStatusPayload,
)
from dicehub.runs.models import (
    Run,
    RunDetail,
    RunError,
    RunExecutionStatus,
    RunFlag,
    RunState,
    RunStatus,
    RunType,
)

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
        raise ProtocolError("dicehub returned an incompatible run response.")
    return response


def _run_from_payload(payload: RunPayload) -> Run:
    return Run(
        run_id=payload.run_id,
        namespace_id=payload.namespace_id,
        name=payload.name,
        state=RunState(payload.state),
        run_type=RunType(payload.run_type) if payload.run_type is not None else None,
        created_at=payload.created_at,
        updated_at=payload.updated_at,
    )


def _run_detail_from_payload(payload: RunDetailPayload) -> RunDetail:
    return RunDetail(
        **_run_from_payload(payload).model_dump(),
        run_internal_id=payload.run_internal_id,
        machine_type_id=payload.machine_type_id,
        node_count=payload.node_count,
        cpu_count=payload.cpu_count,
        execution_status=(
            RunExecutionStatus(payload.execution_status)
            if payload.execution_status is not None
            else None
        ),
        error=RunError(payload.error) if payload.error is not None else None,
        flags=tuple(RunFlag(flag) for flag in payload.flags or ()),
        template_version=payload.template_version,
        module=payload.module,
        flow=payload.flow,
        queue=payload.queue,
        study_id=payload.study_id,
        stage=payload.stage,
        batch=payload.batch,
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
        "The run mutation may have completed, but dicehub did not confirm its outcome.",
        request_id=request_id,
    )


def _meaningful_status(status: RunStatus) -> tuple[object, ...]:
    return (status.state, status.execution_status, status.error, frozenset(status.flags))


def _run_timeout(
    run_id: str,
    timeout_seconds: float,
    last_status: RunStatus | None,
) -> RunTimeoutError:
    return RunTimeoutError(
        run_id=run_id,
        timeout_seconds=timeout_seconds,
        last_status=last_status,
    )
