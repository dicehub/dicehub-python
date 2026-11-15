"""Strict REST wire representations."""

from __future__ import annotations

from typing import Literal

from dicehub._core.rest_models import WireModel

AuthIdentityMode = Literal["API_KEY", "SESSION", "CLIENT_ID", "ANONYMOUS"]


class AuthContext(WireModel):
    identity_mode: AuthIdentityMode
