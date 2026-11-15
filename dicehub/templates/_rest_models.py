"""Explicit REST v2 response representations."""

from __future__ import annotations

from typing import Literal

from pydantic import AwareDatetime

from dicehub._core.rest_models import WireModel, WirePage


class TagDetail(WireModel):
    tag_id: str
    tag: str | None
    description: str | None
    rating: float | None
    tag_type: Literal["APP_TEMPLATE", "COMMUNITY_APP", "MODEL", "MODEL_TEMPLATE"] | None


class TemplateDetail(WireModel):
    template_id: str
    name: str
    slug: str
    description: str | None
    client_type: str | None
    route: str | None
    image_path: str | None
    icon_path: str | None
    template_type: Literal["APP_TEMPLATE", "MODEL_TEMPLATE"] | None
    tags: tuple[TagDetail, ...]
    created_at: AwareDatetime | None
    updated_at: AwareDatetime | None


class TemplateList(WirePage):
    items: tuple[TemplateDetail, ...]
