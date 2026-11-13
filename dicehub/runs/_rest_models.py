"""Strict REST wire representations."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, SecretStr

from dicehub._core.rest_models import WireModel, WirePage


class RunDetail(WireModel):
    run_id: UUID
    run_internal_id: str = Field(pattern=r"^[0-9]{1,19}$")
    namespace_id: str
    machine_type_id: str | None
    node_count: int | None
    cpu_count: int | None
    state: (
        Literal[
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
        | None
    )
    created_at: AwareDatetime | None
    updated_at: AwareDatetime | None
    flags: tuple[
        Literal[
            "NOTIFY",
            "AUTO_ARCHIVE",
            "ARCHIVED",
            "ALWAYS_SYNCHRONIZE",
            "FINALIZER",
            "UPDATING",
            "UPDATE_FAILED",
            "STARTING",
        ],
        ...,
    ]
    name: str | None
    execution_status: Literal["FINISHED", "STOPPED", "FAILED", "INTERRUPTED"] | None
    template_version: str | None
    error: (
        Literal[
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
        | None
    )
    run_type: Literal["REGULAR", "EXTRA", "MICRO", "PREDICTION"] | None
    module: str | None
    flow: str | None
    queue: str | None
    study_id: UUID | None
    stage: int | None
    batch: str | None


class RunList(WirePage):
    items: tuple[RunDetail, ...]


class StartedRun(WireModel):
    run_id: UUID
    state: (
        Literal[
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
        | None
    )
    execution_status: Literal["FINISHED", "STOPPED", "FAILED", "INTERRUPTED"] | None
    error: (
        Literal[
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
        | None
    )
    flags: tuple[
        Literal[
            "NOTIFY",
            "AUTO_ARCHIVE",
            "ARCHIVED",
            "ALWAYS_SYNCHRONIZE",
            "FINALIZER",
            "UPDATING",
            "UPDATE_FAILED",
            "STARTING",
        ],
        ...,
    ]
    updated_at: AwareDatetime | None


class Done(WireModel):
    succeeded: Literal[True]


class MachineDetail(WireModel):
    machine_type_id: str
    provider: Literal["AWS", "LOCAL", "FREE", "HETZNER"]
    product_id: str | None
    cpu_count: int | None
    amount_of_ram: int | None
    amount_of_storage: int | None
    has_efa: bool
    has_lustre: bool
    requires_subscription: bool
    usage_multiplier: float
    max_nodes: int
    gpu_count: int | None
    allowed_for_models: bool


class MachineList(WireModel):
    items: tuple[MachineDetail, ...]


class PriceDetail(WireModel):
    base_amount: str | None
    amount: str
    currency: str
    vat_rate: str


class ProductDetail(WireModel):
    product_id: str
    product_type: str
    price: PriceDetail


class ProductList(WireModel):
    items: tuple[ProductDetail, ...]


class ResourceDetail(WireModel):
    resource_id: UUID
    namespace_id: str
    key: str
    resource_type: Literal["FOLDER", "TEXT", "FILE", "CHANNEL"]


class StorageCredentials(WireModel):
    bucket: str = Field(min_length=36, max_length=36)
    access_key_id: SecretStr = Field(min_length=20, max_length=20)
    secret_access_key: SecretStr = Field(min_length=40, max_length=40)
