from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel, ValidationError

from dicehub._core.graphql import GraphQLExecutor
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
from dicehub.projects._graphql import (
    CREATE_PROJECT_MUTATION,
    DELETE_PROJECT_MUTATION,
    GET_PROJECT_BY_ROUTE_QUERY,
    GET_PROJECT_QUERY,
    LIST_PROJECTS_QUERY,
    MOVE_PROJECT_MUTATION,
    UPDATE_PROJECT_MUTATION,
    CreateProjectData,
    DeleteProjectData,
    GetProjectByRouteData,
    GetProjectData,
    ListProjectsData,
    MoveProjectData,
    ProjectDetailPayload,
    ProjectPayload,
    SingleProjectPayload,
    UpdateProjectData,
)
from dicehub.projects._members import _ProjectMembersMixin
from dicehub.projects._validation import (
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
from dicehub.projects.models import (
    Project,
    ProjectDetail,
    ProjectOrderField,
    ProjectPage,
    ProjectVisibility,
    SortOrder,
)

WireModelT = TypeVar("WireModelT", bound=BaseModel)
_AMBIGUOUS_MUTATION_ERRORS = (TransportError, HTTPError, GraphQLError, ProtocolError)


class ProjectsService(_ProjectMembersMixin):
    def __init__(
        self,
        graphql: GraphQLExecutor,
        *,
        identity_mode: IdentityMode | None = None,
    ) -> None:
        self._graphql = graphql
        self._identity_mode = identity_mode

    def list(
        self,
        *,
        user_id: str | None = None,
        group_id: str | None = None,
        search_filter: str | None = None,
        order_by: ProjectOrderField = ProjectOrderField.NAME,
        order: SortOrder = SortOrder.ASC,
        offset: int = 0,
        limit: int = 20,
        cursor: str | None = None,
    ) -> ProjectPage:
        valid_order_by = validated_enum(order_by, ProjectOrderField, "project order field")
        valid_order = validated_enum(order, SortOrder, "project sort order")
        result = self._graphql.execute(
            operation_name="ListProjects",
            query=LIST_PROJECTS_QUERY,
            variables={
                "userId": validated_optional_id(user_id, "user ID"),
                "groupId": validated_optional_id(group_id, "group ID"),
                "searchFilter": validated_search_filter(search_filter),
                "orderBy": valid_order_by.value,
                "order": valid_order.value,
                "offset": float(validated_offset(offset)),
                "limit": float(validated_page_size(limit)),
                "cursor": validated_cursor(cursor),
            },
        )
        response = _validated_response(
            ListProjectsData,
            result.data,
            "dicehub returned an incompatible project response.",
        )

        payload = response.projects.list_projects
        raise_for_status(payload.status)
        if payload.projects is None or payload.info is None:
            raise ProtocolError("dicehub returned a successful response without a project page.")

        return ProjectPage(
            projects=tuple(_project_from_payload(project) for project in payload.projects),
            offset=int(payload.info.offset),
            count=int(payload.info.count),
            cursor=payload.info.cursor,
        )

    def get(self, *, project_id: str) -> ProjectDetail:
        result = self._graphql.execute(
            operation_name="GetProject",
            query=GET_PROJECT_QUERY,
            variables={"projectId": validated_id(project_id, "project ID")},
        )
        response = _validated_response(
            GetProjectData,
            result.data,
            "dicehub returned an incompatible project response.",
        )
        return _project_detail_from_single(response.projects.get_project)

    def get_by_route(self, *, route: str) -> ProjectDetail:
        result = self._graphql.execute(
            operation_name="GetProjectByRoute",
            query=GET_PROJECT_BY_ROUTE_QUERY,
            variables={"route": validated_route(route)},
        )
        response = _validated_response(
            GetProjectByRouteData,
            result.data,
            "dicehub returned an incompatible project response.",
        )
        return _project_detail_from_single(response.projects.get_project)

    def create(
        self,
        *,
        name: str,
        slug: str,
        group_id: str | None = None,
        description: str | None = None,
        visibility: ProjectVisibility = ProjectVisibility.PRIVATE,
    ) -> ProjectDetail:
        variables: dict[str, object] = {
            "name": validated_name(name),
            "slug": validated_slug(slug),
            "description": validated_description(description),
            "groupId": validated_optional_id(group_id, "group ID"),
            "visibility": validated_enum(visibility, ProjectVisibility, "project visibility").value,
        }
        response = self._execute_mutation(
            response_type=CreateProjectData,
            operation_name="CreateProject",
            query=CREATE_PROJECT_MUTATION,
            variables=variables,
        )
        payload = response.projects.create_project
        raise_for_status(payload.status)
        if payload.project is None:
            raise _unknown_mutation_outcome()
        return _project_detail_from_payload(payload.project)

    def update(
        self,
        *,
        project_id: str,
        name: str | None = None,
        slug: str | None = None,
        description: str | None = None,
        visibility: ProjectVisibility | None = None,
    ) -> None:
        if name is None and slug is None and description is None and visibility is None:
            raise ConfigurationError("Project update must include at least one change.")
        variables: dict[str, object] = {
            "projectId": validated_id(project_id, "project ID"),
            "name": validated_name(name) if name is not None else None,
            "slug": validated_slug(slug) if slug is not None else None,
            "description": validated_description(description),
            "visibility": (
                validated_enum(visibility, ProjectVisibility, "project visibility").value
                if visibility is not None
                else None
            ),
        }
        response = self._execute_mutation(
            response_type=UpdateProjectData,
            operation_name="UpdateProject",
            query=UPDATE_PROJECT_MUTATION,
            variables=variables,
        )
        raise_for_status(response.projects.update_project.status)

    def move(self, *, project_id: str, to_group_id: str) -> None:
        self._require_session()
        response = self._execute_mutation(
            response_type=MoveProjectData,
            operation_name="MoveProject",
            query=MOVE_PROJECT_MUTATION,
            variables={
                "projectId": validated_id(project_id, "project ID"),
                "toGroupId": validated_id(to_group_id, "target group ID"),
            },
        )
        raise_for_status(response.projects.move_project.status)

    def delete(self, *, project_id: str) -> None:
        response = self._execute_mutation(
            response_type=DeleteProjectData,
            operation_name="DeleteProject",
            query=DELETE_PROJECT_MUTATION,
            variables={"projectId": validated_id(project_id, "project ID")},
        )
        raise_for_status(response.projects.delete_project.status)

    def _require_session(self) -> None:
        if self._identity_mode is not IdentityMode.SESSION:
            raise ConfigurationError("Project move requires session-cookie authentication.")

    def _execute_mutation(
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
            return _validated_response(
                response_type,
                result.data,
                "dicehub returned an incompatible project mutation response.",
            )
        except _AMBIGUOUS_MUTATION_ERRORS as error:
            mapped_error = _unknown_mutation_outcome(request_id=error.request_id)
        assert mapped_error is not None
        raise mapped_error


def _validated_response(
    response_type: type[WireModelT],
    data: dict[str, object],
    message: str,
) -> WireModelT:
    response: WireModelT | None = None
    try:
        response = response_type.model_validate(data)
    except ValidationError:
        pass
    if response is None:
        raise ProtocolError(message)
    return response


def _project_from_payload(payload: ProjectPayload) -> Project:
    return Project(
        project_id=payload.project_id,
        group_id=payload.group_id,
        name=payload.name,
        display_route=payload.display_route,
        route=payload.route,
        visibility=ProjectVisibility(payload.visibility),
    )


def _project_detail_from_payload(payload: ProjectDetailPayload) -> ProjectDetail:
    return ProjectDetail(
        **_project_from_payload(payload).model_dump(),
        description=payload.description,
        avatar_url=payload.avatar_url,
    )


def _project_detail_from_single(payload: SingleProjectPayload) -> ProjectDetail:
    raise_for_status(payload.status)
    if payload.project is None:
        raise ProtocolError("dicehub returned a successful response without a project.")
    return _project_detail_from_payload(payload.project)


def _unknown_mutation_outcome(*, request_id: str | None = None) -> MutationOutcomeUnknownError:
    return MutationOutcomeUnknownError(
        "The project mutation may have completed, but dicehub did not confirm its outcome.",
        request_id=request_id,
    )
