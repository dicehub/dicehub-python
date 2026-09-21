from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class User(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    user_id: str = Field(min_length=1, max_length=256)
    username: str = Field(min_length=1, max_length=256)


class MembershipCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    user_id: str = Field(min_length=1, max_length=256)
    username: str = Field(min_length=1, max_length=128)
