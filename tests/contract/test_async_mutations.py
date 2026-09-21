from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import httpx
import pytest

from dicehub import AsyncClient, MutationOutcomeUnknownError

RESOURCE_ID = "12345678-1234-5678-9234-567812345678"
RUN_ID = "12345678-1234-5678-9234-567812345679"
_STATUS = {"succeeded": True, "error": None}


@dataclass(frozen=True)
class _MutationCase:
    name: str
    call: Callable[[AsyncClient], Awaitable[None]]
    operation_name: str
    variables: dict[str, object]
    domain: str
    response_field: str


_MUTATION_CASES = (
    _MutationCase(
        name="api_keys",
        call=lambda client: client.api_keys.delete(api_key_id="91"),
        operation_name="DeleteApiKey",
        variables={"apiKeyId": "91"},
        domain="apiKeys",
        response_field="deleteApiKey",
    ),
    _MutationCase(
        name="apps",
        call=lambda client: client.apps.delete(app_id="101"),
        operation_name="DeleteApp",
        variables={"appId": "101"},
        domain="apps",
        response_field="deleteApp",
    ),
    _MutationCase(
        name="app_members",
        call=lambda client: client.apps.add_member(
            app_id="101",
            member_id="7",
            role_id="3",
        ),
        operation_name="AddAppMember",
        variables={
            "appId": "101",
            "memberId": "7",
            "roleId": "3",
            "visibility": "PRIVATE",
        },
        domain="apps",
        response_field="addMemberToApp",
    ),
    _MutationCase(
        name="configs",
        call=lambda client: client.configs.delete(config_id="301"),
        operation_name="DeleteConfig",
        variables={"configId": "301"},
        domain="configs",
        response_field="deleteConfig",
    ),
    _MutationCase(
        name="groups",
        call=lambda client: client.groups.delete(group_id="73"),
        operation_name="DeleteGroup",
        variables={"groupId": "73"},
        domain="groups",
        response_field="deleteGroup",
    ),
    _MutationCase(
        name="group_members",
        call=lambda client: client.groups.add_member(
            group_id="73",
            member_id="7",
            role_id="3",
        ),
        operation_name="AddGroupMember",
        variables={
            "groupId": "73",
            "memberId": "7",
            "roleId": "3",
            "visibility": "PRIVATE",
        },
        domain="groups",
        response_field="addMemberToGroup",
    ),
    _MutationCase(
        name="projects",
        call=lambda client: client.projects.delete(project_id="91"),
        operation_name="DeleteProject",
        variables={"projectId": "91"},
        domain="projects",
        response_field="deleteProject",
    ),
    _MutationCase(
        name="resources",
        call=lambda client: client.resources.delete(resource_id=RESOURCE_ID),
        operation_name="DeleteResource",
        variables={"resourceId": RESOURCE_ID},
        domain="resources",
        response_field="deleteResource",
    ),
    _MutationCase(
        name="runs",
        call=lambda client: client.runs.stop(run_id=RUN_ID),
        operation_name="StopRun",
        variables={"runId": RUN_ID},
        domain="runs",
        response_field="stopRun",
    ),
)


@pytest.mark.parametrize("case", _MUTATION_CASES, ids=lambda case: case.name)
def test_async_mutation_uses_fixed_contract_once(case: _MutationCase) -> None:
    request_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        payload = json.loads(request.content)
        assert request.headers["cookie"] == "_dicehub_session=test-session-secret"
        assert payload["operationName"] == case.operation_name
        assert payload["variables"] == case.variables
        assert case.response_field in payload["query"]
        return httpx.Response(
            200,
            json={
                "data": {
                    case.domain: {
                        case.response_field: {"status": _STATUS},
                    }
                }
            },
            request=request,
        )

    async def scenario() -> None:
        async with AsyncClient(
            base_url="https://dicehub.test",
            session_cookie="test-session-secret",
            transport=httpx.MockTransport(handler),
        ) as client:
            await case.call(client)

    asyncio.run(scenario())

    assert request_count == 1


def test_async_mutation_timeout_is_unknown_and_not_retried() -> None:
    request_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        raise httpx.ReadTimeout("sentinel transport details", request=request)

    async def scenario() -> MutationOutcomeUnknownError:
        async with AsyncClient(
            base_url="https://dicehub.test",
            api_key="test-api-key",
            transport=httpx.MockTransport(handler),
        ) as client:
            with pytest.raises(MutationOutcomeUnknownError) as captured:
                await client.configs.delete(config_id="301")
            return captured.value

    error = asyncio.run(scenario())

    assert request_count == 1
    assert error.retryable is False
    assert "sentinel" not in str(error)
    assert error.__context__ is None
    assert error.__cause__ is None
