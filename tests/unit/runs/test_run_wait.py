from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field

import httpx
import pytest

from dicehub import (
    Client,
    ProtocolError,
    RunFailedError,
    RunState,
    RunTimeoutError,
    TransportError,
)
from dicehub.runs import service as runs_service

RUN_ID = "12345678-1234-5678-9234-567812345678"
OTHER_RUN_ID = "87654321-4321-6789-a234-567812345678"


@dataclass
class _Clock:
    now: float = 0.0
    sleeps: list[float] = field(default_factory=list)

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> _Clock:
    value = _Clock()
    monkeypatch.setattr(runs_service, "monotonic", value.monotonic)
    monkeypatch.setattr(runs_service, "sleep", value.sleep)
    return value


def _response(
    state: str,
    *,
    run_id: str = RUN_ID,
    updated_at: str = "2026-08-11T10:11:12.456Z",
    execution_status: str | None = None,
    error: str | None = "NONE",
    flags: list[str] | None = None,
) -> dict[str, object]:
    return {
        "data": {
            "runs": {
                "getSingleRunById": {
                    "status": {"succeeded": True, "error": None},
                    "run": {
                        "runId": run_id,
                        "state": state,
                        "executionStatus": execution_status,
                        "error": error,
                        "flags": flags or [],
                        "updatedAt": updated_at,
                    },
                }
            }
        }
    }


def _client(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    timeout: float = 10.0,
) -> Client:
    return Client(
        base_url="https://dicehub.test",
        api_key="test-api-key",
        timeout=timeout,
        transport=httpx.MockTransport(handler),
    )


def _sequence_handler(
    states: list[tuple[str, str]],
    timeout_caps: list[float],
) -> Callable[[httpx.Request], httpx.Response]:
    remaining = iter(states)

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["operationName"] == "GetRunStatus"
        assert payload["variables"] == {"runId": RUN_ID}
        timeout_caps.append(request.extensions["timeout"]["read"])
        state, updated_at = next(remaining)
        return httpx.Response(
            200,
            json=_response(state, updated_at=updated_at),
            request=request,
        )

    return handler


def test_wait_returns_finished_and_caps_each_request_to_remaining_deadline(
    clock: _Clock,
) -> None:
    timeout_caps: list[float] = []
    handler = _sequence_handler(
        [
            ("RUNNING", "2026-08-11T10:11:12Z"),
            ("FINISHED", "2026-08-11T10:11:14Z"),
        ],
        timeout_caps,
    )

    with _client(handler) as client:
        status = client.runs.wait(run_id=RUN_ID, timeout_seconds=5, poll_seconds=2)

    assert status.state is RunState.FINISHED
    assert timeout_caps == [5, 3]
    assert clock.sleeps == [2]


def test_request_timeout_cap_never_loosens_the_client_timeout(clock: _Clock) -> None:
    timeout_caps: list[float] = []
    handler = _sequence_handler(
        [("FINISHED", "2026-08-11T10:11:12Z")],
        timeout_caps,
    )

    with _client(handler, timeout=1.5) as client:
        client.runs.wait(run_id=RUN_ID, timeout_seconds=30, poll_seconds=2)

    assert timeout_caps == [1.5]
    assert clock.sleeps == []


def test_wait_returns_stopped_without_sleep(clock: _Clock) -> None:
    handler = _sequence_handler(
        [("STOPPED", "2026-08-11T10:11:12Z")],
        [],
    )

    with _client(handler) as client:
        status = client.runs.wait(run_id=RUN_ID, timeout_seconds=5)

    assert status.state is RunState.STOPPED
    assert clock.sleeps == []


@pytest.mark.parametrize("state", ["FAILED", "INTERRUPTED", "CANCELED"])
def test_wait_raises_typed_terminal_failure(state: str, clock: _Clock) -> None:
    handler = _sequence_handler([(state, "2026-08-11T10:11:12Z")], [])

    with _client(handler) as client, pytest.raises(RunFailedError) as captured:
        client.runs.wait(run_id=RUN_ID, timeout_seconds=5)

    assert captured.value.status.state.value == state
    assert captured.value.as_dict()["run_status"] == captured.value.status.model_dump(mode="json")
    assert captured.value.retryable is False
    assert clock.sleeps == []


