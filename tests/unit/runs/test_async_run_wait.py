from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field

import httpx
import pytest

from dicehub import AsyncClient, RunState
from dicehub.runs import async_service as async_runs_service

RUN_ID = "12345678-1234-5678-9234-567812345678"


@dataclass
class _Clock:
    now: float = 0.0
    sleeps: list[float] = field(default_factory=list)

    def monotonic(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def _response(state: str, updated_at: str) -> dict[str, object]:
    return {
        "data": {
            "runs": {
                "getSingleRunById": {
                    "status": {"succeeded": True, "error": None},
                    "run": {
                        "runId": RUN_ID,
                        "state": state,
                        "executionStatus": None,
                        "error": "NONE",
                        "flags": [],
                        "updatedAt": updated_at,
                    },
                }
            }
        }
    }


def test_async_wait_preserves_deadlines_without_blocking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = _Clock()
    timeout_caps: list[float] = []
    states = iter(
        [
            ("RUNNING", "2026-08-11T10:11:12Z"),
            ("FINISHED", "2026-08-11T10:11:14Z"),
        ]
    )
    monkeypatch.setattr(async_runs_service, "monotonic", clock.monotonic)
    monkeypatch.setattr("dicehub.runs.async_service.asyncio.sleep", clock.sleep)

    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["operationName"] == "GetRunStatus"
        timeout_caps.append(request.extensions["timeout"]["read"])
        state, updated_at = next(states)
        return httpx.Response(200, json=_response(state, updated_at), request=request)

    async def scenario() -> None:
        async with AsyncClient(
            base_url="https://dicehub.test",
            api_key="test-api-key",
            transport=httpx.MockTransport(handler),
        ) as client:
            status = await client.runs.wait(
                run_id=RUN_ID,
                timeout_seconds=5,
                poll_seconds=2,
            )
            assert status.state is RunState.FINISHED

    asyncio.run(scenario())

    assert timeout_caps == [5, 3]
    assert clock.sleeps == [2]


def test_async_watch_can_close_before_another_poll(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = _Clock()
    calls = 0
    monkeypatch.setattr(async_runs_service, "monotonic", clock.monotonic)
    monkeypatch.setattr("dicehub.runs.async_service.asyncio.sleep", clock.sleep)

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            json=_response("RUNNING", "2026-08-11T10:11:12Z"),
            request=request,
        )

    async def scenario() -> None:
        async with AsyncClient(
            base_url="https://dicehub.test",
            api_key="test-api-key",
            transport=httpx.MockTransport(handler),
        ) as client:
            statuses = client.runs.watch(
                run_id=RUN_ID,
                timeout_seconds=5,
                poll_seconds=1,
            )
            assert (await anext(statuses)).state is RunState.RUNNING
            await statuses.aclose()

    asyncio.run(scenario())

    assert calls == 1
    assert clock.sleeps == []


def test_async_request_cancellation_propagates() -> None:
    entered = asyncio.Event()
    blocked = asyncio.Event()

    async def handler(request: httpx.Request) -> httpx.Response:
        entered.set()
        await blocked.wait()
        return httpx.Response(500, request=request)

    async def scenario() -> None:
        async with AsyncClient(
            base_url="https://dicehub.test",
            api_key="test-api-key",
            transport=httpx.MockTransport(handler),
        ) as client:
            task = asyncio.create_task(client.runs.status(run_id=RUN_ID))
            await entered.wait()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

    asyncio.run(scenario())
