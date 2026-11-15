"""Strict REST wire representations."""

from __future__ import annotations

from typing import Literal

from pydantic import AwareDatetime

from dicehub._core.rest_models import WireModel


class UserDetail(WireModel):
    user_id: str
    username: str
    first_name: str
    last_name: str
    avatar_url: str | None
    email: str | None
    visibility: Literal["INTERNAL", "PRIVATE", "PUBLIC"]
    password_changed_at: AwareDatetime | None
    timezone: str | None
    date_format: str | None
    time_format: int | None
    language: str | None
    location: str | None
    confirmed: bool
    avatar_type: Literal["REGULAR", "GRAVATAR"]
    is_admin: bool
    is_blocked: bool
    created_at: AwareDatetime
    updated_at: AwareDatetime


class UserProfile(WireModel):
    user_id: str
    username: str
    first_name: str
    last_name: str
    avatar_url: str | None


class UserResult(WireModel):
    user: UserDetail | UserProfile


class CandidateList(WireModel):
    items: tuple[UserProfile, ...]
