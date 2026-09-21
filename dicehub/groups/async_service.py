from __future__ import annotations

import asyncio
import base64
from typing import BinaryIO, TypeVar

from pydantic import BaseModel

from dicehub._core.async_graphql import AsyncGraphQLExecutor
from dicehub._core.status import raise_for_status
from dicehub.auth.models import IdentityMode
from dicehub.errors import (
    ConfigurationError,
    GraphQLError,
    HTTPError,
    MutationOutcomeUnknownError,
    ProtocolError,
    TransportError,
)
from dicehub.groups._async_members import _AsyncGroupMembersMixin
from dicehub.groups._graphql import (
    CREATE_GROUP_MUTATION,
    DELETE_GROUP_MUTATION,
    GET_GROUP_BY_ROUTE_QUERY,
    GET_GROUP_QUERY,
    LIST_GROUPS_QUERY,
    MOVE_GROUP_MUTATION,
    UPDATE_GROUP_AVATAR_MUTATION,
    UPDATE_GROUP_MUTATION,
    CreateGroupData,
    DeleteGroupData,
    GetGroupByRouteData,
    GetGroupData,
    ListGroupsData,
    MoveGroupData,
    UpdateGroupAvatarData,
    UpdateGroupData,
)
from dicehub.groups._validation import (
    validated_avatar_png,
    validated_cursor,
    validated_description,
    validated_enum,
    validated_id,
    validated_name,
    validated_offset,
    validated_optional_id,
    validated_page_size,
    validated_route,
    validated_search_filter,
    validated_slug,
)
from dicehub.groups.models import GroupDetail, GroupOrderField, GroupPage, GroupVisibility
from dicehub.groups.service import (
    _group_detail_from_created_payload,
    _group_detail_from_single,
    _group_from_payload,
    _unknown_mutation_outcome,
    _validated_response,
)
from dicehub.projects.models import SortOrder

WireModelT = TypeVar("WireModelT", bound=BaseModel)
_AMBIGUOUS_MUTATION_ERRORS = (TransportError, HTTPError, GraphQLError, ProtocolError)


