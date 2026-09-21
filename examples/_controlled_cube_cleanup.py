"""Bounded run cleanup for the controlled-cube example."""

from __future__ import annotations

import json
import sys
from typing import Protocol

import dicehub as dh
from examples._controlled_cube import (
    TERMINAL_RUN_STATES,
    ControlledCubeError,
    wait_for_terminal,
)


class CleanupSettings(Protocol):
    @property
    def poll_seconds(self) -> float: ...

    @property
    def stop_timeout_seconds(self) -> float: ...


class Emit(Protocol):
    def __call__(self, event: str, **values: object) -> None: ...


def stop_for_cleanup(
    client: dh.Client,
    run_id: str,
    *,
    settings: CleanupSettings,
    primary_error: BaseException | None,
    emit: Emit,
) -> bool:
    """Stop one exact active run or wait for one queued run to resolve."""

    try:
        current = client.runs.status(run_id=run_id)
    except Exception:
        current = None
    if current is not None and current.state in TERMINAL_RUN_STATES:
        emit("cleanup_run_terminal", run_id=run_id, state=current.state.value)
        return True

    stop_already_requested = current is not None and current.state in {
        dh.RunState.STOPPING,
        dh.RunState.INTERRUPTING,
    }
    waiting_for_queue_resolution = current is not None and current.state is dh.RunState.IDLE
    if waiting_for_queue_resolution:
        emit("cleanup_run_waiting_for_queue", run_id=run_id)
    if not stop_already_requested and not waiting_for_queue_resolution:
        try:
            client.runs.stop(run_id=run_id)
            emit("cleanup_run_stop_requested", run_id=run_id)
        except dh.MutationOutcomeUnknownError:
            emit("cleanup_run_stop_outcome_unknown", run_id=run_id)
        except Exception as cleanup_error:
            try:
                reconciled = client.runs.status(run_id=run_id)
            except Exception:
                reconciled = None
            if reconciled is not None and reconciled.state in TERMINAL_RUN_STATES:
                emit("cleanup_run_terminal", run_id=run_id, state=reconciled.state.value)
                return True
            cleanup_failed(
                run_id,
                "run stop failed and no terminal state was confirmed; project deletion skipped",
                cleanup_error,
                primary_error,
                resource="run",
            )
            return False

    try:
        terminal = wait_for_terminal(
            lambda: client.runs.status(run_id=run_id),
            timeout_seconds=settings.stop_timeout_seconds,
            poll_seconds=settings.poll_seconds,
            on_status=lambda status: emit(
                "cleanup_run_status",
                run_id=status.run_id,
                state=status.state.value,
            ),
        )
    except Exception as cleanup_error:
        cleanup_failed(
            run_id,
            "run did not reach a confirmed terminal state; project deletion skipped",
            cleanup_error,
            primary_error,
            resource="run",
        )
        return False
    emit("cleanup_run_terminal", run_id=run_id, state=terminal.state.value)
    return True


def cleanup_failed(
    resource_id: str,
    reason: str,
    cleanup_error: Exception,
    primary_error: BaseException | None,
    *,
    resource: str,
) -> None:
    message = f"{reason}; reconcile exact {resource} ID {resource_id!r}."
    print(
        json.dumps(
            {
                "event": "cleanup_failed",
                f"{resource}_id": resource_id,
                "reason": reason,
            }
        ),
        file=sys.stderr,
    )
    if primary_error is None:
        raise ControlledCubeError(message) from cleanup_error
