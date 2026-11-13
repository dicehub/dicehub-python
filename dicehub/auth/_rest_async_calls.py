"""Read and verify the selected credential identity."""

from __future__ import annotations

import dicehub.auth._rest_models as wire_models
from dicehub._core.rest_request import async_request as request
from dicehub._core.rest_v2 import AsyncRestV2Executor
from dicehub.auth.models import AuthContext, IdentityMode
from dicehub.errors import AuthenticationError


async def context(rest: AsyncRestV2Executor, expected_identity_mode: IdentityMode) -> AuthContext:
    wire = await request(rest, wire_models.AuthContext, method="GET", path="api/v2/auth/context")
    identity = IdentityMode(wire.identity_mode)
    if identity is not expected_identity_mode:
        raise AuthenticationError("dicehub authentication failed.")
    return AuthContext(identity_mode=identity)
