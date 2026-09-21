from __future__ import annotations

import asyncio
import io
import json

import httpx
import pytest

from dicehub import APIError, AsyncClient, Client


@pytest.mark.parametrize("asynchronous", [False, True], ids=["sync", "async"])
@pytest.mark.parametrize("upload", [False, True], ids=["download", "upload"])
def test_file_transfer_errors_do_not_expose_unknown_server_codes(
    asynchronous: bool, upload: bool
) -> None:
    marker = "SENTINEL_PRIVATE_SERVER_DETAIL"
    destination = io.BytesIO()
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            json={"status": {"succeeded": False, "error": marker, "message": marker}},
            request=request,
        )

    async def async_transfer() -> None:
        async with AsyncClient(
            base_url="https://dicehub.test",
            api_key="test-api-key",
            transport=httpx.MockTransport(handler),
        ) as client:
            if upload:
                await client.configs.upload_file(
                    config_id="301", path="mesh/file.bin", source=io.BytesIO(b"input")
                )
            else:
                await client.configs.download_file(
                    config_id="301", path="mesh/file.bin", destination=destination
                )

    with pytest.raises(APIError) as captured:
        if asynchronous:
            asyncio.run(async_transfer())
        else:
            with Client(
                base_url="https://dicehub.test",
                api_key="test-api-key",
                transport=httpx.MockTransport(handler),
            ) as client:
                if upload:
                    client.configs.upload_file(
                        config_id="301", path="mesh/file.bin", source=io.BytesIO(b"input")
                    )
                else:
                    client.configs.download_file(
                        config_id="301", path="mesh/file.bin", destination=destination
                    )

    error = captured.value
    assert marker not in str(error)
    assert marker not in repr(error)
    assert marker not in json.dumps(error.as_dict())
    assert error.server_code is None
    assert error.__cause__ is None
    assert error.__context__ is None
    assert destination.getvalue() == b""
    assert calls == 1
