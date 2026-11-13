"""Map the fixed REST project representation into the existing public models."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from dicehub.errors import ConfigurationError, ProtocolError
from dicehub.projects._validation import (
    validated_cursor,
    validated_enum,
    validated_id,
    validated_offset,
    validated_optional_id,
    validated_page_size,
    validated_route,
    validated_search_filter,
)
from dicehub.projects.models import (
    Project,
    ProjectDetail,
    ProjectOrderField,
    ProjectPage,
    ProjectVisibility,
    SortOrder,
)


class RestProjectSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    project_id: str
    group_id: str
    name: str = Field(min_length=1, max_length=128)
    visibility: Literal["PRIVATE", "INTERNAL", "PUBLIC"]
    route: str = Field(min_length=1)
    display_route: str = Field(min_length=1)

    @field_validator("project_id", "group_id")
    @classmethod
    def check_id(cls, value: str) -> str:
        if (
            not value.isascii()
            or not value.isdecimal()
            or value.startswith("0")
            or len(value) > 19
            or int(value) > 2**63 - 1
        ):
            raise ValueError("invalid project ID")
        return value

    def summary(self) -> Project:
        return Project(
            project_id=self.project_id,
            group_id=self.group_id,
            name=self.name,
            route=self.route,
            display_route=self.display_route,
            visibility=ProjectVisibility(self.visibility),
        )


class RestProject(RestProjectSummary):
    group_type: Literal["USER", "GROUP"] | None = None
    description: str | None
    avatar_url: str | None
    created_at: str
    updated_at: str

    @field_validator("created_at", "updated_at")
    @classmethod
    def check_timestamp(cls, value: str) -> str:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            raise ValueError("timestamp needs an offset")
        return value

    @field_validator("description")
    @classmethod
    def check_description(cls, value: str | None) -> str | None:
        if value is not None and "\0" in value:
            raise ValueError("invalid description")
        return value

    def detail(self) -> ProjectDetail:
        return ProjectDetail(
            **self.summary().model_dump(), description=self.description, avatar_url=self.avatar_url
        )


class RestProjectPage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    items: list[RestProjectSummary]
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0, le=2**31 - 1)
    has_more: bool
    count: int = Field(ge=0)
    cursor: str = Field(max_length=16_384)


def project_id(value: str) -> str:
    value = validated_id(value, "project ID")
    if len(value) > 19 or int(value) > 2**63 - 1:
        raise ConfigurationError("REST v2 project ID exceeds its supported range.")
    return value


def project_route(value: str) -> str:
    return validated_route(value)


def list_query(
    *,
    user_id: str | None,
    group_id: str | None,
    search_filter: str | None,
    order_by: ProjectOrderField,
    order: SortOrder,
    offset: int,
    limit: int,
    cursor: str | None,
) -> dict[str, str | int]:
    params: dict[str, str | int] = {
        "view": "summary",
        "order_by": validated_enum(order_by, ProjectOrderField, "project order field").value,
        "order": validated_enum(order, SortOrder, "project sort order").value,
        "offset": validated_offset(offset),
        "limit": validated_page_size(limit),
    }
    if offset > 2**31 - 1:
        raise ConfigurationError("REST v2 project offset exceeds its supported range.")
    for key, value in (
        ("user_id", validated_optional_id(user_id, "user ID")),
        ("group_id", validated_optional_id(group_id, "group ID")),
    ):
        if value is not None:
            params[key] = project_id(value)
    search = validated_search_filter(search_filter)
    if search is not None:
        params["search"] = search
    cursor = validated_cursor(cursor)
    if cursor is not None:
        params["cursor"] = cursor
    return params


def project_detail(data: object) -> ProjectDetail:
    result = None
    try:
        result = RestProject.model_validate(data).detail()
    except ValidationError:
        pass
    if result is None:
        raise ProtocolError("dicehub returned an incompatible REST v2 project.")
    return result


def project_page(data: object, params: dict[str, str | int]) -> ProjectPage:
    page = None
    try:
        page = RestProjectPage.model_validate(data)
    except ValidationError:
        pass
    if page is None:
        raise ProtocolError("dicehub returned an incompatible REST v2 project page.")
    if (
        page.limit != params["limit"]
        or page.offset != params["offset"]
        or len(page.items) > page.limit
        or len({p.project_id for p in page.items}) != len(page.items)
        or (page.items and page.count < page.offset + len(page.items))
        or page.has_more != (page.count > page.offset + len(page.items))
        or not page.cursor
    ):
        raise ProtocolError("dicehub returned inconsistent REST v2 pagination.")
    return ProjectPage(
        projects=tuple(p.summary() for p in page.items),
        offset=page.offset,
        count=page.count,
        cursor=page.cursor,
    )
