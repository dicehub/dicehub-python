from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


def _utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("run timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


class RunState(str, Enum):
    IDLE = "IDLE"
    PREPARING = "PREPARING"
    AWAITING = "AWAITING"
    RUNNING = "RUNNING"
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SYNCHRONIZING = "SYNCHRONIZING"
    STOPPING = "STOPPING"
    INTERRUPTING = "INTERRUPTING"
    FINISHED = "FINISHED"
    STOPPED = "STOPPED"
    FAILED = "FAILED"
    INTERRUPTED = "INTERRUPTED"
    CANCELED = "CANCELED"


class RunType(str, Enum):
    REGULAR = "REGULAR"
    EXTRA = "EXTRA"
    MICRO = "MICRO"
    PREDICTION = "PREDICTION"


class RunExecutionStatus(str, Enum):
    FINISHED = "FINISHED"
    STOPPED = "STOPPED"
    FAILED = "FAILED"
    INTERRUPTED = "INTERRUPTED"


class RunError(str, Enum):
    NONE = "NONE"
    PREPARING_FAILED = "PREPARING_FAILED"
    CPU_HOURS_QUOTA_EXCEEDED = "CPU_HOURS_QUOTA_EXCEEDED"
    SUBSCRIPTION_ERROR = "SUBSCRIPTION_ERROR"
    SYNCHRONIZING_FAILED = "SYNCHRONIZING_FAILED"
    PROCESSING_FAILED = "PROCESSING_FAILED"
    CREDITS_RAN_OUT = "CREDITS_RAN_OUT"
    MONTHLY_USAGE_LIMIT_REACHED = "MONTHLY_USAGE_LIMIT_REACHED"
    MAX_MONTHLY_USAGE_LIMIT_REACHED = "MAX_MONTHLY_USAGE_LIMIT_REACHED"


class RunFlag(str, Enum):
    NOTIFY = "NOTIFY"
    AUTO_ARCHIVE = "AUTO_ARCHIVE"
    ARCHIVED = "ARCHIVED"
    ALWAYS_SYNCHRONIZE = "ALWAYS_SYNCHRONIZE"
    FINALIZER = "FINALIZER"
    UPDATING = "UPDATING"
    UPDATE_FAILED = "UPDATE_FAILED"


class RunOrderField(str, Enum):
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"


class MachinePrice(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    amount: Decimal = Field(ge=0, max_digits=16, decimal_places=2)
    currency: Literal["EUR"]


class MachineType(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    machine_type_id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,127}$")
    cpu_count: int | None = Field(default=None, ge=1, le=2**31 - 1)
    gpu_count: int | None = Field(default=None, ge=0, le=2**31 - 1)
    ram_gb: int | None = Field(default=None, ge=1, le=2**31 - 1)
    description: str = Field(min_length=1, max_length=256)
    price: MachinePrice | None


class Run(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    run_id: str = Field(min_length=36, max_length=36)
    namespace_id: str = Field(min_length=1, max_length=256)
    name: str | None = None
    state: RunState
    run_type: RunType | None
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at")
    @classmethod
    def normalize_timestamps(cls, value: datetime) -> datetime:
        return _utc_datetime(value)


class RunDetail(Run):
    run_internal_id: int | None = Field(default=None, ge=0)
    machine_type_id: str | None = None
    node_count: int | None = Field(default=None, ge=0)
    cpu_count: int | None = Field(default=None, ge=0)
    execution_status: RunExecutionStatus | None
    error: RunError | None
    flags: tuple[RunFlag, ...]
    template_version: str | None = None
    module: str | None = None
    flow: str | None = None
    queue: str | None = None
    study_id: str | None = Field(default=None, min_length=36, max_length=36)
    stage: int | None
    batch: str | None = None


class RunStatus(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    run_id: str = Field(min_length=36, max_length=36)
    state: RunState
    execution_status: RunExecutionStatus | None
    error: RunError | None
    flags: tuple[RunFlag, ...]
    updated_at: datetime

    @field_validator("updated_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        return _utc_datetime(value)


class RunResultS3Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    bucket: str = Field(min_length=36, max_length=36)
    access_key_id: SecretStr = Field(min_length=20, max_length=20)
    secret_access_key: SecretStr = Field(min_length=40, max_length=40)


class RunPage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    runs: tuple[Run, ...]
    offset: int = Field(ge=0)
    count: int = Field(ge=0)
    cursor: str = Field(max_length=16_384)
