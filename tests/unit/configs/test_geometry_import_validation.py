from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest
from pydantic import ValidationError

from dicehub import (
    Client,
    ConfigurationError,
    GeometryImportRuns,
    RunState,
    RunStatus,
)


def _client() -> Client:
    def forbidden(request: httpx.Request) -> httpx.Response:
        raise AssertionError("Invalid geometry import input must fail before HTTP.")

    return Client(
        base_url="https://dicehub.test",
        api_key="test-api-key",
        transport=httpx.MockTransport(forbidden),
    )


def test_import_geometry_rejects_invalid_config_id() -> None:
    with _client() as client, pytest.raises(ConfigurationError):
        client.configs.import_geometry(config_id="01", filename="cube.stl")


@pytest.mark.parametrize(
    "filename",
    [
        "",
        "cube.obj",
        "cube.STL",
        "1cube.stl",
        "cube-name.stl",
        "cube name.stl",
        "/cube.stl",
        "geometry/cube.stl",
        "../cube.stl",
        "cube\\.stl",
        "cube.stl/",
        "cube\n.stl",
        "x" * 252 + ".stl",
    ],
)
def test_import_geometry_rejects_non_stl_or_non_basename(filename: str) -> None:
    with _client() as client, pytest.raises(ConfigurationError):
        client.configs.import_geometry(config_id="301", filename=filename)


def test_geometry_import_runs_is_frozen_and_allows_no_later_setup() -> None:
    conversion = RunStatus(
        run_id="12345678-1234-5678-9234-567812345678",
        state=RunState.PREPARING,
        execution_status=None,
        error=None,
        flags=(),
        updated_at=datetime(2026, 8, 14, tzinfo=timezone.utc),
    )
    result = GeometryImportRuns(conversion_run=conversion, setup_run=None)

    assert result.setup_run is None
    with pytest.raises(ValidationError):
        result.setup_run = conversion
