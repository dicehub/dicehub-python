from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from dicehub._core.status import ResponseStatus

AUTH_CONTEXT_QUERY = """
query GetAuthContext {
  authentications {
    getAuthContext {
      status {
        succeeded
        error
      }
      authContext {
        identityMode
      }
    }
  }
}
"""


class AuthContextPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    identity_mode: Literal["API_KEY", "SESSION", "CLIENT_ID", "ANONYMOUS"] = Field(
        alias="identityMode"
    )


class GetAuthContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: ResponseStatus
    auth_context: AuthContextPayload | None = Field(alias="authContext")


class Authentications(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    get_auth_context: GetAuthContext = Field(alias="getAuthContext")


class AuthContextData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    authentications: Authentications