class AsyncGroupsService(_AsyncGroupMembersMixin):
    def __init__(
        self,
        graphql: AsyncGraphQLExecutor,
        *,
        identity_mode: IdentityMode | None = None,
    ) -> None:
        self._graphql = graphql
        self._identity_mode = identity_mode

    async def list(
        self,
        *,
        user_id: str | None = None,
        parent_id: str | None = None,
        search_filter: str | None = None,
        order_by: GroupOrderField = GroupOrderField.NAME,
        order: SortOrder = SortOrder.ASC,
        offset: int = 0,
        limit: int = 20,
        cursor: str | None = None,
    ) -> GroupPage:
        valid_order_by = validated_enum(order_by, GroupOrderField, "group order field")
        valid_order = validated_enum(order, SortOrder, "group sort order")
        result = await self._graphql.execute(
            operation_name="ListGroups",
            query=LIST_GROUPS_QUERY,
            variables={
                "userId": validated_optional_id(user_id, "user ID"),
                "parentId": validated_optional_id(parent_id, "parent group ID"),
                "searchFilter": validated_search_filter(search_filter),
                "orderBy": valid_order_by.value,
                "order": valid_order.value,
                "offset": float(validated_offset(offset)),
                "limit": float(validated_page_size(limit)),
                "cursor": validated_cursor(cursor),
            },
        )
        response = _validated_response(
            ListGroupsData,
            result.data,
            "dicehub returned an incompatible group response.",
        )
        payload = response.groups.list_groups
        raise_for_status(payload.status)
        if payload.groups is None or payload.info is None:
            raise ProtocolError("dicehub returned a successful response without a group page.")
        return GroupPage(
            groups=tuple(_group_from_payload(group) for group in payload.groups),
            offset=int(payload.info.offset),
            count=int(payload.info.count),
            cursor=payload.info.cursor,
        )

    async def get(self, *, group_id: str) -> GroupDetail:
        result = await self._graphql.execute(
            operation_name="GetGroup",
            query=GET_GROUP_QUERY,
            variables={"groupId": validated_id(group_id, "group ID")},
        )
        response = _validated_response(
            GetGroupData,
            result.data,
            "dicehub returned an incompatible group response.",
        )
        return _group_detail_from_single(response.groups.get_group)

    async def get_by_route(self, *, route: str) -> GroupDetail:
        result = await self._graphql.execute(
            operation_name="GetGroupByRoute",
            query=GET_GROUP_BY_ROUTE_QUERY,
            variables={"route": validated_route(route)},
        )
        response = _validated_response(
            GetGroupByRouteData,
            result.data,
            "dicehub returned an incompatible group response.",
        )
        return _group_detail_from_single(response.groups.get_group)

    async def create(
        self,
        *,
        name: str,
        slug: str,
        parent_id: str | None = None,
        description: str | None = None,
        visibility: GroupVisibility = GroupVisibility.PRIVATE,
    ) -> GroupDetail:
        if parent_id is None:
            self._require_session("Top-level group creation")
        response = await self._execute_mutation(
            response_type=CreateGroupData,
            operation_name="CreateGroup",
            query=CREATE_GROUP_MUTATION,
            variables={
                "name": validated_name(name),
                "slug": validated_slug(slug),
                "description": validated_description(description),
                "groupId": validated_optional_id(parent_id, "parent group ID"),
                "visibility": validated_enum(
                    visibility,
                    GroupVisibility,
                    "group visibility",
                ).value,
            },
        )
        payload = response.groups.create_group
        raise_for_status(payload.status)
        if payload.group is None:
            raise _unknown_mutation_outcome()
        return _group_detail_from_created_payload(payload.group)

    async def update(
        self,
        *,
        group_id: str,
        name: str | None = None,
        slug: str | None = None,
        description: str | None = None,
        visibility: GroupVisibility | None = None,
    ) -> None:
        if name is None and slug is None and description is None and visibility is None:
            raise ConfigurationError("Group update must include at least one change.")
        response = await self._execute_mutation(
            response_type=UpdateGroupData,
            operation_name="UpdateGroup",
            query=UPDATE_GROUP_MUTATION,
            variables={
                "groupId": validated_id(group_id, "group ID"),
                "name": validated_name(name) if name is not None else None,
                "slug": validated_slug(slug) if slug is not None else None,
                "description": validated_description(description),
                "visibility": (
                    validated_enum(visibility, GroupVisibility, "group visibility").value
                    if visibility is not None
                    else None
                ),
            },
        )
        raise_for_status(response.groups.update_group.status)

    async def set_avatar(self, *, group_id: str, source: BinaryIO) -> None:
        valid_group_id = validated_id(group_id, "group ID")
        content = await asyncio.to_thread(validated_avatar_png, source)
        encoded = base64.b64encode(content).decode("ascii")
        response = await self._execute_mutation(
            response_type=UpdateGroupAvatarData,
            operation_name="UpdateGroupAvatar",
            query=UPDATE_GROUP_AVATAR_MUTATION,
            variables={
                "groupId": valid_group_id,
                "avatar": f"data:image/png;base64,{encoded}",
            },
        )
        raise_for_status(response.groups.update_group.status)

    async def clear_avatar(self, *, group_id: str) -> None:
        response = await self._execute_mutation(
            response_type=UpdateGroupAvatarData,
            operation_name="UpdateGroupAvatar",
            query=UPDATE_GROUP_AVATAR_MUTATION,
            variables={
                "groupId": validated_id(group_id, "group ID"),
                "avatar": "",
            },
        )
        raise_for_status(response.groups.update_group.status)

    async def delete(self, *, group_id: str) -> None:
        response = await self._execute_mutation(
            response_type=DeleteGroupData,
            operation_name="DeleteGroup",
            query=DELETE_GROUP_MUTATION,
            variables={"groupId": validated_id(group_id, "group ID")},
        )
        raise_for_status(response.groups.delete_group.status)

    async def move(self, *, group_id: str, to_group_id: str) -> None:
        self._require_session("Group move")
        response = await self._execute_mutation(
            response_type=MoveGroupData,
            operation_name="MoveGroup",
            query=MOVE_GROUP_MUTATION,
            variables={
                "groupId": validated_id(group_id, "group ID"),
                "toGroupId": validated_id(to_group_id, "target group ID"),
            },
        )
        raise_for_status(response.groups.move_group.status)

    def _require_session(self, operation: str) -> None:
        if self._identity_mode is not IdentityMode.SESSION:
            raise ConfigurationError(f"{operation} requires session-cookie authentication.")

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
            return _validated_response(
                response_type,
                result.data,
                "dicehub returned an incompatible group mutation response.",
            )
        except _AMBIGUOUS_MUTATION_ERRORS as error:
            mapped_error = _unknown_mutation_outcome(request_id=error.request_id)
        assert mapped_error is not None
        raise mapped_error
