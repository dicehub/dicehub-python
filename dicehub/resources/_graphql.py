from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from dicehub._core.status import ResponseStatus

_RESOURCE_FIELDS = """
        resourceId
        namespaceId
        key
        resourceType
"""

GET_RESOURCE_QUERY = f"""
query GetResource($resourceId: String!) {{
  resources {{
    getResourceById(resourceId: $resourceId) {{
      status {{ succeeded error }}
      resource {{
{_RESOURCE_FIELDS}      }}
    }}
  }}
}}
"""

GET_RESOURCE_BY_KEY_QUERY = f"""
query GetResourceByKey($namespaceId: String!, $key: String!) {{
  resources {{
    getResourceByKey(namespaceId: $namespaceId, key: $key) {{
      status {{ succeeded error }}
      resource {{
{_RESOURCE_FIELDS}      }}
    }}
  }}
}}
"""

LIST_RESOURCES_QUERY = f"""
query ListResources(
  $namespaceId: String!
  $path: String!
  $resourceType: ResourceTypeEnum
  $searchFilter: String
  $deep: Boolean!
  $order: OrderTypeEnum!
  $offset: Float!
  $limit: Float!
  $cursor: String
) {{
  resources {{
    listResources(
      namespaceId: $namespaceId
      path: $path
      resourceType: $resourceType
      searchFilter: $searchFilter
      deep: $deep
      orderBy: "key"
      order: $order
      offset: $offset
      limit: $limit
      ahead: 1
      cursor: $cursor
    ) {{
      status {{ succeeded error }}
      info {{ offset count cursor }}
      resources {{
{_RESOURCE_FIELDS}      }}
    }}
  }}
}}
"""

GET_RESOURCE_TEXT_QUERY = """
query GetResourceText($resourceId: String!) {
  resources {
    getTextContent(resourceId: $resourceId) {
      status { succeeded error }
      content
    }
  }
}
"""

CREATE_RESOURCE_TEXT_MUTATION = """
mutation CreateResourceText($namespaceId: String!, $key: String!, $content: String!) {
  resources {
    createText(namespaceId: $namespaceId, key: $key, content: $content) {
      status { succeeded error }
    }
  }
}
"""

SET_RESOURCE_TEXT_MUTATION = """
mutation SetResourceText($resourceId: String!, $content: String!) {
  resources {
    setTextContent(resourceId: $resourceId, content: $content) {
      status { succeeded error }
    }
  }
}
"""

DELETE_RESOURCE_MUTATION = """
mutation DeleteResource($resourceId: String!) {
  resources {
    deleteResource(resourceId: $resourceId) {
      status { succeeded error }
    }
  }
}
"""


class ResourcePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    resource_id: str = Field(alias="resourceId", min_length=1, max_length=256)
    namespace_id: str = Field(alias="namespaceId", min_length=1, max_length=256)
    key: str = Field(min_length=4, max_length=1029)
    resource_type: Literal["FOLDER", "TEXT", "FILE", "CHANNEL"] = Field(alias="resourceType")


class ListInfoPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    offset: float = Field(ge=0)
    count: float = Field(ge=0)
    cursor: str = Field(max_length=16_384)

    @field_validator("offset", "count")
    @classmethod
    def validate_integer_float(cls, value: float) -> float:
        if not math.isfinite(value) or not value.is_integer():
            raise ValueError("invalid resource page information")
        return value


class SingleResourcePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: ResponseStatus
    resource: ResourcePayload | None


class GetResourceQueryPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    get_resource: SingleResourcePayload = Field(alias="getResourceById")


class GetResourceData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    resources: GetResourceQueryPayload


class GetResourceByKeyQueryPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    get_resource: SingleResourcePayload = Field(alias="getResourceByKey")


class GetResourceByKeyData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    resources: GetResourceByKeyQueryPayload


class ListResourcesPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: ResponseStatus
    info: ListInfoPayload | None
    resources: list[ResourcePayload] | None


class ListResourcesQueryPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    list_resources: ListResourcesPayload = Field(alias="listResources")


class ListResourcesData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    resources: ListResourcesQueryPayload


class ResourceTextPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: ResponseStatus
    content: str | None


class GetResourceTextQueryPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    get_text: ResourceTextPayload = Field(alias="getTextContent")


class GetResourceTextData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    resources: GetResourceTextQueryPayload


class DefaultMutationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: ResponseStatus


class CreateResourceTextMutationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    create_text: DefaultMutationPayload = Field(alias="createText")


class CreateResourceTextData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    resources: CreateResourceTextMutationPayload


class SetResourceTextMutationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    set_text: DefaultMutationPayload = Field(alias="setTextContent")


class SetResourceTextData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    resources: SetResourceTextMutationPayload


class DeleteResourceMutationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    delete_resource: DefaultMutationPayload = Field(alias="deleteResource")


class DeleteResourceData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    resources: DeleteResourceMutationPayload
