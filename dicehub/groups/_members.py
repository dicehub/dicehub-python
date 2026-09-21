from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel, ValidationError

from dicehub._core.graphql import GraphQLExecutor
from dicehub._core.status import raise_for_status
from dicehub.errors import (
    ConfigurationError,
    GraphQLError,
    HTTPError,
    MutationOutcomeUnknownError,
    ProtocolError,
    SelectorResolutionError,
    TransportError,
)
from dicehub.groups._member_graphql import (
    ADD_GROUP_MEMBER_MUTATION,
    LIST_GROUP_ROLES_QUERY,
    LIST_GROUP_TEAM_MEMBERSHIPS_QUERY,
    LIST_GROUP_USER_MEMBERSHIPS_QUERY,
    REMOVE_GROUP_MEMBER_MUTATION,
    UPDATE_GROUP_MEMBER_MUTATION,
    AddGroupMemberData,
    GroupMemberTeamPayload,
    GroupMemberUserPayload,
    GroupRolePayload,
    GroupTeamMembershipPayload,
    GroupUserMembershipPayload,
    ListGroupRolesData,
    ListGroupTeamMembershipsData,
    ListGroupUserMembershipsData,
    RemoveGroupMemberData,
    UpdateGroupMemberData,
)
from dicehub.groups._validation import (
    validated_cursor,
    validated_enum,
    validated_id,
    validated_offset,
    validated_page_size,
    validated_role_name,
    validated_search_filter,
)
from dicehub.groups.models import (
    GroupMemberTeam,
    GroupMemberUser,
    GroupRole,
    GroupTeamMembership,
    GroupTeamMembershipPage,
    GroupUserMembership,
    GroupUserMembershipPage,
    MembershipVisibility,
)

WireModelT = TypeVar("WireModelT", bound=BaseModel)
_AMBIGUOUS_MUTATION_ERRORS = (TransportError, HTTPError, GraphQLError, ProtocolError)


