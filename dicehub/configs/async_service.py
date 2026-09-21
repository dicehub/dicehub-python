from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Sequence
from typing import BinaryIO, TypeVar

from pydantic import BaseModel

from dicehub._core.async_graphql import AsyncGraphQLExecutor
from dicehub._core.status import raise_for_status
from dicehub.configs._graphql import (
    CREATE_CONFIG_MUTATION,
    DELETE_CONFIG_CONTENT_MUTATION,
    DELETE_CONFIG_MUTATION,
    GET_CONFIG_QUERY,
    GET_CONFIG_TEXT_QUERY,
    IMPORT_CONFIG_GEOMETRY_MUTATION,
    LIST_CONFIG_CONTENT_QUERY,
    LIST_CONFIGS_QUERY,
    SET_CONFIG_TEXT_MUTATION,
    SET_CONFIG_VALUES_MUTATION,
    UPDATE_CONFIG_MUTATION,
    CreateConfigData,
    DeleteConfigContentData,
    DeleteConfigData,
    GetConfigData,
    GetConfigTextData,
    ImportConfigGeometryData,
    ListConfigContentData,
    ListConfigsData,
    SetConfigTextData,
    SetConfigValuesData,
    UpdateConfigData,
)
from dicehub.configs._validation import (
    MAX_FILE_BYTES,
    validated_config_value_updates,
    validated_content_path,
    validated_cursor,
    validated_description,
    validated_file_limit,
    validated_geometry_filename,
    validated_id,
    validated_name,
    validated_offset,
    validated_page_size,
    validated_search_filter,
    validated_text_content,
    validated_yaml_path,
)
from dicehub.configs.models import (
    Config,
    ConfigContentArea,
    ConfigContentEntry,
    ConfigContentPage,
    ConfigContentType,
    ConfigPage,
    ConfigValueUpdate,
    GeometryImportRuns,
)
from dicehub.configs.service import (
    _config_from_payload,
    _file_endpoint,
    _run_status_from_payload,
    _unknown_mutation_outcome,
    _validated_response,
)
from dicehub.errors import (
    ConfigurationError,
    GraphQLError,
    HTTPError,
    MutationOutcomeUnknownError,
    ProtocolError,
    TransportError,
)
from dicehub.projects.models import SortOrder

WireModelT = TypeVar("WireModelT", bound=BaseModel)
_AMBIGUOUS_MUTATION_ERRORS = (TransportError, HTTPError, GraphQLError, ProtocolError)
_MAX_TEXT_RESPONSE_BYTES = 13 * 1024 * 1024


