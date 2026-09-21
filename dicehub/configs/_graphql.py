from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from dicehub._core.status import ResponseStatus
from dicehub.runs._graphql import RunStatusPayload

LIST_CONFIGS_QUERY = """
query ListConfigs(
  $appId: String!
  $searchFilter: String
  $order: OrderTypeEnum!
  $offset: Float!
  $limit: Float!
  $cursor: String
) {
  configs {
    listConfigs(
      appId: $appId
      searchFilter: $searchFilter
      orderBy: "config_id"
      order: $order
      offset: $offset
      limit: $limit
      ahead: 1
      cursor: $cursor
    ) {
      status { succeeded error }
      info { offset count cursor }
      configs {
        configId
        appId
        configInternalId
        name
        description
        isDefault
        templateVersion
        updating
      }
    }
  }
}
"""

GET_CONFIG_QUERY = """
query GetConfig($configId: String!) {
  configs {
    getSingleConfigById(configId: $configId) {
      status { succeeded error }
      config {
        configId
        appId
        configInternalId
        name
        description
        isDefault
        templateVersion
        updating
      }
    }
  }
}
"""

CREATE_CONFIG_MUTATION = """
mutation CreateConfig(
  $appId: String!
  $sourceConfigId: String
  $name: String
  $description: String
) {
  configs {
    createConfig(
      appId: $appId
      configId: $sourceConfigId
      name: $name
      description: $description
    ) {
      status { succeeded error }
      config {
        configId
        appId
        configInternalId
        name
        description
        isDefault
        templateVersion
        updating
      }
    }
  }
}
"""

UPDATE_CONFIG_MUTATION = """
mutation UpdateConfig($configId: String!, $name: String, $description: String) {
  configs {
    updateConfig(configId: $configId, name: $name, description: $description) {
      status { succeeded error }
    }
  }
}
"""

DELETE_CONFIG_MUTATION = """
mutation DeleteConfig($configId: String!) {
  configs {
    deleteConfig(configId: $configId) {
      status { succeeded error }
    }
  }
}
"""

IMPORT_CONFIG_GEOMETRY_MUTATION = """
mutation ImportConfigGeometry($configId: String!, $filename: String!) {
  configs {
    importConfigGeometry(configId: $configId, filename: $filename) {
      status { succeeded error }
      conversionRun {
        runId
        state
        executionStatus
        error
        flags
        updatedAt
      }
      setupRun {
        runId
        state
        executionStatus
        error
        flags
        updatedAt
      }
    }
  }
}
"""

LIST_CONFIG_CONTENT_QUERY = """
query ListConfigContent(
  $configId: String!
  $area: ConfigContentAreaEnum!
  $path: String
  $deep: Boolean!
  $order: OrderTypeEnum!
  $offset: Float!
  $limit: Float!
  $cursor: String
) {
  configs {
    listConfigContent(
      configId: $configId
      area: $area
      path: $path
      deep: $deep
      order: $order
      offset: $offset
      limit: $limit
      ahead: 1
      cursor: $cursor
    ) {
      status { succeeded error }
      info { offset count cursor }
      entries { path resourceType }
    }
  }
}
"""

GET_CONFIG_TEXT_QUERY = """
query GetConfigText($configId: String!, $path: String!) {
  configs {
    getConfigText(configId: $configId, path: $path) {
      status { succeeded error }
      content
    }
  }
}
"""

SET_CONFIG_TEXT_MUTATION = """
mutation SetConfigText($configId: String!, $path: String!, $content: String!) {
  configs {
    setConfigText(configId: $configId, path: $path, content: $content) {
      status { succeeded error }
    }
  }
}
"""

SET_CONFIG_VALUES_MUTATION = """
mutation SetConfigValues(
  $configId: String!
  $path: String!
  $updates: [ConfigValueUpdateInput!]!
) {
  configs {
    setConfigValues(configId: $configId, path: $path, updates: $updates) {
      status { succeeded error }
    }
  }
}
"""

