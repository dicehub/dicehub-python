from __future__ import annotations

from types import TracebackType

import httpx

from dicehub._core.defaults import DEFAULT_BASE_URL
from dicehub._core.graphql import GraphQLTransport
from dicehub._core.rest_v2 import (
    ApiProtocol,
    ProjectReads,
    validate_api_protocol,
    validate_project_reads,
)
from dicehub.api_keys.service import ApiKeysService
from dicehub.apps.service import AppsService
from dicehub.auth.models import IdentityMode
from dicehub.auth.service import AuthService
from dicehub.configs.service import ConfigsService
from dicehub.groups.service import GroupsService
from dicehub.projects.service import ProjectsService
from dicehub.resources.service import ResourcesService
from dicehub.runs.service import RunsService
from dicehub.storage.service import StorageService
from dicehub.teams.service import TeamsService
from dicehub.templates.service import TemplatesService
from dicehub.users.service import UsersService


class Client:
    """Synchronous dicehub client."""

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        api_key: str | None = None,
        session_cookie: str | None = None,
        project_reads: ProjectReads = "graphql",
        api_protocol: ApiProtocol = "graphql",
        timeout: float = 10.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        validate_project_reads(project_reads)
        validate_api_protocol(api_protocol)
        self._graphql = GraphQLTransport(
            base_url=base_url,
            api_key=api_key,
            session_cookie=session_cookie,
            timeout=timeout,
            transport=transport,
        )
        expected_identity_mode = (
            IdentityMode.API_KEY if api_key is not None else IdentityMode.SESSION
        )
        self.auth = AuthService(
            self._graphql,
            rest_api=self._graphql if api_protocol == "rest_v2" else None,
            expected_identity_mode=expected_identity_mode,
        )
        self.api_keys = ApiKeysService(
            self._graphql,
            rest_api=self._graphql if api_protocol == "rest_v2" else None,
            identity_mode=expected_identity_mode,
        )
        self.apps = AppsService(
            self._graphql, rest_api=self._graphql if api_protocol == "rest_v2" else None
        )
        self.configs = ConfigsService(
            self._graphql, rest_api=self._graphql if api_protocol == "rest_v2" else None
        )
        self.groups = GroupsService(
            self._graphql,
            rest_api=self._graphql if api_protocol == "rest_v2" else None,
            identity_mode=expected_identity_mode,
        )
        self.projects = ProjectsService(
            self._graphql,
            rest_api=self._graphql if api_protocol == "rest_v2" else None,
            rest=self._graphql if project_reads == "rest_v2" or api_protocol == "rest_v2" else None,
            identity_mode=expected_identity_mode,
        )
        self.resources = ResourcesService(
            self._graphql, rest_api=self._graphql if api_protocol == "rest_v2" else None
        )
        self.runs = RunsService(
            self._graphql, rest_api=self._graphql if api_protocol == "rest_v2" else None
        )
        self.storage = StorageService(self._graphql)
        self.teams = TeamsService(
            self._graphql, rest_api=self._graphql if api_protocol == "rest_v2" else None
        )
        self.templates = TemplatesService(
            self._graphql, rest_api=self._graphql if api_protocol == "rest_v2" else None
        )
        self.users = UsersService(
            self._graphql, rest_api=self._graphql if api_protocol == "rest_v2" else None
        )

    def close(self) -> None:
        self._graphql.close()

    def __enter__(self) -> Client:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
