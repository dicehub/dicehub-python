from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

from dicehub._core.async_graphql import AsyncGraphQLExecutor
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
from dicehub.projects._member_graphql import (
    ADD_PROJECT_MEMBER_MUTATION,
    LIST_PROJECT_ROLES_QUERY,
    LIST_PROJECT_TEAM_MEMBERSHIPS_QUERY,
    LIST_PROJECT_USER_MEMBERSHIPS_QUERY,
    REMOVE_PROJECT_MEMBER_MUTATION,
    UPDATE_PROJECT_MEMBER_MUTATION,
    AddProjectMemberData,
    ListProjectRolesData,
    ListProjectTeamMembershipsData,
    ListProjectUserMembershipsData,
    RemoveProjectMemberData,
    UpdateProjectMemberData,
)
from dicehub.projects._members import (
    _membership_list_variables,
    _role_from_payload,
    _team_membership_from_payload,
    _unknown_mutation_outcome,
    _user_membership_from_payload,
    _validated_response,
)
from dicehub.projects._validation import validated_enum, validated_id, validated_role_name
from dicehub.projects.models import (
    MembershipVisibility,
    ProjectRole,
    ProjectTeamMembershipPage,
    ProjectUserMembershipPage,
)

WireModelT = TypeVar("WireModelT", bound=BaseModel)
_AMBIGUOUS_MUTATION_ERRORS = (TransportError, HTTPError, GraphQLError, ProtocolError)


class _AsyncProjectMembersMixin:
    _graphql: AsyncGraphQLExecutor

    async def list_roles(self, *, project_id: str) -> tuple[ProjectRole, ...]:
        result = await self._graphql.execute(
            operation_name="ListProjectRoles",
            query=LIST_PROJECT_ROLES_QUERY,
            variables={"projectId": validated_id(project_id, "project ID")},
        )
        response = _validated_response(ListProjectRolesData, result.data)
        payload = response.projects.list_roles
        raise_for_status(payload.status)
        if payload.roles is None:
            raise ProtocolError("dicehub returned a successful response without project roles.")
        return tuple(_role_from_payload(role) for role in payload.roles)

    async def get_role_by_name(self, *, project_id: str, name: str) -> ProjectRole:
        valid_name = validated_role_name(name)
        roles = await self.list_roles(project_id=project_id)
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
        project_id: str,
        include_inherited: bool = True,
        search_filter: str | None = None,
        offset: int = 0,
        limit: int = 20,
        cursor: str | None = None,
    ) -> ProjectUserMembershipPage:
        variables = _membership_list_variables(
            project_id=project_id,
            include_inherited=include_inherited,
            deduplicate=None,
            search_filter=search_filter,
            offset=offset,
            limit=limit,
            cursor=cursor,
        )
        result = await self._graphql.execute(
            operation_name="ListProjectUserMemberships",
            query=LIST_PROJECT_USER_MEMBERSHIPS_QUERY,
            variables=variables,
        )
        response = _validated_response(ListProjectUserMembershipsData, result.data)
        payload = response.projects.list_memberships
        raise_for_status(payload.status)
        if payload.memberships is None or payload.info is None:
            raise ProtocolError(
                "dicehub returned a successful response without a project user membership page."
            )
        return ProjectUserMembershipPage(
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
        project_id: str,
        include_inherited: bool = True,
        deduplicate: bool = False,
        search_filter: str | None = None,
        offset: int = 0,
        limit: int = 20,
        cursor: str | None = None,
    ) -> ProjectTeamMembershipPage:
        variables = _membership_list_variables(
            project_id=project_id,
            include_inherited=include_inherited,
            deduplicate=deduplicate,
            search_filter=search_filter,
            offset=offset,
            limit=limit,
            cursor=cursor,
        )
        result = await self._graphql.execute(
            operation_name="ListProjectTeamMemberships",
            query=LIST_PROJECT_TEAM_MEMBERSHIPS_QUERY,
            variables=variables,
        )
        response = _validated_response(ListProjectTeamMembershipsData, result.data)
        payload = response.projects.list_memberships
        raise_for_status(payload.status)
        if payload.memberships is None or payload.info is None:
            raise ProtocolError(
                "dicehub returned a successful response without a project team membership page."
            )
        return ProjectTeamMembershipPage(
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
        project_id: str,
        member_id: str,
        role_id: str,
        visibility: MembershipVisibility = MembershipVisibility.PRIVATE,
    ) -> None:
        response = await self._execute_member_mutation(
            response_type=AddProjectMemberData,
            operation_name="AddProjectMember",
            query=ADD_PROJECT_MEMBER_MUTATION,
            variables={
                "projectId": validated_id(project_id, "project ID"),
                "memberId": validated_id(member_id, "member ID"),
                "roleId": validated_id(role_id, "role ID"),
                "visibility": validated_enum(
                    visibility,
                    MembershipVisibility,
                    "membership visibility",
                ).value,
            },
        )
        raise_for_status(response.projects.add_member.status)

    async def update_member(
        self,
        *,
        project_id: str,
        member_id: str,
        role_id: str | None = None,
        visibility: MembershipVisibility | None = None,
    ) -> None:
        if role_id is None and visibility is None:
            raise ConfigurationError("Project member update must include at least one change.")
        response = await self._execute_member_mutation(
            response_type=UpdateProjectMemberData,
            operation_name="UpdateProjectMember",
            query=UPDATE_PROJECT_MEMBER_MUTATION,
            variables={
                "projectId": validated_id(project_id, "project ID"),
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
        raise_for_status(response.projects.update_member.status)

    async def remove_member(self, *, project_id: str, member_id: str) -> None:
        response = await self._execute_member_mutation(
            response_type=RemoveProjectMemberData,
            operation_name="RemoveProjectMember",
            query=REMOVE_PROJECT_MEMBER_MUTATION,
            variables={
                "projectId": validated_id(project_id, "project ID"),
                "memberId": validated_id(member_id, "member ID"),
            },
        )
        raise_for_status(response.projects.remove_member.status)

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
            mapped_error = _unknown_mutation_outcome(request_id=error.request_id)
        assert mapped_error is not None
        raise mapped_error
