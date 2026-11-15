"""Map unconfirmed writes without retaining transport or response exceptions."""

from collections.abc import Awaitable, Callable
from functools import wraps
from typing import ParamSpec, TypeVar

from dicehub.errors import HTTPError, MutationOutcomeUnknownError, ProtocolError, TransportError

P = ParamSpec("P")
R = TypeVar("R")


def mutation_outcome(function: Callable[P, R]) -> Callable[P, R]:
    @wraps(function)
    def execute(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return function(*args, **kwargs)
        except (HTTPError, ProtocolError, TransportError) as error:
            mapped = MutationOutcomeUnknownError(
                "The mutation may have completed, but dicehub did not confirm its outcome.",
                request_id=error.request_id,
            )
        raise mapped

    return execute


def async_mutation_outcome(function: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
    @wraps(function)
    async def execute(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return await function(*args, **kwargs)
        except (HTTPError, ProtocolError, TransportError) as error:
            mapped = MutationOutcomeUnknownError(
                "The mutation may have completed, but dicehub did not confirm its outcome.",
                request_id=error.request_id,
            )
        raise mapped

    return execute
