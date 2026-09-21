from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict


class IdentityMode(str, Enum):
    API_KEY = "API_KEY"
    SESSION = "SESSION"
    CLIENT_ID = "CLIENT_ID"
    ANONYMOUS = "ANONYMOUS"


class AuthContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    identity_mode: IdentityMode
