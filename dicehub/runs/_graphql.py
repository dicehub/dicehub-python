from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from dicehub._core.status import ResponseStatus

LIST_RUNS_QUERY = """
query ListRuns(
  $namespaceId: String!
  $includeDescendants: Boolean!
  $appId: String
  $runTypes: [RunTypeEnum]
  $states: [RunStateTypeEnum]
  $orderBy: String!
  $order: OrderTypeEnum!
  $offset: Int!
  $limit: Int!
  $cursor: String
) {
  runs {
    listRunsByNamespaceId(
      namespaceId: $namespaceId
      deep: $includeDescendants
      appId: $appId
      runType: $runTypes
      state: $states
      orderBy: $orderBy
      order: $order
      offset: $offset
      limit: $limit
      ahead: 1
      cursor: $cursor
    ) {
      status { succeeded error }
      info { offset count cursor }
      runs {
        runId
        namespaceId
        name
        state
        runType
        createdAt
        updatedAt
      }
    }
  }
}
"""

GET_RUN_QUERY = """
query GetRun($runId: String!) {
  runs {
    getSingleRunById(runId: $runId) {
      status { succeeded error }
      run {
        runId
        runInternalId
        namespaceId
        machineTypeId
        nodeCount
        cpuCount
        state
        createdAt
        updatedAt
        flags
        name
        executionStatus
        templateVersion
        error
        runType
        module
        flow
        queue
        studyId
        stage
        batch
      }
    }
  }
}
"""

