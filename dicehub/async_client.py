from __future__ import annotations

from types import TracebackType

import httpx

from dicehub._core.async_graphql import AsyncGraphQLTransport
from dicehub._core.defaults import DEFAULT_BASE_URL
from dicehub._core.rest_v2 import (
    ApiProtocol,
    ProjectReads,
    validate_api_protocol,
    validate_project_reads,
)
from dicehub.api_keys.async_service import AsyncApiKeysService
from dicehub.apps.async_service import AsyncAppsService
from dicehub.auth.async_service import AsyncAuthService
from dicehub.auth.models import IdentityMode
from dicehub.configs.async_service import AsyncConfigsService
from dicehub.groups.async_service import AsyncGroupsService
from dicehub.projects.async_service import AsyncProjectsService
from dicehub.resources.async_service import AsyncResourcesService
from dicehub.runs.async_service import AsyncRunsService
from dicehub.storage.async_service import AsyncStorageService
from dicehub.teams.async_service import AsyncTeamsService
from dicehub.templates.async_service import AsyncTemplatesService
from dicehub.users.async_service import AsyncUsersService


class AsyncClient:
    """Asynchronous dicehub client."""

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        api_key: str | None = None,
        session_cookie: str | None = None,
        project_reads: ProjectReads = "graphql",
        api_protocol: ApiProtocol = "graphql",
        timeout: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        validate_project_reads(project_reads)
        validate_api_protocol(api_protocol)
        self._graphql = AsyncGraphQLTransport(
            base_url=base_url,
            api_key=api_key,
            session_cookie=session_cookie,
            timeout=timeout,
            transport=transport,
        )
        expected_identity_mode = (
            IdentityMode.API_KEY if api_key is not None else IdentityMode.SESSION
        )
        self.auth = AsyncAuthService(
            self._graphql,
            rest_api=self._graphql if api_protocol == "rest_v2" else None,
            expected_identity_mode=expected_identity_mode,
        )
        self.api_keys = AsyncApiKeysService(
            self._graphql,
            rest_api=self._graphql if api_protocol == "rest_v2" else None,
            identity_mode=expected_identity_mode,
        )
        self.apps = AsyncAppsService(
            self._graphql, rest_api=self._graphql if api_protocol == "rest_v2" else None
        )
        self.configs = AsyncConfigsService(
            self._graphql, rest_api=self._graphql if api_protocol == "rest_v2" else None
        )
        self.groups = AsyncGroupsService(
            self._graphql,
            rest_api=self._graphql if api_protocol == "rest_v2" else None,
            identity_mode=expected_identity_mode,
        )
        self.projects = AsyncProjectsService(
            self._graphql,
            rest_api=self._graphql if api_protocol == "rest_v2" else None,
            rest=self._graphql if project_reads == "rest_v2" or api_protocol == "rest_v2" else None,
            identity_mode=expected_identity_mode,
        )
        self.resources = AsyncResourcesService(
            self._graphql, rest_api=self._graphql if api_protocol == "rest_v2" else None
        )
        self.runs = AsyncRunsService(
            self._graphql, rest_api=self._graphql if api_protocol == "rest_v2" else None
        )
        self.storage = AsyncStorageService(self._graphql)
        self.teams = AsyncTeamsService(
            self._graphql, rest_api=self._graphql if api_protocol == "rest_v2" else None
        )
        self.templates = AsyncTemplatesService(
            self._graphql, rest_api=self._graphql if api_protocol == "rest_v2" else None
        )
        self.users = AsyncUsersService(
            self._graphql, rest_api=self._graphql if api_protocol == "rest_v2" else None
        )

    async def aclose(self) -> None:
        await self._graphql.aclose()

    async def __aenter__(self) -> AsyncClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()
