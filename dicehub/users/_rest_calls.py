"""Fixed profile and membership-candidate reads."""

from __future__ import annotations

import dicehub.users._rest_models as wire_models
from dicehub._core.rest_models import convert, identifier
from dicehub._core.rest_request import request
from dicehub._core.rest_v2 import RestV2Executor
from dicehub.errors import SelectorResolutionError
from dicehub.users.models import MembershipCandidate, User


def me(rest: RestV2Executor) -> User:
    wire = request(rest, wire_models.UserResult, method="GET", path="api/v2/users/me")
    return convert(User, wire.user, ("user_id", "username"))


def resolve_membership_candidate(
    rest: RestV2Executor, namespace_id: str, username: str
) -> MembershipCandidate:
    path = f"api/v2/namespaces/{identifier(namespace_id)}/membership-candidates"
    wire = request(
        rest, wire_models.CandidateList, method="GET", path=path, params={"search": username}
    )
    matches = tuple(item for item in wire.items if item.username.casefold() == username.casefold())
    if len(matches) != 1:
        raise SelectorResolutionError(
            selector="username", reason="NOT_FOUND" if not matches else "AMBIGUOUS"
        )
    return convert(MembershipCandidate, matches[0], ("user_id", "username"))
