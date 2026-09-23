from __future__ import annotations

import pytest

from dicehub._core.status import ResponseStatus, raise_for_status
from dicehub.errors import APIError, AuthenticationError


def test_success_status_is_accepted() -> None:
    raise_for_status(ResponseStatus(succeeded=True))


def test_failure_without_server_error_is_generic() -> None:
    with pytest.raises(APIError) as captured:
        raise_for_status(ResponseStatus(succeeded=False))

    assert captured.value.message == "dicehub rejected the operation."
    assert captured.value.server_code is None


def test_authentication_status_uses_authentication_error() -> None:
    with pytest.raises(AuthenticationError) as captured:
        raise_for_status(ResponseStatus(succeeded=False, error="AUTH_ERROR"))

    assert captured.value.message == "dicehub authentication failed."


def test_unexpected_server_error_is_not_exposed() -> None:
    sentinel = "sentinel-server-secret"
    with pytest.raises(APIError) as captured:
        raise_for_status(ResponseStatus(succeeded=False, error=sentinel))

    assert captured.value.server_code is None
    assert sentinel not in str(captured.value)
    assert sentinel not in repr(captured.value.as_dict())
