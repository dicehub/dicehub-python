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
    ProjectMemberTeamPayload,
    ProjectMemberUserPayload,
    ProjectRolePayload,
    ProjectTeamMembershipPayload,
    ProjectUserMembershipPayload,
    RemoveProjectMemberData,
    UpdateProjectMemberData,
)
from dicehub.projects._validation import (
    validated_cursor,
    validated_enum,
    validated_id,
    validated_offset,
    validated_page_size,
    validated_role_name,
    validated_search_filter,
)
from dicehub.projects.models import (
    MembershipVisibility,
    ProjectMemberTeam,
    ProjectMemberUser,
    ProjectRole,
    ProjectTeamMembership,
    ProjectTeamMembershipPage,
    ProjectUserMembership,
    ProjectUserMembershipPage,
)

WireModelT = TypeVar("WireModelT", bound=BaseModel)
_AMBIGUOUS_MUTATION_ERRORS = (TransportError, HTTPError, GraphQLError, ProtocolError)


class _ProjectMembersMixin:
    _graphql: GraphQLExecutor

    def list_roles(self, *, project_id: str) -> tuple[ProjectRole, ...]:
        result = self._graphql.execute(
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

    def get_role_by_name(self, *, project_id: str, name: str) -> ProjectRole:
        valid_name = validated_role_name(name)
        matches = tuple(
            role for role in self.list_roles(project_id=project_id) if role.name == valid_name
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
        result = self._graphql.execute(
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

    def list_team_members(
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
        result = self._graphql.execute(
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

    def add_member(
        self,
        *,
        project_id: str,
        member_id: str,
        role_id: str,
        visibility: MembershipVisibility = MembershipVisibility.PRIVATE,
    ) -> None:
        response = self._execute_member_mutation(
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

    def update_member(
        self,
        *,
        project_id: str,
        member_id: str,
        role_id: str | None = None,
        visibility: MembershipVisibility | None = None,
    ) -> None:
        if role_id is None and visibility is None:
            raise ConfigurationError("Project member update must include at least one change.")
        response = self._execute_member_mutation(
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

    def remove_member(self, *, project_id: str, member_id: str) -> None:
        response = self._execute_member_mutation(
            response_type=RemoveProjectMemberData,
            operation_name="RemoveProjectMember",
            query=REMOVE_PROJECT_MEMBER_MUTATION,
            variables={
                "projectId": validated_id(project_id, "project ID"),
                "memberId": validated_id(member_id, "member ID"),
            },
        )
        raise_for_status(response.projects.remove_member.status)

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
    project_id: str,
    include_inherited: bool,
    deduplicate: bool | None,
    search_filter: str | None,
    offset: int,
    limit: int,
    cursor: str | None,
) -> dict[str, object]:
    if not isinstance(include_inherited, bool):
        raise ConfigurationError("Project membership inherited flag must be boolean.")
    if deduplicate is not None and not isinstance(deduplicate, bool):
        raise ConfigurationError("Project membership deduplicate flag must be boolean.")
    variables: dict[str, object] = {
        "projectId": validated_id(project_id, "project ID"),
        "includeInherited": include_inherited,
        "searchFilter": validated_search_filter(search_filter),
        "offset": float(validated_offset(offset)),
        "limit": float(validated_page_size(limit)),
        "cursor": validated_cursor(cursor),
    }
    if deduplicate is not None:
        variables["deduplicate"] = deduplicate
    return variables


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
        raise ProtocolError("dicehub returned an incompatible project membership response.")
    return response


def _role_from_payload(payload: ProjectRolePayload) -> ProjectRole:
    return ProjectRole(role_id=payload.role_id, name=payload.name)


def _user_from_payload(payload: ProjectMemberUserPayload) -> ProjectMemberUser:
    return ProjectMemberUser(
        user_id=payload.user_id,
        first_name=payload.first_name,
        last_name=payload.last_name,
        username=payload.username,
        avatar_url=payload.avatar_url,
    )


def _team_from_payload(payload: ProjectMemberTeamPayload) -> ProjectMemberTeam:
    return ProjectMemberTeam(
        team_id=payload.team_id,
        name=payload.name,
        route=payload.route,
        avatar_url=payload.avatar_url,
    )


def _user_membership_from_payload(
    payload: ProjectUserMembershipPayload,
) -> ProjectUserMembership:
    return ProjectUserMembership(
        membership_id=payload.membership_id,
        member_id=payload.member_id,
        namespace_id=payload.namespace_id,
        role_id=payload.role_id,
        visibility=MembershipVisibility(payload.visibility),
        inherited=payload.inherited,
        user=_user_from_payload(payload.user),
    )


def _team_membership_from_payload(
    payload: ProjectTeamMembershipPayload,
) -> ProjectTeamMembership:
    return ProjectTeamMembership(
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
        "The project membership mutation may have completed, but dicehub did not confirm its "
        "outcome.",
        request_id=request_id,
    )