GET_RUN_STATUS_QUERY = """
query GetRunStatus($runId: String!) {
  runs {
    getSingleRunById(runId: $runId) {
      status { succeeded error }
      run {
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

START_RUN_MUTATION = """
mutation StartRun(
  $configId: String!
  $machineTypeId: String!
  $nodeCount: Int!
  $cpuCount: Int
  $notify: Boolean!
) {
  configs {
    startRun(
      configId: $configId
      machineTypeId: $machineTypeId
      nodeCount: $nodeCount
      cpuCount: $cpuCount
      notify: $notify
    ) {
      status { succeeded error }
      run {
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

STOP_RUN_MUTATION = """
mutation StopRun($runId: String!) {
  runs {
    stopRun(runId: $runId) {
      status { succeeded error }
    }
  }
}
"""

GET_RUN_RESULT_FOLDER_QUERY = """
query GetRunResultFolder($appId: String!, $key: String!) {
  resources {
    getResourceByKey(namespaceId: $appId, key: $key) {
      status { succeeded error }
      resource { resourceId }
    }
  }
}
"""

GET_RUN_RESULT_S3_CREDENTIALS_MUTATION = """
mutation GetRunResultS3Credentials(
  $resourceId: String!
  $generateNewKey: Boolean!
) {
  resources {
    getFolderS3Credentials(
      resourceId: $resourceId
      generateNewKey: $generateNewKey
    ) {
      status { succeeded error }
      bucket
      accessKeyId
      secretAccessKey
    }
  }
}
"""

RunStateValue = Literal[
    "IDLE",
    "PREPARING",
    "AWAITING",
    "RUNNING",
    "PENDING",
    "PROCESSING",
    "SYNCHRONIZING",
    "STOPPING",
    "INTERRUPTING",
    "FINISHED",
    "STOPPED",
    "FAILED",
    "INTERRUPTED",
    "CANCELED",
]
RunTypeValue = Literal["REGULAR", "EXTRA", "MICRO", "PREDICTION"]
RunExecutionStatusValue = Literal["FINISHED", "STOPPED", "FAILED", "INTERRUPTED"]
RunErrorValue = Literal[
    "NONE",
    "PREPARING_FAILED",
    "CPU_HOURS_QUOTA_EXCEEDED",
    "SUBSCRIPTION_ERROR",
    "SYNCHRONIZING_FAILED",
    "PROCESSING_FAILED",
    "CREDITS_RAN_OUT",
    "MONTHLY_USAGE_LIMIT_REACHED",
    "MAX_MONTHLY_USAGE_LIMIT_REACHED",
]
RunFlagValue = Literal[
    "NOTIFY",
    "AUTO_ARCHIVE",
    "ARCHIVED",
    "ALWAYS_SYNCHRONIZE",
    "FINALIZER",
    "UPDATING",
    "UPDATE_FAILED",
]


def _validated_uuid(value: str) -> str:
    parsed: UUID | None = None
    if isinstance(value, str) and len(value) == 36 and value.isascii():
        try:
            parsed = UUID(value)
        except ValueError:
            pass
    if parsed is None or str(parsed) != value.lower():
        raise ValueError("invalid run UUID")
    return str(parsed)


def _validated_positive_id(value: str) -> str:
    if (
        not isinstance(value, str)
        or not value.isascii()
        or not value.isdigit()
        or value.startswith("0")
        or len(value) > 256
    ):
        raise ValueError("invalid run namespace ID")
    return value


def _parsed_timestamp(value: object) -> datetime:
    if not isinstance(value, str) or not 1 <= len(value) <= 64 or not value.isascii():
        raise ValueError("invalid run timestamp")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise ValueError("invalid run timestamp") from error
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class RunPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    run_id: str = Field(alias="runId")
    namespace_id: str = Field(alias="namespaceId")
    name: str | None = None
    state: RunStateValue
    run_type: RunTypeValue | None = Field(alias="runType")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")

    @field_validator("run_id")
    @classmethod
    def validate_run_id(cls, value: str) -> str:
        return _validated_uuid(value)

    @field_validator("namespace_id")
    @classmethod
    def validate_namespace_id(cls, value: str) -> str:
        return _validated_positive_id(value)

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def validate_timestamps(cls, value: object) -> datetime:
        return _parsed_timestamp(value)


class RunDetailPayload(RunPayload):
    run_internal_id: int | None = Field(alias="runInternalId", default=None, ge=0)
    machine_type_id: str | None = Field(alias="machineTypeId", default=None)
    node_count: int | None = Field(alias="nodeCount", default=None, ge=0)
    cpu_count: int | None = Field(alias="cpuCount", default=None, ge=0)
    flags: list[RunFlagValue] | None
    execution_status: RunExecutionStatusValue | None = Field(alias="executionStatus")
    template_version: str | None = Field(alias="templateVersion", default=None)
    error: RunErrorValue | None
    module: str | None = None
    flow: str | None = None
    queue: str | None = None
    study_id: str | None = Field(alias="studyId", default=None)
    stage: int | None
    batch: str | None = None

    @field_validator("study_id")
    @classmethod
    def validate_study_id(cls, value: str | None) -> str | None:
        return None if value is None else _validated_uuid(value)


class RunStatusPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    run_id: str = Field(alias="runId")
    state: RunStateValue
    execution_status: RunExecutionStatusValue | None = Field(alias="executionStatus")
    error: RunErrorValue | None
    flags: list[RunFlagValue] | None
    updated_at: datetime = Field(alias="updatedAt")

    @field_validator("run_id")
    @classmethod
    def validate_run_id(cls, value: str) -> str:
        return _validated_uuid(value)

    @field_validator("updated_at", mode="before")
    @classmethod
    def validate_timestamp(cls, value: object) -> datetime:
        return _parsed_timestamp(value)


class ListInfoPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    offset: float = Field(ge=0)
    count: float = Field(ge=0)
    cursor: str = Field(max_length=16_384)

    @field_validator("offset", "count")
    @classmethod
    def validate_integer_float(cls, value: float) -> float:
        if not math.isfinite(value) or not value.is_integer():
            raise ValueError("invalid run page information")
        return value


class ListRunsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: ResponseStatus
    info: ListInfoPayload | None
    runs: list[RunPayload] | None


class ListRuns(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    list_runs: ListRunsPayload = Field(alias="listRunsByNamespaceId")


class ListRunsData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    runs: ListRuns


class SingleRunPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: ResponseStatus
    run: RunDetailPayload | None


class GetRun(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    get_run: SingleRunPayload = Field(alias="getSingleRunById")


class GetRunData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    runs: GetRun


class SingleRunStatusPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: ResponseStatus
    run: RunStatusPayload | None


class GetRunStatus(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    get_run: SingleRunStatusPayload = Field(alias="getSingleRunById")


class GetRunStatusData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    runs: GetRunStatus


class RunResultFolderResourcePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    resource_id: str = Field(alias="resourceId")

    @field_validator("resource_id")
    @classmethod
    def validate_resource_id(cls, value: str) -> str:
        return _validated_uuid(value)


class RunResultFolderPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: ResponseStatus
    resource: RunResultFolderResourcePayload | None


class RunResultFolderResources(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    get_result_folder: RunResultFolderPayload = Field(alias="getResourceByKey")


class GetRunResultFolderData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    resources: RunResultFolderResources


class RunResultS3CredentialsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: ResponseStatus
    bucket: str | None = Field(default=None, min_length=36, max_length=36)
    access_key_id: str | None = Field(
        alias="accessKeyId",
        default=None,
        min_length=20,
        max_length=20,
    )
    secret_access_key: str | None = Field(
        alias="secretAccessKey",
        default=None,
        min_length=40,
        max_length=40,
    )

    @field_validator("bucket")
    @classmethod
    def validate_bucket(cls, value: str | None) -> str | None:
        return None if value is None else _validated_uuid(value)


class RunResultS3CredentialsResources(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    get_credentials: RunResultS3CredentialsPayload = Field(alias="getFolderS3Credentials")


class GetRunResultS3CredentialsData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    resources: RunResultS3CredentialsResources


class StartRunPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: ResponseStatus
    run: RunStatusPayload | None


class StartRunConfigs(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    start_run: StartRunPayload = Field(alias="startRun")


class StartRunData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    configs: StartRunConfigs


class StopRunPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: ResponseStatus


class StopRunRuns(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    stop_run: StopRunPayload = Field(alias="stopRun")


class StopRunData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    runs: StopRunRuns
