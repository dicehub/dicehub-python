from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Literal

if TYPE_CHECKING:
    from dicehub.runs.models import RunStatus


class DiceHubError(Exception):
    """Base exception with a stable machine-readable code."""

    code: ClassVar[str] = "DICEHUB_ERROR"
    exit_code: ClassVar[int] = 1
    default_retryable: ClassVar[bool] = False

    def __init__(
        self,
        message: str,
        *,
        request_id: str | None = None,
        retryable: bool | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.request_id = request_id
        self.retryable = self.default_retryable if retryable is None else retryable

    def as_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
        }
        if self.request_id is not None:
            payload["request_id"] = self.request_id
        return payload


class ConfigurationError(DiceHubError):
    code = "CONFIGURATION_ERROR"
    exit_code = 2


class AuthenticationRequiredError(DiceHubError):
    code = "AUTH_REQUIRED"
    exit_code = 3


class AuthenticationError(DiceHubError):
    code = "AUTH_FAILED"
    exit_code = 3


class TransportError(DiceHubError):
    code = "TRANSPORT_ERROR"
    exit_code = 5
    default_retryable = True


class HTTPError(DiceHubError):
    code = "HTTP_ERROR"
    exit_code = 5

    def __init__(self, status_code: int, *, request_id: str | None = None) -> None:
        super().__init__(
            f"dicehub returned HTTP {status_code}.",
            request_id=request_id,
            retryable=status_code in {408, 429, 502, 503, 504},
        )
        self.status_code = status_code

    def as_dict(self) -> dict[str, object]:
        payload = super().as_dict()
        payload["status_code"] = self.status_code
        return payload


class GraphQLError(DiceHubError):
    code = "GRAPHQL_ERROR"
    exit_code = 4


class APIError(DiceHubError):
    code = "API_ERROR"
    exit_code = 4

    def __init__(
        self,
        message: str,
        *,
        server_code: str | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message, request_id=request_id)
        self.server_code = server_code

    def as_dict(self) -> dict[str, object]:
        payload = super().as_dict()
        if self.server_code is not None:
            payload["server_code"] = self.server_code
        return payload


class ProtocolError(DiceHubError):
    code = "PROTOCOL_ERROR"
    exit_code = 1


class SelectorResolutionError(DiceHubError):
    """A human-readable selector did not identify one record."""

    code = "SELECTOR_RESOLUTION_ERROR"
    exit_code = 4

    def __init__(
        self,
        *,
        selector: str,
        reason: Literal["NOT_FOUND", "AMBIGUOUS"],
        request_id: str | None = None,
    ) -> None:
        self.selector = selector
        self.reason = reason
        super().__init__(
            "The exact membership selector did not resolve to one authorized result.",
            request_id=request_id,
        )

    def as_dict(self) -> dict[str, object]:
        payload = super().as_dict()
        payload["selector"] = self.selector
        payload["reason"] = self.reason
        return payload


class MutationOutcomeUnknownError(DiceHubError):
    """A mutation may have completed, but dicehub did not confirm its outcome."""

    code = "MUTATION_OUTCOME_UNKNOWN"
    exit_code = 5


class RunTimeoutError(DiceHubError):
    """A run did not reach a terminal state before the caller's deadline."""

    code = "RUN_TIMEOUT"
    exit_code = 6
    default_retryable = True

    def __init__(
        self,
        *,
        run_id: str,
        timeout_seconds: float,
        last_status: RunStatus | None,
    ) -> None:
        super().__init__("The run did not reach a terminal state before the timeout.")
        self.run_id = run_id
        self.timeout_seconds = timeout_seconds
        self.last_status = last_status

    def as_dict(self) -> dict[str, object]:
        payload = super().as_dict()
        payload["run_id"] = self.run_id
        payload["timeout_seconds"] = self.timeout_seconds
        if self.last_status is not None:
            payload["last_status"] = self.last_status.model_dump(mode="json")
        return payload


class RunFailedError(DiceHubError):
    """A run reached a terminal failure state."""

    code = "RUN_FAILED"
    exit_code = 4

    def __init__(self, status: RunStatus) -> None:
        super().__init__(f"The run ended in terminal state {status.state.value}.")
        self.status = status

    def as_dict(self) -> dict[str, object]:
        payload = super().as_dict()
        payload["run_status"] = self.status.model_dump(mode="json")
        return payload
