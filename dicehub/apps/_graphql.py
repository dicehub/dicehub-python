from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from dicehub._core.status import ResponseStatus

LIST_APPS_QUERY = """
query ListApps(
  $projectId: String!
  $searchFilter: String
  $orderBy: String!
  $order: OrderTypeEnum!
  $offset: Float!
  $limit: Float!
  $cursor: String
  $isPublished: Boolean
) {
  apps {
    listApps(
      projectId: $projectId
      searchFilter: $searchFilter
      orderBy: $orderBy
      order: $order
      offset: $offset
      limit: $limit
      ahead: 1
      cursor: $cursor
      isPublished: $isPublished
    ) {
      status { succeeded error }
      info { offset count cursor }
      apps {
        appId
        projectId
        name
        displayRoute
        route
        visibility
        appType
      }
    }
  }
}
"""

GET_APP_QUERY = """
query GetApp($appId: String!) {
  apps {
    getAppById(appId: $appId) {
      status { succeeded error }
      app {
        appId
        projectId
        name
        displayRoute
        route
        visibility
        appType
        description
        templateId
        templateName
        templateVersion
        templateSlug
        iconPath
        previewUrl
      }
    }
  }
}
"""

GET_APP_BY_ROUTE_QUERY = """
query GetAppByRoute($route: String!) {
  apps {
    getAppByRoute(route: $route) {
      app {
        appId
        projectId
        name
        displayRoute
        route
        visibility
        appType
        description
        templateId
        templateName
        templateVersion
        templateSlug
        iconPath
        previewUrl
      }
      status { succeeded error }
    }
  }
}
"""

CREATE_APP_MUTATION = """
mutation CreateApp(
  $projectId: String!
  $templateId: String!
  $name: String!
  $description: String
) {
  apps {
    createApp(
      projectId: $projectId
      templateId: $templateId
      name: $name
      description: $description
    ) {
      status { succeeded error }
      app {
        appId
        projectId
        name
        displayRoute
        route
        visibility
        appType
        description
        templateId
        templateName
        templateVersion
        templateSlug
        iconPath
        previewUrl
      }
    }
  }
}
"""

UPDATE_APP_MUTATION = """
mutation UpdateApp(
  $appId: String!
  $name: String
  $description: String
) {
  apps {
    updateApp(
      appId: $appId
      name: $name
      description: $description
    ) {
      status { succeeded error }
    }
  }
}
"""

DELETE_APP_MUTATION = """
mutation DeleteApp($appId: String!) {
  apps {
    deleteApp(appId: $appId) {
      status { succeeded error }
    }
  }
}
"""


def _valid_positive_id(value: str) -> bool:
    return (
        0 < len(value) <= 256 and value.isascii() and value.isdigit() and not value.startswith("0")
    )


class AppPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    app_id: str = Field(alias="appId", min_length=1, max_length=256)
    project_id: str = Field(alias="projectId", min_length=1, max_length=256)
    name: str = Field(min_length=1, max_length=128)
    display_route: str = Field(alias="displayRoute", min_length=1, max_length=16_384)
    route: str | None = Field(default=None, max_length=16_384)
    visibility: Literal["INTERNAL", "PRIVATE", "PUBLIC"] | None
    app_type: Literal["REGULAR", "MODEL", "PREVIEW"] | None = Field(alias="appType")

    @field_validator("app_id", "project_id")
    @classmethod
    def validate_ids(cls, value: str) -> str:
        if not _valid_positive_id(value):
            raise ValueError("invalid app namespace ID")
        return value


class AppDetailPayload(AppPayload):
    description: str | None
    template_id: str | None = Field(alias="templateId", default=None, max_length=256)
    template_name: str | None = Field(alias="templateName", default=None, max_length=128)
    template_version: str | None = Field(alias="templateVersion", default=None, max_length=256)
    template_slug: str | None = Field(alias="templateSlug", default=None, max_length=256)
    icon_path: str | None = Field(alias="iconPath", default=None, max_length=16_384)
    preview_url: str | None = Field(alias="previewUrl", default=None, max_length=16_384)

    @field_validator("template_id")
    @classmethod
    def validate_template_id(cls, value: str | None) -> str | None:
        if value is not None and not _valid_positive_id(value):
            raise ValueError("invalid template namespace ID")
        return value

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        if value is not None and "\0" in value:
            raise ValueError("invalid app description")
        return value


class ListInfoPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    offset: float = Field(ge=0)
    count: float = Field(ge=0)
    cursor: str = Field(max_length=16_384)

    @field_validator("offset", "count")
    @classmethod
    def validate_integer_float(cls, value: float) -> float:
        if not math.isfinite(value) or not value.is_integer():
            raise ValueError("invalid app page information")
        return value


class ListAppsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: ResponseStatus
    info: ListInfoPayload | None
    apps: list[AppPayload] | None


class ListApps(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    list_apps: ListAppsPayload = Field(alias="listApps")


class ListAppsData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    apps: ListApps


class SingleAppPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: ResponseStatus
    app: AppDetailPayload | None


class GetApp(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    get_app: SingleAppPayload = Field(alias="getAppById")


class GetAppData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    apps: GetApp


class GetAppByRoute(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    get_app: SingleAppPayload = Field(alias="getAppByRoute")


class GetAppByRouteData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    apps: GetAppByRoute


class CreateApp(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    create_app: SingleAppPayload = Field(alias="createApp")


class CreateAppData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    apps: CreateApp


class DefaultMutationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: ResponseStatus


class UpdateApp(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    update_app: DefaultMutationPayload = Field(alias="updateApp")


class UpdateAppData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    apps: UpdateApp


class DeleteApp(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    delete_app: DefaultMutationPayload = Field(alias="deleteApp")


class DeleteAppData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    apps: DeleteApp
