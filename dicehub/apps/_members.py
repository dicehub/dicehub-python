from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel, ValidationError

from dicehub._core.graphql import GraphQLExecutor
from dicehub._core.status import raise_for_status
from dicehub.apps._member_graphql import (
    ADD_APP_MEMBER_MUTATION,
    LIST_APP_ROLES_QUERY,
    LIST_APP_TEAM_MEMBERSHIPS_QUERY,
    LIST_APP_USER_MEMBERSHIPS_QUERY,
    REMOVE_APP_MEMBER_MUTATION,
    UPDATE_APP_MEMBER_MUTATION,
    AddAppMemberData,
    AppMemberTeamPayload,
    AppMemberUserPayload,
    AppRolePayload,
    AppTeamMembershipPayload,
    AppUserMembershipPayload,
    ListAppRolesData,
    ListAppTeamMembershipsData,
    ListAppUserMembershipsData,
    RemoveAppMemberData,
    UpdateAppMemberData,
)
from dicehub.apps._validation import (
    validated_cursor,
    validated_enum,
    validated_id,
    validated_offset,
    validated_page_size,
    validated_role_name,
    validated_search_filter,
)
from dicehub.apps.models import (
    AppMemberTeam,
    AppMemberUser,
    AppRole,
    AppTeamMembership,
    AppTeamMembershipPage,
    AppUserMembership,
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


class _AppMembersMixin:
    _graphql: GraphQLExecutor

    def list_roles(self, *, app_id: str) -> tuple[AppRole, ...]:
        result = self._graphql.execute(
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

    def get_role_by_name(self, *, app_id: str, name: str) -> AppRole:
        valid_name = validated_role_name(name)
        matches = tuple(role for role in self.list_roles(app_id=app_id) if role.name == valid_name)
        if len(matches) != 1:
            raise SelectorResolutionError(
                selector="role_name",
                reason="NOT_FOUND" if not matches else "AMBIGUOUS",
            )
        return matches[0]

    def list_user_members(
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
        result = self._graphql.execute(
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

    def list_team_members(
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
        result = self._graphql.execute(
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

    def add_member(
        self,
        *,
        app_id: str,
        member_id: str,
        role_id: str,
        visibility: MembershipVisibility = MembershipVisibility.PRIVATE,
    ) -> None:
        response = self._execute_member_mutation(
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

    def update_member(
        self,
        *,
        app_id: str,
        member_id: str,
        role_id: str | None = None,
        visibility: MembershipVisibility | None = None,
    ) -> None:
        if role_id is None and visibility is None:
            raise ConfigurationError("App member update must include at least one change.")
        response = self._execute_member_mutation(
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

    def remove_member(self, *, app_id: str, member_id: str) -> None:
        response = self._execute_member_mutation(
            response_type=RemoveAppMemberData,
            operation_name="RemoveAppMember",
            query=REMOVE_APP_MEMBER_MUTATION,
            variables={
                "appId": validated_id(app_id, "app ID"),
                "memberId": validated_id(member_id, "member ID"),
            },
        )
        raise_for_status(response.apps.remove_member.status)

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
            mapped_error = _unknown_mutation_outcome(
                app_id=str(variables["appId"]),
                member_id=str(variables["memberId"]),
                request_id=error.request_id,
            )
        assert mapped_error is not None
        raise mapped_error


def _membership_list_variables(
    *,
    app_id: str,
    include_inherited: bool,
    deduplicate: bool | None,
    search_filter: str | None,
    offset: int,
    limit: int,
    cursor: str | None,
) -> dict[str, object]:
    if not isinstance(include_inherited, bool):
        raise ConfigurationError("App membership inherited flag must be boolean.")
    if deduplicate is not None and not isinstance(deduplicate, bool):
        raise ConfigurationError("App membership deduplicate flag must be boolean.")
    variables: dict[str, object] = {
        "appId": validated_id(app_id, "app ID"),
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
        raise ProtocolError("dicehub returned an incompatible app membership response.")
    return response


def _role_from_payload(payload: AppRolePayload) -> AppRole:
    return AppRole(role_id=payload.role_id, name=payload.name)


def _user_from_payload(payload: AppMemberUserPayload) -> AppMemberUser:
    return AppMemberUser(
        user_id=payload.user_id,
        first_name=payload.first_name,
        last_name=payload.last_name,
        username=payload.username,
        avatar_url=payload.avatar_url,
    )


def _team_from_payload(payload: AppMemberTeamPayload) -> AppMemberTeam:
    return AppMemberTeam(
        team_id=payload.team_id,
        name=payload.name,
        route=payload.route,
        avatar_url=payload.avatar_url,
    )


def _user_membership_from_payload(
    payload: AppUserMembershipPayload,
) -> AppUserMembership:
    return AppUserMembership(
        membership_id=payload.membership_id,
        member_id=payload.member_id,
        namespace_id=payload.namespace_id,
        role_id=payload.role_id,
        visibility=MembershipVisibility(payload.visibility),
        inherited=payload.inherited,
        user=_user_from_payload(payload.user),
    )


def _team_membership_from_payload(
    payload: AppTeamMembershipPayload,
) -> AppTeamMembership:
    return AppTeamMembership(
        membership_id=payload.membership_id,
        member_id=payload.member_id,
        namespace_id=payload.namespace_id,
        role_id=payload.role_id,
        visibility=MembershipVisibility(payload.visibility),
        inherited=payload.inherited,
        team=_team_from_payload(payload.team),
    )


def _unknown_mutation_outcome(
    *,
    app_id: str,
    member_id: str,
    request_id: str | None = None,
) -> MutationOutcomeUnknownError:
    return MutationOutcomeUnknownError(
        "The app membership mutation may have completed, but dicehub did not confirm its outcome. "
        f"Reconcile app ID {app_id} and member ID {member_id} before another mutation.",
        request_id=request_id,
    )
