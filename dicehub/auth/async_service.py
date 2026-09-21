from __future__ import annotations

from pydantic import ValidationError

from dicehub._core.async_graphql import AsyncGraphQLExecutor
from dicehub._core.status import raise_for_status
from dicehub.auth._graphql import AUTH_CONTEXT_QUERY, AuthContextData
from dicehub.auth.models import AuthContext, IdentityMode
from dicehub.errors import AuthenticationError, ProtocolError


class AsyncAuthService:
    def __init__(
        self,
        graphql: AsyncGraphQLExecutor,
        *,
        expected_identity_mode: IdentityMode,
    ) -> None:
        self._graphql = graphql
        self._expected_identity_mode = expected_identity_mode

    async def context(self) -> AuthContext:
        operation = await self._graphql.execute(
            operation_name="GetAuthContext",
            query=AUTH_CONTEXT_QUERY,
        )
        response: AuthContextData | None = None
        try:
            response = AuthContextData.model_validate(operation.data)
        except ValidationError:
            pass
        if response is None:
            raise ProtocolError("dicehub returned an incompatible auth-context response.")

        payload = response.authentications.get_auth_context
        raise_for_status(payload.status)
        if payload.auth_context is None:
            raise ProtocolError("dicehub returned a successful response without an auth context.")
        identity_mode = IdentityMode(payload.auth_context.identity_mode)
        if identity_mode is not self._expected_identity_mode:
            raise AuthenticationError("dicehub authentication failed.")
        return AuthContext(identity_mode=identity_mode)
