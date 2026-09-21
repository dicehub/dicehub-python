from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel, ValidationError

from dicehub._core.graphql import GraphQLExecutor
from dicehub._core.status import raise_for_status
from dicehub.apps._graphql import (
    CREATE_APP_MUTATION,
    DELETE_APP_MUTATION,
    GET_APP_BY_ROUTE_QUERY,
    GET_APP_QUERY,
    LIST_APPS_QUERY,
    UPDATE_APP_MUTATION,
    AppDetailPayload,
    AppPayload,
    CreateAppData,
    DeleteAppData,
    GetAppByRouteData,
    GetAppData,
    ListAppsData,
    SingleAppPayload,
    UpdateAppData,
)
from dicehub.apps._members import _AppMembersMixin
from dicehub.apps._validation import (
    validated_cursor,
    validated_description,
    validated_enum,
    validated_id,
    validated_name,
    validated_offset,
    validated_optional_bool,
    validated_page_size,
    validated_route,
    validated_search_filter,
)
from dicehub.apps.models import App, AppDetail, AppOrderField, AppPage, AppType, AppVisibility
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


class AppsService(_AppMembersMixin):
    def __init__(self, graphql: GraphQLExecutor) -> None:
        self._graphql = graphql

    def list(
        self,
        *,
        project_id: str,
        search_filter: str | None = None,
        order_by: AppOrderField = AppOrderField.NAME,
        order: SortOrder = SortOrder.ASC,
        offset: int = 0,
        limit: int = 20,
        cursor: str | None = None,
        is_published: bool | None = None,
    ) -> AppPage:
        valid_order_by = validated_enum(order_by, AppOrderField, "app order field")
        valid_order = validated_enum(order, SortOrder, "app sort order")
        result = self._graphql.execute(
            operation_name="ListApps",
            query=LIST_APPS_QUERY,
            variables={
                "projectId": validated_id(project_id, "project ID"),
                "searchFilter": validated_search_filter(search_filter),
                "orderBy": valid_order_by.value,
                "order": valid_order.value,
                "offset": float(validated_offset(offset)),
                "limit": float(validated_page_size(limit)),
                "cursor": validated_cursor(cursor),
                "isPublished": validated_optional_bool(is_published, "publication filter"),
            },
        )
        response = _validated_response(ListAppsData, result.data)
        payload = response.apps.list_apps
        raise_for_status(payload.status)
        if payload.apps is None or payload.info is None:
            raise ProtocolError("dicehub returned a successful response without an app page.")
        return AppPage(
            apps=tuple(_app_from_payload(app) for app in payload.apps),
            offset=int(payload.info.offset),
            count=int(payload.info.count),
            cursor=payload.info.cursor,
        )

    def get(self, *, app_id: str) -> AppDetail:
        result = self._graphql.execute(
            operation_name="GetApp",
            query=GET_APP_QUERY,
            variables={"appId": validated_id(app_id, "app ID")},
        )
        response = _validated_response(GetAppData, result.data)
        return _app_detail_from_single(response.apps.get_app)

    def get_by_route(self, *, route: str) -> AppDetail:
        result = self._graphql.execute(
            operation_name="GetAppByRoute",
            query=GET_APP_BY_ROUTE_QUERY,
            variables={"route": validated_route(route)},
        )
        response = _validated_response(GetAppByRouteData, result.data)
        return _app_detail_from_single(response.apps.get_app)

    def create(
        self,
        *,
        project_id: str,
        template_id: str,
        name: str,
        description: str | None = None,
    ) -> AppDetail:
        response = self._execute_mutation(
            response_type=CreateAppData,
            operation_name="CreateApp",
            query=CREATE_APP_MUTATION,
            variables={
                "projectId": validated_id(project_id, "project ID"),
                "templateId": validated_id(template_id, "template ID"),
                "name": validated_name(name),
                "description": validated_description(description),
            },
        )
        payload = response.apps.create_app
        raise_for_status(payload.status)
        if payload.app is None:
            raise _unknown_mutation_outcome()
        return _app_detail_from_payload(payload.app)

    def update(
        self,
        *,
        app_id: str,
        name: str | None = None,
        description: str | None = None,
    ) -> None:
        if name is None and description is None:
            raise ConfigurationError("App update must include at least one change.")
        response = self._execute_mutation(
            response_type=UpdateAppData,
            operation_name="UpdateApp",
            query=UPDATE_APP_MUTATION,
            variables={
                "appId": validated_id(app_id, "app ID"),
                "name": validated_name(name) if name is not None else None,
                "description": validated_description(description),
            },
        )
        raise_for_status(response.apps.update_app.status)

    def delete(self, *, app_id: str) -> None:
        response = self._execute_mutation(
            response_type=DeleteAppData,
            operation_name="DeleteApp",
            query=DELETE_APP_MUTATION,
            variables={"appId": validated_id(app_id, "app ID")},
        )
        raise_for_status(response.apps.delete_app.status)

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
            return _validated_response(response_type, result.data)
        except _AMBIGUOUS_MUTATION_ERRORS as error:
            mapped_error = _unknown_mutation_outcome(request_id=error.request_id)
        assert mapped_error is not None
        raise mapped_error


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
        raise ProtocolError("dicehub returned an incompatible app response.")
    return response


def _app_from_payload(payload: AppPayload) -> App:
    return App(
        app_id=payload.app_id,
        project_id=payload.project_id,
        name=payload.name,
        display_route=payload.display_route,
        route=payload.route,
        visibility=AppVisibility(payload.visibility) if payload.visibility is not None else None,
        app_type=AppType(payload.app_type) if payload.app_type is not None else None,
    )


def _app_detail_from_payload(payload: AppDetailPayload) -> AppDetail:
    return AppDetail(
        **_app_from_payload(payload).model_dump(),
        description=payload.description,
        template_id=payload.template_id,
        template_name=payload.template_name,
        template_version=payload.template_version,
        template_slug=payload.template_slug,
        icon_path=payload.icon_path,
        preview_url=payload.preview_url,
    )


def _app_detail_from_single(payload: SingleAppPayload) -> AppDetail:
    raise_for_status(payload.status)
    if payload.app is None:
        raise ProtocolError("dicehub returned a successful response without an app.")
    return _app_detail_from_payload(payload.app)


def _unknown_mutation_outcome(*, request_id: str | None = None) -> MutationOutcomeUnknownError:
    return MutationOutcomeUnknownError(
        "The app mutation may have completed, but dicehub did not confirm its outcome.",
        request_id=request_id,
    )
