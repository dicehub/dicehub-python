from __future__ import annotations

import math
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator

from dicehub._core.status import ResponseStatus

_TEMPLATE_FIELDS = """
        templateId
        name
        slug
        description
        clientType
        route
        imagePath
        iconPath
        tags { tagId tag }
        createdAt
        updatedAt
"""

LIST_TEMPLATES_QUERY = f"""
query ListTemplates(
  $searchFilter: String
  $templateType: TemplateTypeEnum
  $tags: [String]
  $orderBy: ListTemplatesOrderByEnum!
  $order: OrderTypeEnum!
  $offset: Float!
  $limit: Float!
  $cursor: String
) {{
  templates {{
    listTemplates(
      searchFilter: $searchFilter
      templateType: $templateType
      tags: $tags
      orderBy: $orderBy
      order: $order
      offset: $offset
      limit: $limit
      ahead: 1
      cursor: $cursor
    ) {{
      status {{ succeeded error }}
      info {{ offset count cursor }}
      templates {{
{_TEMPLATE_FIELDS}
      }}
    }}
  }}
}}
"""

GET_TEMPLATE_QUERY = f"""
query GetTemplate($templateId: String!) {{
  templates {{
    getTemplateById(templateId: $templateId) {{
      status {{ succeeded error }}
      template {{
{_TEMPLATE_FIELDS}
      }}
    }}
  }}
}}
"""

GET_TEMPLATE_BY_ROUTE_QUERY = f"""
query GetTemplateByRoute($route: String!) {{
  templates {{
    getTemplateByRoute(route: $route) {{
      status {{ succeeded error }}
      template {{
{_TEMPLATE_FIELDS}
      }}
    }}
  }}
}}
"""


def _valid_positive_id(value: str) -> bool:
    return (
        0 < len(value) <= 256 and value.isascii() and value.isdigit() and not value.startswith("0")
    )


def _parsed_timestamp(value: object) -> datetime:
    if not isinstance(value, str) or not 1 <= len(value) <= 64 or not value.isascii():
        raise ValueError("invalid template timestamp")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise ValueError("invalid template timestamp") from error
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _valid_printable(value: str, *, max_length: int) -> bool:
    return 0 < len(value) <= max_length and all(character.isprintable() for character in value)


class TemplateTagPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    tag_id: str = Field(alias="tagId", min_length=1, max_length=256)
    tag: str = Field(min_length=1, max_length=256)

    @field_validator("tag_id")
    @classmethod
    def validate_tag_id(cls, value: str) -> str:
        if not _valid_positive_id(value):
            raise ValueError("invalid template tag ID")
        return value

    @field_validator("tag")
    @classmethod
    def validate_tag(cls, value: str) -> str:
        if not _valid_printable(value, max_length=256):
            raise ValueError("invalid template tag")
        return value


class TemplatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    template_id: str = Field(alias="templateId", min_length=1, max_length=256)
    name: str = Field(min_length=1, max_length=256)
    slug: str = Field(min_length=1, max_length=256)
    description: str | None
    client_type: str | None = Field(alias="clientType", max_length=256)
    route: str | None = Field(max_length=16_384)
    image_path: str | None = Field(alias="imagePath", max_length=16_384)
    icon_path: str | None = Field(alias="iconPath", max_length=16_384)
    tags: list[TemplateTagPayload]
    created_at: datetime | None = Field(alias="createdAt")
    updated_at: datetime | None = Field(alias="updatedAt")

    @field_validator("template_id")
    @classmethod
    def validate_template_id(cls, value: str) -> str:
        if not _valid_positive_id(value):
            raise ValueError("invalid template ID")
        return value

    @field_validator("name", "slug")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        if not _valid_printable(value, max_length=256):
            raise ValueError("invalid template text")
        return value

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        if value is not None and "\0" in value:
            raise ValueError("invalid template description")
        return value

    @field_validator("client_type", "image_path", "icon_path")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        if value is not None and any(not character.isprintable() for character in value):
            raise ValueError("invalid template text")
        return value

    @field_validator("route")
    @classmethod
    def validate_route(cls, value: str | None) -> str | None:
        if value is not None and (
            not value.startswith("/") or any(not character.isprintable() for character in value)
        ):
            raise ValueError("invalid template route")
        return value

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def validate_timestamps(cls, value: object) -> datetime | None:
        return None if value is None else _parsed_timestamp(value)


class ListInfoPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    offset: float = Field(ge=0)
    count: float = Field(ge=0)
    cursor: str = Field(max_length=16_384)

    @field_validator("offset", "count")
    @classmethod
    def validate_integer_float(cls, value: float) -> float:
        if not math.isfinite(value) or not value.is_integer():
            raise ValueError("invalid template page information")
        return value


class ListTemplatesPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: ResponseStatus
    info: ListInfoPayload | None
    templates: list[TemplatePayload] | None


class ListTemplates(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    list_templates: ListTemplatesPayload = Field(alias="listTemplates")


class ListTemplatesData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    templates: ListTemplates


class SingleTemplatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: ResponseStatus
    template: TemplatePayload | None


class GetTemplate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    get_template: SingleTemplatePayload = Field(alias="getTemplateById")


class GetTemplateData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    templates: GetTemplate


class GetTemplateByRoute(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    get_template: SingleTemplatePayload = Field(alias="getTemplateByRoute")


class GetTemplateByRouteData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    templates: GetTemplateByRoute
