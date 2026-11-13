"""Explicit REST v2 response representations."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from dicehub._core.rest_models import WireModel, WirePage


class ResourceDetail(WireModel):
    resource_id: UUID
    namespace_id: str
    key: str
    resource_type: Literal["FOLDER", "TEXT", "FILE", "CHANNEL"]


class ResourceList(WirePage):
    items: tuple[ResourceDetail, ...]


class ResourceText(WireModel):
    content: str | None


class Done(WireModel):
    succeeded: Literal[True]
