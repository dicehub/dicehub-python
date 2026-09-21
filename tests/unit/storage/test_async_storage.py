from __future__ import annotations

import asyncio
import hashlib
import io
from pathlib import Path

import httpx
import pytest

from dicehub import AsyncClient, ProtocolError


def test_async_storage_upload_preserves_receipt() -> None:
    content = b"async storage content"

    async def handler(request: httpx.Request) -> httpx.Response:
        assert await request.aread() == content
        return httpx.Response(
            200,
            json={"status": {"succeeded": True, "error": None}},
            request=request,
        )

    async def scenario() -> None:
        async with AsyncClient(
            base_url="https://dicehub.test",
            api_key="test-api-key",
            transport=httpx.MockTransport(handler),
        ) as client:
            receipt = await client.storage.upload(
                namespace_id="42",
                path="mesh/result.bin",
                source=io.BytesIO(content),
            )
            assert receipt.bytes_sent == len(content)
            assert receipt.sha256 == hashlib.sha256(content).hexdigest()

    asyncio.run(scenario())


def test_async_storage_file_download_is_atomic(tmp_path: Path) -> None:
    destination = tmp_path / "result.bin"

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"content",
            headers={"Content-Type": "application/octet-stream"},
            request=request,
        )

    async def scenario() -> None:
        async with AsyncClient(
            base_url="https://dicehub.test",
            api_key="test-api-key",
            transport=httpx.MockTransport(handler),
        ) as client:
            with pytest.raises(ProtocolError):
                await client.storage.download_file(
                    namespace_id="42",
                    path="mesh/result.bin",
                    destination_path=destination,
                    max_bytes=3,
                )

    asyncio.run(scenario())

    assert not destination.exists()
    assert list(tmp_path.iterdir()) == []
