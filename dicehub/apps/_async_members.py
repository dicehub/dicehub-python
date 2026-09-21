from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

from dicehub._core.async_graphql import AsyncGraphQLExecutor
from dicehub._core.status import raise_for_status
from dicehub.apps._member_graphql import (
    ADD_APP_MEMBER_MUTATION,
    LIST_APP_ROLES_QUERY,
    LIST_APP_TEAM_MEMBERSHIPS_QUERY,
    LIST_APP_USER_MEMBERSHIPS_QUERY,
    REMOVE_APP_MEMBER_MUTATION,
    UPDATE_APP_MEMBER_MUTATION,
    AddAppMemberData,
    ListAppRolesData,
    ListAppTeamMembershipsData,
    ListAppUserMembershipsData,
    RemoveAppMemberData,
    UpdateAppMemberData,
)
from dicehub.apps._members import (
    _membership_list_variables,
    _role_from_payload,
    _team_membership_from_payload,
    _unknown_mutation_outcome,
    _user_membership_from_payload,
    _validated_response,
)
from dicehub.apps._validation import validated_enum, validated_id, validated_role_name
from dicehub.apps.models import (
    AppRole,
    AppTeamMembershipPage,
    AppUserMembershipPage,
    MembershipVisibility,
)
from dicehub.errors import (
    ConfigurationError,
    GraphQLError,
    HTTPError,
    MutationOutcomeUnknownError,
    ProtocolError,
    SelectorResolutionError,
    TransportError,
)

WireModelT = TypeVar("WireModelT", bound=BaseModel)
_AMBIGUOUS_MUTATION_ERRORS = (TransportError, HTTPError, GraphQLError, ProtocolError)


class _AsyncAppMembersMixin:
    _graphql: AsyncGraphQLExecutor

    async def list_roles(self, *, app_id: str) -> tuple[AppRole, ...]:
        result = await self._graphql.execute(
            operation_name="ListAppRoles",
            query=LIST_APP_ROLES_QUERY,
            variables={"appId": validated_id(app_id, "app ID")},
        )
        response = _validated_response(ListAppRolesData, result.data)
        payload = response.apps.list_roles
        raise_for_status(payload.status)
        if payload.roles is None:
            raise ProtocolError("dicehub returned a successful response without app roles.")
        return tuple(_role_from_payload(role) for role in payload.roles)

    async def get_role_by_name(self, *, app_id: str, name: str) -> AppRole:
        valid_name = validated_role_name(name)
        roles = await self.list_roles(app_id=app_id)
        matches = tuple(role for role in roles if role.name == valid_name)
        if len(matches) != 1:
            raise SelectorResolutionError(
                selector="role_name",
                reason="NOT_FOUND" if not matches else "AMBIGUOUS",
            )
        return matches[0]

    async def list_user_members(
        self,
        *,
        app_id: str,
        include_inherited: bool = True,
        search_filter: str | None = None,
        offset: int = 0,
        limit: int = 20,
        cursor: str | None = None,
    ) -> AppUserMembershipPage:
        variables = _membership_list_variables(
            app_id=app_id,
            include_inherited=include_inherited,
            deduplicate=None,
            search_filter=search_filter,
            offset=offset,
            limit=limit,
            cursor=cursor,
        )
        result = await self._graphql.execute(
            operation_name="ListAppUserMemberships",
            query=LIST_APP_USER_MEMBERSHIPS_QUERY,
            variables=variables,
        )
        response = _validated_response(ListAppUserMembershipsData, result.data)
        payload = response.apps.list_memberships
        raise_for_status(payload.status)
        if payload.memberships is None or payload.info is None:
            raise ProtocolError(
                "dicehub returned a successful response without an app user membership page."
            )
        return AppUserMembershipPage(
            memberships=tuple(
                _user_membership_from_payload(membership) for membership in payload.memberships
            ),
            offset=int(payload.info.offset),
            count=int(payload.info.count),
            cursor=payload.info.cursor,
        )

    async def list_team_members(
        self,
        *,
        app_id: str,
        include_inherited: bool = True,
        deduplicate: bool = False,
        search_filter: str | None = None,
        offset: int = 0,
        limit: int = 20,
        cursor: str | None = None,
    ) -> AppTeamMembershipPage:
        variables = _membership_list_variables(
            app_id=app_id,
            include_inherited=include_inherited,
            deduplicate=deduplicate,
            search_filter=search_filter,
            offset=offset,
            limit=limit,
            cursor=cursor,
        )
        result = await self._graphql.execute(
            operation_name="ListAppTeamMemberships",
            query=LIST_APP_TEAM_MEMBERSHIPS_QUERY,
            variables=variables,
        )
        response = _validated_response(ListAppTeamMembershipsData, result.data)
        payload = response.apps.list_memberships
        raise_for_status(payload.status)
        if payload.memberships is None or payload.info is None:
            raise ProtocolError(
                "dicehub returned a successful response without an app team membership page."
            )
        return AppTeamMembershipPage(
            memberships=tuple(
                _team_membership_from_payload(membership) for membership in payload.memberships
            ),
            offset=int(payload.info.offset),
            count=int(payload.info.count),
            cursor=payload.info.cursor,
        )

    async def add_member(
        self,
        *,
        app_id: str,
        member_id: str,
        role_id: str,
        visibility: MembershipVisibility = MembershipVisibility.PRIVATE,
    ) -> None:
        response = await self._execute_member_mutation(
            response_type=AddAppMemberData,
            operation_name="AddAppMember",
            query=ADD_APP_MEMBER_MUTATION,
            variables={
                "appId": validated_id(app_id, "app ID"),
                "memberId": validated_id(member_id, "member ID"),
                "roleId": validated_id(role_id, "role ID"),
                "visibility": validated_enum(
                    visibility,
                    MembershipVisibility,
                    "membership visibility",
                ).value,
            },
        )
        raise_for_status(response.apps.add_member.status)

    async def update_member(
        self,
        *,
        app_id: str,
        member_id: str,
        role_id: str | None = None,
        visibility: MembershipVisibility | None = None,
    ) -> None:
        if role_id is None and visibility is None:
            raise ConfigurationError("App member update must include at least one change.")
        response = await self._execute_member_mutation(
            response_type=UpdateAppMemberData,
            operation_name="UpdateAppMember",
            query=UPDATE_APP_MEMBER_MUTATION,
            variables={
                "appId": validated_id(app_id, "app ID"),
                "memberId": validated_id(member_id, "member ID"),
                "roleId": validated_id(role_id, "role ID") if role_id is not None else None,
                "visibility": (
                    validated_enum(
                        visibility,
                        MembershipVisibility,
                        "membership visibility",
                    ).value
                    if visibility is not None
                    else None
                ),
            },
        )
        raise_for_status(response.apps.update_member.status)

    async def remove_member(self, *, app_id: str, member_id: str) -> None:
        response = await self._execute_member_mutation(
            response_type=RemoveAppMemberData,
            operation_name="RemoveAppMember",
            query=REMOVE_APP_MEMBER_MUTATION,
            variables={
                "appId": validated_id(app_id, "app ID"),
                "memberId": validated_id(member_id, "member ID"),
            },
        )
        raise_for_status(response.apps.remove_member.status)

    async def _execute_member_mutation(
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
            mapped_error = _unknown_mutation_outcome(
                app_id=str(variables["appId"]),
                member_id=str(variables["memberId"]),
                request_id=error.request_id,
            )
        assert mapped_error is not None
        raise mapped_error