def test_watch_omits_timestamp_only_duplicates_and_yields_terminal_once(
    clock: _Clock,
) -> None:
    timeout_caps: list[float] = []
    handler = _sequence_handler(
        [
            ("RUNNING", "2026-08-11T10:11:12Z"),
            ("RUNNING", "2026-08-11T10:11:13Z"),
            ("PROCESSING", "2026-08-11T10:11:14Z"),
            ("FINISHED", "2026-08-11T10:11:15Z"),
        ],
        timeout_caps,
    )

    with _client(handler) as client:
        statuses = list(client.runs.watch(run_id=RUN_ID, timeout_seconds=10, poll_seconds=1))

    assert [status.state for status in statuses] == [
        RunState.RUNNING,
        RunState.PROCESSING,
        RunState.FINISHED,
    ]
    assert timeout_caps == [10, 9, 8, 7]
    assert clock.sleeps == [1, 1, 1]


def test_wait_uses_the_exact_deadline_and_reports_last_status(clock: _Clock) -> None:
    timeout_caps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        timeout_caps.append(request.extensions["timeout"]["read"])
        return httpx.Response(200, json=_response("RUNNING"), request=request)

    with _client(handler) as client, pytest.raises(RunTimeoutError) as captured:
        client.runs.wait(run_id=RUN_ID, timeout_seconds=3, poll_seconds=2)

    assert timeout_caps == [3, 1]
    assert clock.sleeps == [2, 1]
    assert captured.value.exit_code == 6
    assert captured.value.retryable is True
    assert captured.value.last_status is not None
    assert captured.value.last_status.state is RunState.RUNNING
    assert captured.value.as_dict()["last_status"] == captured.value.last_status.model_dump(
        mode="json"
    )


def test_transport_timeout_before_deadline_remains_a_transport_error(clock: _Clock) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("private transport detail", request=request)

    with _client(handler) as client, pytest.raises(TransportError):
        client.runs.wait(run_id=RUN_ID, timeout_seconds=3, poll_seconds=1)

    assert clock.now == 0


def test_transport_timeout_at_deadline_becomes_a_run_timeout(clock: _Clock) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        clock.now = 3
        raise httpx.ReadTimeout("private transport detail", request=request)

    with _client(handler) as client, pytest.raises(RunTimeoutError) as captured:
        client.runs.wait(run_id=RUN_ID, timeout_seconds=3, poll_seconds=1)

    assert captured.value.__context__ is None
    assert captured.value.last_status is None


def test_terminal_response_after_deadline_is_not_accepted(clock: _Clock) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        clock.now = 3
        return httpx.Response(200, json=_response("FINISHED"), request=request)

    with _client(handler) as client, pytest.raises(RunTimeoutError) as captured:
        client.runs.wait(run_id=RUN_ID, timeout_seconds=3, poll_seconds=1)

    assert captured.value.last_status is not None
    assert captured.value.last_status.state is RunState.FINISHED
    assert clock.sleeps == []


def test_closing_watch_stops_before_sleep_or_another_request(clock: _Clock) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=_response("RUNNING"), request=request)

    with _client(handler) as client:
        statuses = client.runs.watch(run_id=RUN_ID, timeout_seconds=5, poll_seconds=1)
        assert next(statuses).state is RunState.RUNNING
        statuses.close()

    assert calls == 1
    assert clock.sleeps == []


@pytest.mark.parametrize(
    "response",
    [
        _response("UNKNOWN"),
        _response("RUNNING", run_id=OTHER_RUN_ID),
    ],
)
def test_watch_fails_closed_on_malformed_or_mismatched_status(
    response: dict[str, object],
    clock: _Clock,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=response, request=request)

    with _client(handler) as client, pytest.raises(ProtocolError):
        list(client.runs.watch(run_id=RUN_ID, timeout_seconds=5))

    assert clock.sleeps == []
