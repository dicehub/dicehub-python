from __future__ import annotations

import re
from typing import TypeVar

from dicehub._core import validation as _shared
from dicehub._core.membership import MembershipVisibility
from dicehub.errors import ConfigurationError
from dicehub.projects.models import ProjectOrderField, ProjectVisibility, SortOrder

_SLUG_PATTERN = re.compile(r"[A-Za-z0-9_-]{3,128}")

EnumT = TypeVar(
    "EnumT",
    ProjectOrderField,
    ProjectVisibility,
    SortOrder,
    MembershipVisibility,
)


def validated_optional_id(value: str | None, label: str) -> str | None:
    return _shared.validated_optional_id(value, label)


def validated_id(value: str, label: str) -> str:
    return _shared.validated_id(value, label)


def validated_name(value: str) -> str:
    return _shared.validated_name(value, "Project", min_length=3)


def validated_role_name(value: str) -> str:
    return _shared.validated_role_name(value, "Project")


def validated_slug(value: str) -> str:
    if not isinstance(value, str) or _SLUG_PATTERN.fullmatch(value) is None:
        raise ConfigurationError(
            "Project slug must be 3 to 128 ASCII letters, digits, underscores, or hyphens."
        )
    return value


def validated_route(value: str) -> str:
    return _shared.validated_route(value, "Project")


def validated_description(value: str | None) -> str | None:
    return _shared.validated_description(value, "Project")


def validated_enum(value: EnumT, expected_type: type[EnumT], label: str) -> EnumT:
    return _shared.validated_enum(value, expected_type, label)


def validated_search_filter(value: str | None) -> str | None:
    return _shared.validated_search_filter(value, "Project")


def validated_page_size(value: int) -> int:
    return _shared.validated_page_size(value, "Project")


def validated_offset(value: int) -> int:
    return _shared.validated_offset(value, "Project")


def validated_cursor(value: str | None) -> str | None:
    return _shared.validated_cursor(value, "Project")
