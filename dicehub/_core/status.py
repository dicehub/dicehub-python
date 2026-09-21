from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from dicehub.errors import APIError, AuthenticationError


class ResponseStatus(BaseModel):
    """Strict private model for dicehub operation status payloads."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    succeeded: bool
    error: str | None = None


def raise_for_status(status: ResponseStatus) -> None:
    if status.succeeded:
        return
    if status.error == "AUTH_ERROR":
        raise AuthenticationError("dicehub authentication failed.")
    raise APIError("dicehub rejected the operation.")
