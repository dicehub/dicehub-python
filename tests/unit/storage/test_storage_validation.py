from __future__ import annotations

import io

import httpx
import pytest

from dicehub import Client, ConfigurationError


def _client() -> Client:
    def forbidden(request: httpx.Request) -> httpx.Response:
        raise AssertionError("Invalid storage input must fail before HTTP.")

    return Client(
        base_url="https://dicehub.test",
        api_key="test-api-key",
        transport=httpx.MockTransport(forbidden),
    )


# Resource tests cover the same imported ID/path validators; retain storage entry-point checks.
def test_transfer_rejects_invalid_namespace_id() -> None:
    with _client() as client, pytest.raises(ConfigurationError):
        client.storage.upload(
            namespace_id="01",
            path="file.bin",
            source=io.BytesIO(b"content"),
        )


@pytest.mark.parametrize("path", ["", "../escape"])
def test_transfer_rejects_unsafe_storage_paths(path: str) -> None:
    with _client() as client, pytest.raises(ConfigurationError):
        client.storage.upload(
            namespace_id="101",
            path=path,
            source=io.BytesIO(b"content"),
        )


def test_transfer_rejects_non_binary_streams_and_invalid_limits() -> None:
    with _client() as client, pytest.raises(ConfigurationError):
        client.storage.upload(
            namespace_id="101",
            path="file.bin",
            source=object(),  # type: ignore[arg-type]
        )

    with _client() as client, pytest.raises(ConfigurationError):
        client.storage.download(
            namespace_id="101",
            path="file.bin",
            destination=object(),  # type: ignore[arg-type]
        )

    for max_bytes in (0, -1, True):
        with _client() as client, pytest.raises(ConfigurationError):
            client.storage.upload(
                namespace_id="101",
                path="file.bin",
                source=io.BytesIO(b"content"),
                max_bytes=max_bytes,
            )


def test_file_helpers_require_path_like_arguments() -> None:
    with _client() as client, pytest.raises(ConfigurationError):
        client.storage.upload_file(
            namespace_id="101",
            path="file.bin",
            source_path=object(),  # type: ignore[arg-type]
        )

    with _client() as client, pytest.raises(ConfigurationError):
        client.storage.download_file(
            namespace_id="101",
            path="file.bin",
            destination_path=object(),  # type: ignore[arg-type]
        )
