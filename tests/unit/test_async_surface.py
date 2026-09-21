from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any

from dicehub.api_keys import ApiKeysService, AsyncApiKeysService
from dicehub.apps import AppsService, AsyncAppsService
from dicehub.auth import AsyncAuthService, AuthService
from dicehub.configs import AsyncConfigsService, ConfigsService
from dicehub.groups import AsyncGroupsService, GroupsService
from dicehub.projects import AsyncProjectsService, ProjectsService
from dicehub.resources import AsyncResourcesService, ResourcesService
from dicehub.runs import AsyncRunsService, RunsService
from dicehub.storage import AsyncStorageService, StorageService
from dicehub.teams import AsyncTeamsService, TeamsService
from dicehub.templates import AsyncTemplatesService, TemplatesService
from dicehub.users import AsyncUsersService, UsersService

_SERVICE_PAIRS = (
    (AuthService, AsyncAuthService),
    (ApiKeysService, AsyncApiKeysService),
    (AppsService, AsyncAppsService),
    (ConfigsService, AsyncConfigsService),
    (GroupsService, AsyncGroupsService),
    (ProjectsService, AsyncProjectsService),
    (ResourcesService, AsyncResourcesService),
    (RunsService, AsyncRunsService),
    (StorageService, AsyncStorageService),
    (TeamsService, AsyncTeamsService),
    (TemplatesService, AsyncTemplatesService),
    (UsersService, AsyncUsersService),
)


def _public_methods(service: type[object]) -> dict[str, Callable[..., Any]]:
    return {
        name: method
        for name, method in inspect.getmembers(service, inspect.isfunction)
        if not name.startswith("_")
    }


def test_async_services_match_the_complete_sync_surface() -> None:
    for sync_service, async_service in _SERVICE_PAIRS:
        sync_methods = _public_methods(sync_service)
        async_methods = _public_methods(async_service)
        assert async_methods.keys() == sync_methods.keys(), async_service.__name__

        for name, sync_method in sync_methods.items():
            async_method = async_methods[name]
            sync_signature = inspect.signature(sync_method)
            async_signature = inspect.signature(async_method)
            assert async_signature.parameters == sync_signature.parameters, (
                f"{async_service.__name__}.{name}"
            )
            if async_service is not AsyncRunsService or name != "watch":
                assert async_signature.return_annotation == sync_signature.return_annotation
            assert inspect.iscoroutinefunction(async_method) is (
                async_service is not AsyncRunsService or name != "watch"
            ), f"{async_service.__name__}.{name}"