class AsyncConfigsService:
    def __init__(self, graphql: AsyncGraphQLExecutor) -> None:
        self._graphql = graphql

    async def list(
        self,
        *,
        app_id: str,
        search_filter: str | None = None,
        order: SortOrder = SortOrder.ASC,
        offset: int = 0,
        limit: int = 20,
        cursor: str | None = None,
    ) -> ConfigPage:
        if not isinstance(order, SortOrder):
            raise ConfigurationError("Config sort order is invalid.")
        result = await self._graphql.execute(
            operation_name="ListConfigs",
            query=LIST_CONFIGS_QUERY,
            variables={
                "appId": validated_id(app_id, "app ID"),
                "searchFilter": validated_search_filter(search_filter),
                "order": order.value,
                "offset": float(validated_offset(offset)),
                "limit": float(validated_page_size(limit)),
                "cursor": validated_cursor(cursor),
            },
        )
        response = _validated_response(ListConfigsData, result.data)
        payload = response.configs.list_configs
        raise_for_status(payload.status)
        if payload.configs is None or payload.info is None:
            raise ProtocolError("dicehub returned a successful response without a config page.")
        return ConfigPage(
            configs=tuple(_config_from_payload(config) for config in payload.configs),
            offset=int(payload.info.offset),
            count=int(payload.info.count),
            cursor=payload.info.cursor,
        )

    async def get(self, *, config_id: str) -> Config:
        result = await self._graphql.execute(
            operation_name="GetConfig",
            query=GET_CONFIG_QUERY,
            variables={"configId": validated_id(config_id, "config ID")},
        )
        response = _validated_response(GetConfigData, result.data)
        payload = response.configs.get_config
        raise_for_status(payload.status)
        if payload.config is None:
            raise ProtocolError("dicehub returned a successful response without a config.")
        return _config_from_payload(payload.config)

    async def create(
        self,
        *,
        app_id: str,
        source_config_id: str | None = None,
        name: str | None = None,
        description: str | None = None,
    ) -> Config:
        response = await self._execute_mutation(
            response_type=CreateConfigData,
            operation_name="CreateConfig",
            query=CREATE_CONFIG_MUTATION,
            variables={
                "appId": validated_id(app_id, "app ID"),
                "sourceConfigId": (
                    validated_id(source_config_id, "source config ID")
                    if source_config_id is not None
                    else None
                ),
                "name": validated_name(name),
                "description": validated_description(description),
            },
        )
        payload = response.configs.create_config
        raise_for_status(payload.status)
        if payload.config is None:
            raise _unknown_mutation_outcome()
        return _config_from_payload(payload.config)

    async def update(
        self,
        *,
        config_id: str,
        name: str | None = None,
        description: str | None = None,
    ) -> None:
        if name is None and description is None:
            raise ConfigurationError("Config update requires a name or description.")
        response = await self._execute_mutation(
            response_type=UpdateConfigData,
            operation_name="UpdateConfig",
            query=UPDATE_CONFIG_MUTATION,
            variables={
                "configId": validated_id(config_id, "config ID"),
                "name": validated_name(name),
                "description": validated_description(description),
            },
        )
        raise_for_status(response.configs.update_config.status)

    async def delete(self, *, config_id: str) -> None:
        response = await self._execute_mutation(
            response_type=DeleteConfigData,
            operation_name="DeleteConfig",
            query=DELETE_CONFIG_MUTATION,
            variables={"configId": validated_id(config_id, "config ID")},
        )
        raise_for_status(response.configs.delete_config.status)

    async def import_geometry(self, *, config_id: str, filename: str) -> GeometryImportRuns:
        """Start the server-owned conversion and ordered geometry-setup runs."""

        response = await self._execute_mutation(
            response_type=ImportConfigGeometryData,
            operation_name="ImportConfigGeometry",
            query=IMPORT_CONFIG_GEOMETRY_MUTATION,
            variables={
                "configId": validated_id(config_id, "config ID"),
                "filename": validated_geometry_filename(filename),
            },
        )
        payload = response.configs.import_config_geometry
        raise_for_status(payload.status)
        if payload.conversion_run is None:
            raise _unknown_mutation_outcome()
        return GeometryImportRuns(
            conversion_run=_run_status_from_payload(payload.conversion_run),
            setup_run=(
                _run_status_from_payload(payload.setup_run)
                if payload.setup_run is not None
                else None
            ),
        )

    async def list_content(
        self,
        *,
        config_id: str,
        area: ConfigContentArea,
        path: str = "",
        recursive: bool = False,
        order: SortOrder = SortOrder.ASC,
        offset: int = 0,
        limit: int = 20,
        cursor: str | None = None,
    ) -> ConfigContentPage:
        if not isinstance(area, ConfigContentArea):
            raise ConfigurationError("Config content area is invalid.")
        if not isinstance(recursive, bool):
            raise ConfigurationError("Config recursive flag is invalid.")
        if not isinstance(order, SortOrder):
            raise ConfigurationError("Config sort order is invalid.")
        result = await self._graphql.execute(
            operation_name="ListConfigContent",
            query=LIST_CONFIG_CONTENT_QUERY,
            variables={
                "configId": validated_id(config_id, "config ID"),
                "area": area.value,
                "path": validated_content_path(path, allow_empty=True) or None,
                "deep": recursive,
                "order": order.value,
                "offset": float(validated_offset(offset)),
                "limit": float(validated_page_size(limit)),
                "cursor": validated_cursor(cursor),
            },
        )
        response = _validated_response(ListConfigContentData, result.data)
        payload = response.configs.list_config_content
        raise_for_status(payload.status)
        if payload.entries is None or payload.info is None:
            raise ProtocolError("dicehub returned a successful response without config content.")
        return ConfigContentPage(
            entries=tuple(
                ConfigContentEntry(
                    path=entry.path,
                    resource_type=ConfigContentType(entry.resource_type),
                )
                for entry in payload.entries
            ),
            offset=int(payload.info.offset),
            count=int(payload.info.count),
            cursor=payload.info.cursor,
        )

    async def get_text(self, *, config_id: str, path: str) -> str:
        result = await self._graphql.execute(
            operation_name="GetConfigText",
            query=GET_CONFIG_TEXT_QUERY,
            variables={
                "configId": validated_id(config_id, "config ID"),
                "path": validated_content_path(path),
            },
            max_response_bytes=_MAX_TEXT_RESPONSE_BYTES,
        )
        response = _validated_response(GetConfigTextData, result.data)
        payload = response.configs.get_config_text
        raise_for_status(payload.status)
        if payload.content is None:
            raise ProtocolError("dicehub returned a successful response without config text.")
        return payload.content

    async def set_text(self, *, config_id: str, path: str, content: str) -> None:
        response = await self._execute_mutation(
            response_type=SetConfigTextData,
            operation_name="SetConfigText",
            query=SET_CONFIG_TEXT_MUTATION,
            variables={
                "configId": validated_id(config_id, "config ID"),
                "path": validated_content_path(path),
                "content": validated_text_content(content),
            },
        )
        raise_for_status(response.configs.set_config_text.status)

    async def set_values(
        self,
        *,
        config_id: str,
        path: str,
        updates: Sequence[ConfigValueUpdate],
    ) -> None:
        response = await self._execute_mutation(
            response_type=SetConfigValuesData,
            operation_name="SetConfigValues",
            query=SET_CONFIG_VALUES_MUTATION,
            variables={
                "configId": validated_id(config_id, "config ID"),
                "path": validated_yaml_path(path),
                "updates": validated_config_value_updates(updates),
            },
        )
        raise_for_status(response.configs.set_config_values.status)

    async def delete_content(
        self,
        *,
        config_id: str,
        area: ConfigContentArea,
        path: str,
    ) -> None:
        if not isinstance(area, ConfigContentArea):
            raise ConfigurationError("Config content area is invalid.")
        response = await self._execute_mutation(
            response_type=DeleteConfigContentData,
            operation_name="DeleteConfigContent",
            query=DELETE_CONFIG_CONTENT_MUTATION,
            variables={
                "configId": validated_id(config_id, "config ID"),
                "area": area.value,
                "path": validated_content_path(path),
            },
        )
        raise_for_status(response.configs.delete_config_content.status)

    async def upload_file(
        self,
        *,
        config_id: str,
        path: str,
        source: BinaryIO,
        max_bytes: int = MAX_FILE_BYTES,
    ) -> None:
        endpoint = _file_endpoint(config_id, path)
        limit = validated_file_limit(max_bytes)
        if not callable(getattr(source, "read", None)):
            raise ConfigurationError("Config file source must be readable.")
        mapped_error: MutationOutcomeUnknownError | None = None
        try:
            await self._graphql.upload_binary(
                path=endpoint,
                chunks=_bounded_file_chunks(source, limit),
            )
        except _AMBIGUOUS_MUTATION_ERRORS as error:
            mapped_error = _unknown_mutation_outcome(request_id=error.request_id)
        if mapped_error is not None:
            raise mapped_error

    async def download_file(
        self,
        *,
        config_id: str,
        path: str,
        destination: BinaryIO,
        max_bytes: int = MAX_FILE_BYTES,
    ) -> int:
        if not callable(getattr(destination, "write", None)):
            raise ConfigurationError("Config file destination must be writable.")
        return await self._graphql.download_binary(
            path=_file_endpoint(config_id, path),
            destination=destination,
            max_bytes=validated_file_limit(max_bytes),
        )

    async def _execute_mutation(
        self,
        *,
        response_type: type[WireModelT],
        operation_name: str,
        query: str,
        variables: dict[str, object],
    ) -> WireModelT:
        mapped_error: MutationOutcomeUnknownError | None = None
        try:
            result = await self._graphql.execute(
                operation_name=operation_name,
                query=query,
                variables=variables,
            )
            return _validated_response(response_type, result.data)
        except _AMBIGUOUS_MUTATION_ERRORS as error:
            mapped_error = _unknown_mutation_outcome(request_id=error.request_id)
        assert mapped_error is not None
        raise mapped_error


async def _bounded_file_chunks(source: BinaryIO, max_bytes: int) -> AsyncIterator[bytes]:
    total = 0
    while True:
        chunk = await asyncio.to_thread(source.read, 64 * 1024)
        if not isinstance(chunk, bytes):
            raise ConfigurationError("Config file source must return bytes.")
        if not chunk:
            return
        total += len(chunk)
        if total > max_bytes:
            raise ConfigurationError("Config file exceeds the configured upload limit.")
        yield chunk