class _GroupMembersMixin:
    _graphql: GraphQLExecutor

    def list_roles(self, *, group_id: str) -> tuple[GroupRole, ...]:
        result = self._graphql.execute(
            operation_name="ListGroupRoles",
            query=LIST_GROUP_ROLES_QUERY,
            variables={"groupId": validated_id(group_id, "group ID")},
        )
        response = _validated_response(ListGroupRolesData, result.data)
        payload = response.groups.list_roles
        raise_for_status(payload.status)
        if payload.roles is None:
            raise ProtocolError("dicehub returned a successful response without group roles.")
        return tuple(_role_from_payload(role) for role in payload.roles)

    def get_role_by_name(self, *, group_id: str, name: str) -> GroupRole:
        valid_name = validated_role_name(name)
        matches = tuple(
            role for role in self.list_roles(group_id=group_id) if role.name == valid_name
        )
        if len(matches) != 1:
            raise SelectorResolutionError(
                selector="role_name",
                reason="NOT_FOUND" if not matches else "AMBIGUOUS",
            )
        return matches[0]

    def list_user_members(
        self,
        *,
        group_id: str,
        include_inherited: bool = True,
        deduplicate: bool = False,
        search_filter: str | None = None,
        offset: int = 0,
        limit: int = 20,
        cursor: str | None = None,
    ) -> GroupUserMembershipPage:
        variables = _membership_list_variables(
            group_id=group_id,
            include_inherited=include_inherited,
            deduplicate=deduplicate,
            search_filter=search_filter,
            offset=offset,
            limit=limit,
            cursor=cursor,
        )
        result = self._graphql.execute(
            operation_name="ListGroupUserMemberships",
            query=LIST_GROUP_USER_MEMBERSHIPS_QUERY,
            variables=variables,
        )
        response = _validated_response(ListGroupUserMembershipsData, result.data)
        payload = response.groups.list_memberships
        raise_for_status(payload.status)
        if payload.memberships is None or payload.info is None:
            raise ProtocolError(
                "dicehub returned a successful response without a group user membership page."
            )
        return GroupUserMembershipPage(
            memberships=tuple(
                _user_membership_from_payload(membership) for membership in payload.memberships
            ),
            offset=int(payload.info.offset),
            count=int(payload.info.count),
            cursor=payload.info.cursor,
        )

    def list_team_members(
        self,
        *,
        group_id: str,
        include_inherited: bool = True,
        deduplicate: bool = False,
        search_filter: str | None = None,
        offset: int = 0,
        limit: int = 20,
        cursor: str | None = None,
    ) -> GroupTeamMembershipPage:
        variables = _membership_list_variables(
            group_id=group_id,
            include_inherited=include_inherited,
            deduplicate=deduplicate,
            search_filter=search_filter,
            offset=offset,
            limit=limit,
            cursor=cursor,
        )
        result = self._graphql.execute(
            operation_name="ListGroupTeamMemberships",
            query=LIST_GROUP_TEAM_MEMBERSHIPS_QUERY,
            variables=variables,
        )
        response = _validated_response(ListGroupTeamMembershipsData, result.data)
        payload = response.groups.list_memberships
        raise_for_status(payload.status)
        if payload.memberships is None or payload.info is None:
            raise ProtocolError(
                "dicehub returned a successful response without a group team membership page."
            )
        return GroupTeamMembershipPage(
            memberships=tuple(
                _team_membership_from_payload(membership) for membership in payload.memberships
            ),
            offset=int(payload.info.offset),
            count=int(payload.info.count),
            cursor=payload.info.cursor,
        )

    def add_member(
        self,
        *,
        group_id: str,
        member_id: str,
        role_id: str,
        visibility: MembershipVisibility = MembershipVisibility.PRIVATE,
    ) -> None:
        response = self._execute_member_mutation(
            response_type=AddGroupMemberData,
            operation_name="AddGroupMember",
            query=ADD_GROUP_MEMBER_MUTATION,
            variables={
                "groupId": validated_id(group_id, "group ID"),
                "memberId": validated_id(member_id, "member ID"),
                "roleId": validated_id(role_id, "role ID"),
                "visibility": validated_enum(
                    visibility,
                    MembershipVisibility,
                    "membership visibility",
                ).value,
            },
        )
        raise_for_status(response.groups.add_member.status)

    def update_member(
        self,
        *,
        group_id: str,
        member_id: str,
        role_id: str | None = None,
        visibility: MembershipVisibility | None = None,
    ) -> None:
        if role_id is None and visibility is None:
            raise ConfigurationError("Group member update must include at least one change.")
        response = self._execute_member_mutation(
            response_type=UpdateGroupMemberData,
            operation_name="UpdateGroupMember",
            query=UPDATE_GROUP_MEMBER_MUTATION,
            variables={
                "groupId": validated_id(group_id, "group ID"),
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
        raise_for_status(response.groups.update_member.status)

    def remove_member(self, *, group_id: str, member_id: str) -> None:
        response = self._execute_member_mutation(
            response_type=RemoveGroupMemberData,
            operation_name="RemoveGroupMember",
            query=REMOVE_GROUP_MEMBER_MUTATION,
            variables={
                "groupId": validated_id(group_id, "group ID"),
                "memberId": validated_id(member_id, "member ID"),
            },
        )
        raise_for_status(response.groups.remove_member.status)

    def _execute_member_mutation(
        self,
        *,
        response_type: type[WireModelT],
        operation_name: str,
        query: str,
        variables: dict[str, object],
    ) -> WireModelT:
        mapped_error: MutationOutcomeUnknownError | None = None
        try:
            result = self._graphql.execute(
                operation_name=operation_name,
                query=query,
                variables=variables,
            )
            return _validated_response(response_type, result.data)
        except _AMBIGUOUS_MUTATION_ERRORS as error:
            mapped_error = _unknown_mutation_outcome(request_id=error.request_id)
        assert mapped_error is not None
        raise mapped_error


def _membership_list_variables(
    *,
    group_id: str,
    include_inherited: bool,
    deduplicate: bool,
    search_filter: str | None,
    offset: int,
    limit: int,
    cursor: str | None,
) -> dict[str, object]:
    if not isinstance(include_inherited, bool) or not isinstance(deduplicate, bool):
        raise ConfigurationError("Group membership flags must be boolean values.")
    return {
        "groupId": validated_id(group_id, "group ID"),
        "includeInherited": include_inherited,
        "deduplicate": deduplicate,
        "searchFilter": validated_search_filter(search_filter),
        "offset": float(validated_offset(offset)),
        "limit": float(validated_page_size(limit)),
        "cursor": validated_cursor(cursor),
    }


def _validated_response(
    response_type: type[WireModelT],
    data: dict[str, object],
) -> WireModelT:
    response: WireModelT | None = None
    try:
        response = response_type.model_validate(data)
    except ValidationError:
        pass
    if response is None:
        raise ProtocolError("dicehub returned an incompatible group membership response.")
    return response


def _role_from_payload(payload: GroupRolePayload) -> GroupRole:
    return GroupRole(role_id=payload.role_id, name=payload.name)


def _user_from_payload(payload: GroupMemberUserPayload) -> GroupMemberUser:
    return GroupMemberUser(
        user_id=payload.user_id,
        first_name=payload.first_name,
        last_name=payload.last_name,
        username=payload.username,
        avatar_url=payload.avatar_url,
    )


def _team_from_payload(payload: GroupMemberTeamPayload) -> GroupMemberTeam:
    return GroupMemberTeam(
        team_id=payload.team_id,
        name=payload.name,
        route=payload.route,
        avatar_url=payload.avatar_url,
    )


def _user_membership_from_payload(
    payload: GroupUserMembershipPayload,
) -> GroupUserMembership:
    return GroupUserMembership(
        membership_id=payload.membership_id,
        member_id=payload.member_id,
        namespace_id=payload.namespace_id,
        role_id=payload.role_id,
        visibility=MembershipVisibility(payload.visibility),
        inherited=payload.inherited,
        user=_user_from_payload(payload.user),
    )


def _team_membership_from_payload(
    payload: GroupTeamMembershipPayload,
) -> GroupTeamMembership:
    return GroupTeamMembership(
        membership_id=payload.membership_id,
        member_id=payload.member_id,
        namespace_id=payload.namespace_id,
        role_id=payload.role_id,
        visibility=MembershipVisibility(payload.visibility),
        inherited=payload.inherited,
        team=_team_from_payload(payload.team),
    )


def _unknown_mutation_outcome(*, request_id: str | None = None) -> MutationOutcomeUnknownError:
    return MutationOutcomeUnknownError(
        "The group membership mutation may have completed, but dicehub did not confirm its "
        "outcome.",
        request_id=request_id,
    )
