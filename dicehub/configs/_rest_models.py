"""Explicit REST v2 response representations."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime

from dicehub._core.rest_models import WireModel, WirePage


class ConfigDetail(WireModel):
    config_id: str
    app_id: str
    config_internal_id: str
    name: str
    description: str | None
    is_default: bool
    template_version: str | None
    updating: bool | None


class ConfigList(WirePage):
    items: tuple[ConfigDetail, ...]


class Done(WireModel):
    succeeded: Literal[True]


class ConfigContentEntry(WireModel):
    path: str
    resource_type: Literal["FOLDER", "TEXT", "FILE", "CHANNEL"]


class ConfigContentList(WirePage):
    items: tuple[ConfigContentEntry, ...]


class ConfigTextResponse(WireModel):
    content: str


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


class GeometryRuns(WireModel):
    conversion_run: StartedRun
    setup_run: StartedRun | None