DELETE_CONFIG_CONTENT_MUTATION = """
mutation DeleteConfigContent(
  $configId: String!
  $area: ConfigContentAreaEnum!
  $path: String!
) {
  configs {
    deleteConfigContent(configId: $configId, area: $area, path: $path) {
      status { succeeded error }
    }
  }
}
"""


def _valid_positive_id(value: str) -> bool:
    return (
        0 < len(value) <= 256 and value.isascii() and value.isdigit() and not value.startswith("0")
    )


class ConfigPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    config_id: str = Field(alias="configId", min_length=1, max_length=256)
    app_id: str = Field(alias="appId", min_length=1, max_length=256)
    config_internal_id: str = Field(alias="configInternalId", min_length=1, max_length=256)
    name: str = Field(min_length=1, max_length=128)
    description: str | None
    is_default: bool = Field(alias="isDefault")
    template_version: str | None = Field(alias="templateVersion", default=None, max_length=256)
    updating: bool | None

    @field_validator("config_id", "app_id", "config_internal_id")
    @classmethod
    def validate_ids(cls, value: str) -> str:
        if not _valid_positive_id(value):
            raise ValueError("invalid config namespace ID")
        return value

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        if value is not None and "\0" in value:
            raise ValueError("invalid config description")
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
            raise ValueError("invalid config page information")
        return value


class ListConfigsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: ResponseStatus
    info: ListInfoPayload | None
    configs: list[ConfigPayload] | None


class ListConfigs(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    list_configs: ListConfigsPayload = Field(alias="listConfigs")


class ListConfigsData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    configs: ListConfigs


class SingleConfigPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: ResponseStatus
    config: ConfigPayload | None


class GetConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    get_config: SingleConfigPayload = Field(alias="getSingleConfigById")


class GetConfigData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    configs: GetConfig


class CreateConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    create_config: SingleConfigPayload = Field(alias="createConfig")


class CreateConfigData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    configs: CreateConfig


class DefaultPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: ResponseStatus


class UpdateConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    update_config: DefaultPayload = Field(alias="updateConfig")


class UpdateConfigData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    configs: UpdateConfig


class DeleteConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    delete_config: DefaultPayload = Field(alias="deleteConfig")


class DeleteConfigData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    configs: DeleteConfig


class ImportConfigGeometryPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: ResponseStatus
    conversion_run: RunStatusPayload | None = Field(alias="conversionRun")
    setup_run: RunStatusPayload | None = Field(alias="setupRun")


class ImportConfigGeometry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    import_config_geometry: ImportConfigGeometryPayload = Field(alias="importConfigGeometry")


class ImportConfigGeometryData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    configs: ImportConfigGeometry


class ConfigContentPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    path: str = Field(min_length=1, max_length=1024)
    resource_type: Literal["FOLDER", "TEXT", "FILE"] = Field(alias="resourceType")

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        if (
            value.startswith("/")
            or value.endswith("/")
            or "\\" in value
            or any(not part or part in {".", ".."} or len(part) > 255 for part in value.split("/"))
            or any(not character.isprintable() for character in value)
        ):
            raise ValueError("invalid config content path")
        return value


class ListConfigContentPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: ResponseStatus
    info: ListInfoPayload | None
    entries: list[ConfigContentPayload] | None


class ListConfigContent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    list_config_content: ListConfigContentPayload = Field(alias="listConfigContent")


class ListConfigContentData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    configs: ListConfigContent


class ConfigTextPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: ResponseStatus
    content: str | None


class GetConfigText(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    get_config_text: ConfigTextPayload = Field(alias="getConfigText")


class GetConfigTextData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    configs: GetConfigText


class SetConfigText(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    set_config_text: DefaultPayload = Field(alias="setConfigText")


class SetConfigTextData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    configs: SetConfigText


class SetConfigValues(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    set_config_values: DefaultPayload = Field(alias="setConfigValues")


class SetConfigValuesData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    configs: SetConfigValues


class DeleteConfigContent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    delete_config_content: DefaultPayload = Field(alias="deleteConfigContent")


class DeleteConfigContentData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    configs: DeleteConfigContent
