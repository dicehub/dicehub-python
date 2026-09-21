from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import TypeVar

from pydantic import BaseModel

from dicehub._core.async_graphql import AsyncGraphQLExecutor
from dicehub._core.status import raise_for_status
from dicehub.api_keys._graphql import (
    CREATE_API_KEY_MUTATION,
    DELETE_API_KEY_MUTATION,
    GET_API_KEY_QUERY,
    LIST_API_KEY_PERMISSIONS_QUERY,
    LIST_API_KEYS_QUERY,
    UPDATE_API_KEY_MUTATION,
    CreateApiKeyData,
    DeleteApiKeyData,
    GetApiKeyData,
    ListApiKeyPermissionsData,
    ListApiKeysData,
    UpdateApiKeyData,
)
from dicehub.api_keys._validation import (
    validated_id,
    validated_name,
    validated_permissions,
    validated_validity_window,
)
from dicehub.api_keys.models import ApiKey, CreatedApiKey, NamespacePermission
from dicehub.api_keys.service import (
    _api_key_from_payload,
    _timestamp_variable,
    _unknown_mutation_outcome,
    _validated_response,
)
from dicehub.auth.models import IdentityMode
from dicehub.errors import (
    ConfigurationError,
    GraphQLError,
    HTTPError,
    MutationOutcomeUnknownError,
    ProtocolError,
    TransportError,
)

WireModelT = TypeVar("WireModelT", bound=BaseModel)
_AMBIGUOUS_MUTATION_ERRORS = (TransportError, HTTPError, GraphQLError, ProtocolError)
_API_KEY_LIST_PAGE_SIZE = 20
_MAX_API_KEY_NUMERIC_ID = 2**63 - 1
_MAX_LISTED_API_KEYS = 10_000
_MAX_API_KEY_LIST_REQUESTS = 501
_INVALID_API_KEY_LIST_MESSAGE = "dicehub returned an invalid API-key listing."


