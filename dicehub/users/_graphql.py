from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from dicehub._core.status import ResponseStatus

WHO_AM_I_QUERY = """
query WhoAmI {
  users {
    me {
      status {
        succeeded
        error
      }
      user {
        userId
        username
      }
    }
  }
}
"""

SEARCH_MEMBERSHIP_CANDIDATES_QUERY = """
query SearchMembershipCandidates($namespaceId: String!, $searchFilter: String!) {
  users {
    searchMembershipCandidates(
      namespaceId: $namespaceId
      searchFilter: $searchFilter
    ) {
      status {
        succeeded
        error
      }
      candidates {
        userId
        username
      }
    }
  }
}
"""


class UserPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    user_id: str = Field(alias="userId", min_length=1, max_length=256)
    username: str = Field(min_length=1, max_length=256)


class Me(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: ResponseStatus
    user: UserPayload | None


class Users(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    me: Me


class WhoAmIData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    users: Users


def _valid_positive_id(value: str) -> bool:
    return (
        0 < len(value) <= 256 and value.isascii() and value.isdigit() and not value.startswith("0")
    )


def _valid_printable(value: str, *, max_length: int) -> bool:
    return 0 < len(value) <= max_length and all(character.isprintable() for character in value)


class MembershipCandidatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    user_id: str = Field(alias="userId", min_length=1, max_length=256)
    username: str = Field(min_length=1, max_length=128)

    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, value: str) -> str:
        if not _valid_positive_id(value):
            raise ValueError("invalid membership candidate user ID")
        return value

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        if not _valid_printable(value, max_length=128):
            raise ValueError("invalid membership candidate username")
        return value


class SearchMembershipCandidatesPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: ResponseStatus
    candidates: list[MembershipCandidatePayload] | None


class SearchMembershipCandidates(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    search_membership_candidates: SearchMembershipCandidatesPayload = Field(
        alias="searchMembershipCandidates"
    )


class SearchMembershipCandidatesData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    users: SearchMembershipCandidates
