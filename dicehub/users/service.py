from __future__ import annotations

from pydantic import ValidationError

from dicehub._core.graphql import GraphQLExecutor
from dicehub._core.status import raise_for_status
from dicehub.errors import ProtocolError, SelectorResolutionError
from dicehub.users._graphql import (
    SEARCH_MEMBERSHIP_CANDIDATES_QUERY,
    WHO_AM_I_QUERY,
    MembershipCandidatePayload,
    SearchMembershipCandidatesData,
    WhoAmIData,
)
from dicehub.users._validation import validated_namespace_id, validated_username
from dicehub.users.models import MembershipCandidate, User


class UsersService:
    def __init__(self, graphql: GraphQLExecutor) -> None:
        self._graphql = graphql

    def me(self) -> User:
        result = self._graphql.execute(
            operation_name="WhoAmI",
            query=WHO_AM_I_QUERY,
        )
        response: WhoAmIData | None = None
        try:
            response = WhoAmIData.model_validate(result.data)
        except ValidationError:
            pass
        if response is None:
            raise ProtocolError("dicehub returned an incompatible whoami response.")

        raise_for_status(response.users.me.status)
        if response.users.me.user is None:
            raise ProtocolError("dicehub returned a successful response without a user.")
        return User(
            user_id=response.users.me.user.user_id,
            username=response.users.me.user.username,
        )

    def resolve_membership_candidate(
        self,
        *,
        namespace_id: str,
        username: str,
    ) -> MembershipCandidate:
        valid_namespace_id = validated_namespace_id(namespace_id)
        valid_username = validated_username(username)
        result = self._graphql.execute(
            operation_name="SearchMembershipCandidates",
            query=SEARCH_MEMBERSHIP_CANDIDATES_QUERY,
            variables={
                "namespaceId": valid_namespace_id,
                "searchFilter": valid_username,
            },
        )
        response = _validated_response(result.data)
        payload = response.users.search_membership_candidates
        raise_for_status(payload.status)
        if payload.candidates is None:
            raise ProtocolError(
                "dicehub returned a successful response without membership candidates."
            )

        matches = tuple(
            candidate
            for candidate in payload.candidates
            if candidate.username.casefold() == valid_username.casefold()
        )
        if len(matches) != 1:
            raise SelectorResolutionError(
                selector="username",
                reason="NOT_FOUND" if not matches else "AMBIGUOUS",
            )
        return _candidate_from_payload(matches[0])


def _validated_response(data: dict[str, object]) -> SearchMembershipCandidatesData:
    response: SearchMembershipCandidatesData | None = None
    try:
        response = SearchMembershipCandidatesData.model_validate(data)
    except ValidationError:
        pass
    if response is None:
        raise ProtocolError("dicehub returned an incompatible membership candidate response.")
    return response


def _candidate_from_payload(payload: MembershipCandidatePayload) -> MembershipCandidate:
    return MembershipCandidate(
        user_id=payload.user_id,
        username=payload.username,
    )