class AsyncApiKeysService:
    def __init__(
        self,
        graphql: AsyncGraphQLExecutor,
        *,
        identity_mode: IdentityMode | None = None,
    ) -> None:
        self._graphql = graphql
        self._identity_mode = identity_mode

    async def create(
        self,
        *,
        namespace_id: str,
        name: str,
        permissions: Sequence[NamespacePermission],
        not_before: datetime | None = None,
        expires_at: datetime | None = None,
    ) -> CreatedApiKey:
        self._require_session()
        permission_values = validated_permissions(permissions)
        not_before, expires_at = validated_validity_window(
            not_before,
            expires_at,
        )
        response = await self._execute_mutation(
            response_type=CreateApiKeyData,
            operation_name="CreateApiKey",
            query=CREATE_API_KEY_MUTATION,
            variables={
                "namespaceId": validated_id(namespace_id, "namespace ID"),
                "name": validated_name(name),
                "permissions": permission_values,
                "notBefore": _timestamp_variable(not_before),
                "expiresAt": _timestamp_variable(expires_at),
            },
        )
        payload = response.api_keys.create_api_key
        raise_for_status(payload.status)
        if payload.api_key is None:
            raise _unknown_mutation_outcome()
        metadata = _api_key_from_payload(payload.api_key)
        return CreatedApiKey(
            **metadata.model_dump(),
            value=payload.api_key.value,
        )

    async def list(self, *, namespace_id: str) -> tuple[ApiKey, ...]:
        self._require_session()
        valid_namespace_id = validated_id(namespace_id, "namespace ID")
        api_keys: list[ApiKey] = []
        seen_ids: set[str] = set()
        before_api_key_id: str | None = None
        previous_numeric_id: int | None = None

        for request_number in range(1, _MAX_API_KEY_LIST_REQUESTS + 1):
            result = await self._graphql.execute(
                operation_name="ListApiKeys",
                query=LIST_API_KEYS_QUERY,
                variables={
                    "namespaceId": valid_namespace_id,
                    "beforeApiKeyId": before_api_key_id,
                    "limit": _API_KEY_LIST_PAGE_SIZE,
                },
            )
            response = _validated_response(ListApiKeysData, result.data)
            payload = response.api_keys.list_api_keys
            raise_for_status(payload.status)
            if payload.api_keys is None:
                raise ProtocolError("dicehub returned a successful response without API keys.")

            page = payload.api_keys
            if len(page) > _API_KEY_LIST_PAGE_SIZE:
                raise ProtocolError(_INVALID_API_KEY_LIST_MESSAGE)
            if page and page[-1].api_key_id == before_api_key_id:
                raise ProtocolError(_INVALID_API_KEY_LIST_MESSAGE)

            page_models: list[ApiKey] = []
            for item in page:
                numeric_id = int(item.api_key_id)
                if (
                    numeric_id > _MAX_API_KEY_NUMERIC_ID
                    or item.api_key_id in seen_ids
                    or (previous_numeric_id is not None and numeric_id >= previous_numeric_id)
                ):
                    raise ProtocolError(_INVALID_API_KEY_LIST_MESSAGE)
                seen_ids.add(item.api_key_id)
                previous_numeric_id = numeric_id
                page_models.append(_api_key_from_payload(item))

            if len(api_keys) + len(page_models) > _MAX_LISTED_API_KEYS:
                raise ProtocolError(_INVALID_API_KEY_LIST_MESSAGE)
            api_keys.extend(page_models)

            if len(page) < _API_KEY_LIST_PAGE_SIZE:
                return tuple(api_keys)

            before_api_key_id = page[-1].api_key_id

            if request_number == _MAX_API_KEY_LIST_REQUESTS:
                raise ProtocolError(_INVALID_API_KEY_LIST_MESSAGE)

        raise ProtocolError(_INVALID_API_KEY_LIST_MESSAGE)  # pragma: no cover

    async def get(self, *, namespace_id: str, api_key_id: str) -> ApiKey | None:
        self._require_session()
        result = await self._graphql.execute(
            operation_name="GetApiKey",
            query=GET_API_KEY_QUERY,
            variables={
                "namespaceId": validated_id(namespace_id, "namespace ID"),
                "apiKeyId": validated_id(api_key_id, "API-key ID"),
            },
        )
        response = _validated_response(GetApiKeyData, result.data)
        payload = response.api_keys.get_api_key
        raise_for_status(payload.status)
        return None if payload.api_key is None else _api_key_from_payload(payload.api_key)

    async def list_permissions(self, *, namespace_id: str) -> tuple[NamespacePermission, ...]:
        self._require_session()
        result = await self._graphql.execute(
            operation_name="ListApiKeyPermissions",
            query=LIST_API_KEY_PERMISSIONS_QUERY,
            variables={"namespaceId": validated_id(namespace_id, "namespace ID")},
        )
        response = _validated_response(ListApiKeyPermissionsData, result.data)
        payload = response.api_keys.list_api_key_permissions
        raise_for_status(payload.status)
        return tuple(payload.permissions)

    async def update(
        self,
        *,
        namespace_id: str,
        api_key_id: str,
        name: str,
        permissions: Sequence[NamespacePermission] | None = None,
    ) -> ApiKey:
        self._require_session()
        response = await self._execute_mutation(
            response_type=UpdateApiKeyData,
            operation_name="UpdateApiKey",
            query=UPDATE_API_KEY_MUTATION,
            variables={
                "namespaceId": validated_id(namespace_id, "namespace ID"),
                "apiKeyId": validated_id(api_key_id, "API-key ID"),
                "name": validated_name(name),
                "permissions": (
                    None if permissions is None else validated_permissions(permissions)
                ),
            },
        )
        payload = response.api_keys.update_api_key
        raise_for_status(payload.status)
        if payload.api_key is None:
            raise _unknown_mutation_outcome()
        return _api_key_from_payload(payload.api_key)

    async def delete(self, *, api_key_id: str) -> None:
        self._require_session()
        response = await self._execute_mutation(
            response_type=DeleteApiKeyData,
            operation_name="DeleteApiKey",
            query=DELETE_API_KEY_MUTATION,
            variables={"apiKeyId": validated_id(api_key_id, "API-key ID")},
        )
        raise_for_status(response.api_keys.delete_api_key.status)

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

    def _require_session(self) -> None:
        if self._identity_mode is IdentityMode.API_KEY:
            raise ConfigurationError(
                "API-key administration requires session-cookie authentication."
            )
