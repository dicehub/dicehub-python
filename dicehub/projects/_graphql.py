from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from dicehub._core.status import ResponseStatus

LIST_PROJECTS_QUERY = """
query ListProjects(
  $userId: String
  $groupId: String
  $searchFilter: String
  $orderBy: String!
  $order: OrderTypeEnum!
  $offset: Float!
  $limit: Float!
  $cursor: String
) {
  projects {
    listProjects(
      userId: $userId
      groupId: $groupId
      searchFilter: $searchFilter
      orderBy: $orderBy
      order: $order
      offset: $offset
      limit: $limit
      ahead: 1
      cursor: $cursor
    ) {
      status { succeeded error }
      info { offset count cursor }
      projects {
        projectId
        groupId
        name
        displayRoute
        route
        visibility
      }
    }
  }
}
"""

GET_PROJECT_QUERY = """
query GetProject($projectId: String!) {
  projects {
    getProjectById(projectId: $projectId) {
      status { succeeded error }
      project {
        projectId
        groupId
        name
        displayRoute
        route
        visibility
        description
        avatarUrl
      }
    }
  }
}
"""

GET_PROJECT_BY_ROUTE_QUERY = """
query GetProjectByRoute($route: String!) {
  projects {
    getProjectByRoute(route: $route) {
      # The server derives SQL fields from the first nested selection for this resolver.
      # Keep project before status until getProjectByRoute excludes status server-side.
      project {
        projectId
        groupId
        name
        displayRoute
        route
        visibility
        description
        avatarUrl
      }
      status { succeeded error }
    }
  }
}
"""

CREATE_PROJECT_MUTATION = """
mutation CreateProject(
  $name: String!
  $slug: String!
  $description: String
  $groupId: String
  $visibility: ProjectVisibilityEnum!
) {
  projects {
    createProject(
      name: $name
      slug: $slug
      description: $description
      groupId: $groupId
      visibility: $visibility
    ) {
      status { succeeded error }
      project {
        projectId
        groupId
        name
        displayRoute
        route
        visibility
        description
        avatarUrl
      }
    }
  }
}
"""

UPDATE_PROJECT_MUTATION = """
mutation UpdateProject(
  $projectId: String!
  $name: String
  $slug: String
  $description: String
  $visibility: ProjectVisibilityEnum
) {
  projects {
    updateProject(
      projectId: $projectId
      name: $name
      slug: $slug
      description: $description
      visibility: $visibility
    ) {
      status { succeeded error }
    }
  }
}
"""

MOVE_PROJECT_MUTATION = """
mutation MoveProject($projectId: String!, $toGroupId: String!) {
  projects {
    moveProject(projectId: $projectId, toGroupId: $toGroupId) {
      status { succeeded error }
    }
  }
}
"""

DELETE_PROJECT_MUTATION = """
mutation DeleteProject($projectId: String!) {
  projects {
    deleteProject(projectId: $projectId) {
      status { succeeded error }
    }
  }
}
"""


def _valid_positive_id(value: str) -> bool:
    return (
        0 < len(value) <= 256 and value.isascii() and value.isdigit() and not value.startswith("0")
    )


class ProjectPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    project_id: str = Field(alias="projectId", min_length=1, max_length=256)
    group_id: str = Field(alias="groupId", min_length=1, max_length=256)
    name: str = Field(min_length=1, max_length=128)
    display_route: str = Field(alias="displayRoute", min_length=1)
    route: str = Field(min_length=1)
    visibility: Literal["INTERNAL", "PRIVATE", "PUBLIC"]

    @field_validator("project_id", "group_id")
    @classmethod
    def validate_ids(cls, value: str) -> str:
        if not _valid_positive_id(value):
            raise ValueError("invalid project namespace ID")
        return value


class ProjectDetailPayload(ProjectPayload):
    description: str | None
    avatar_url: str | None = Field(alias="avatarUrl")

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        if value is not None and "\0" in value:
            raise ValueError("invalid project description")
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
            raise ValueError("invalid project page information")
        return value


class ListProjectsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: ResponseStatus
    info: ListInfoPayload | None
    projects: list[ProjectPayload] | None


class ListProjects(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    list_projects: ListProjectsPayload = Field(alias="listProjects")


class ListProjectsData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    projects: ListProjects


class SingleProjectPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: ResponseStatus
    project: ProjectDetailPayload | None


class GetProject(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    get_project: SingleProjectPayload = Field(alias="getProjectById")


class GetProjectData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    projects: GetProject


class GetProjectByRoute(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    get_project: SingleProjectPayload = Field(alias="getProjectByRoute")


class GetProjectByRouteData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    projects: GetProjectByRoute


class CreateProject(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    create_project: SingleProjectPayload = Field(alias="createProject")


class CreateProjectData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    projects: CreateProject


class DefaultMutationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: ResponseStatus


class UpdateProject(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    update_project: DefaultMutationPayload = Field(alias="updateProject")


class UpdateProjectData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    projects: UpdateProject


class MoveProject(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    move_project: DefaultMutationPayload = Field(alias="moveProject")


class MoveProjectData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    projects: MoveProject


class DeleteProject(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    delete_project: DefaultMutationPayload = Field(alias="deleteProject")


class DeleteProjectData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    projects: DeleteProject
