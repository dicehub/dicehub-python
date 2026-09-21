from __future__ import annotations

import json
from pathlib import Path
from types import TracebackType
from typing import Any, ClassVar, cast

import pytest
from pydantic import BaseModel
from typer.testing import CliRunner

from dicehub import cli as cli_module
from dicehub.cli.commands import resource as resource_commands
from dicehub.resources import Resource, ResourcePage, ResourceType
from dicehub.storage import DownloadReceipt, UploadReceipt

runner = CliRunner()
RESOURCE_ID = "12345678-1234-5678-9234-567812345678"
NAMESPACE_ID = "101"
SHA256 = "a" * 64
_MISSING = object()


def _resource() -> Resource:
    return Resource(
        resource_id=RESOURCE_ID,
        namespace_id=NAMESPACE_ID,
        key="data/meshes/cube.stl",
        resource_type=ResourceType.FILE,
    )


def _page(*, offset: int) -> ResourcePage:
    return ResourcePage(resources=(_resource(),), offset=offset, count=1, cursor="next")


class _UnsafeResource(BaseModel):
    resource_id: str
    namespace_id: str
    key: str
    resource_type: str


class _FakeResources:
    calls: ClassVar[list[tuple[str, dict[str, object]]]] = []
    get_result: ClassVar[BaseModel] = _resource()

    def list(
        self,
        *,
        namespace_id: str,
        path: str,
        resource_type: ResourceType | None,
        recursive: bool,
        offset: int,
        limit: int,
        cursor: str | None,
    ) -> ResourcePage:
        self.calls.append(
            (
                "list",
                {
                    "namespace_id": namespace_id,
                    "path": path,
                    "resource_type": resource_type,
                    "recursive": recursive,
                    "offset": offset,
                    "limit": limit,
                    "cursor": cursor,
                },
            )
        )
        return _page(offset=offset)

    def get(self, *, resource_id: str) -> Resource:
        self.calls.append(("get", {"resource_id": resource_id}))
        return cast(Resource, self.get_result)

    def delete(self, *, resource_id: str) -> None:
        self.calls.append(("delete", {"resource_id": resource_id}))


class _FakeStorage:
    calls: ClassVar[list[tuple[str, dict[str, object]]]] = []

    def upload_file(
        self,
        *,
        namespace_id: str,
        path: str,
        source_path: Path,
        max_bytes: object = _MISSING,
    ) -> UploadReceipt:
        arguments: dict[str, object] = {
            "namespace_id": namespace_id,
            "path": path,
            "source_path": source_path,
        }
        if max_bytes is not _MISSING:
            arguments["max_bytes"] = max_bytes
        self.calls.append(("upload_file", arguments))
        return UploadReceipt(
            namespace_id=namespace_id,
            path=path,
            bytes_sent=12,
            sha256=SHA256,
            server_verified=True,
        )

    def download_file(
        self,
        *,
        namespace_id: str,
        path: str,
        destination_path: Path,
        overwrite: bool,
        max_bytes: object = _MISSING,
    ) -> DownloadReceipt:
        arguments: dict[str, object] = {
            "namespace_id": namespace_id,
            "path": path,
            "destination_path": destination_path,
            "overwrite": overwrite,
        }
        if max_bytes is not _MISSING:
            arguments["max_bytes"] = max_bytes
        self.calls.append(("download_file", arguments))
        return DownloadReceipt(
            namespace_id=namespace_id,
            path=path,
            bytes_received=12,
            sha256=SHA256,
            server_verified=True,
        )


class _FakeClient:
    resources = _FakeResources()
    storage = _FakeStorage()
    constructions: ClassVar[list[dict[str, object]]] = []

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None = None,
        session_cookie: str | None = None,
    ) -> None:
        self.constructions.append(
            {
                "base_url": base_url,
                "api_key": api_key,
                "session_cookie": session_cookie,
            }
        )

    def __enter__(self) -> _FakeClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None


@pytest.fixture(autouse=True)
def reset_fakes(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeResources.calls = []
    _FakeResources.get_result = _resource()
    _FakeStorage.calls = []
    _FakeClient.constructions = []
    for name in ("DICEHUB_API_KEY", "DICEHUB_SESSION_COOKIE", "DICEHUB_URL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(resource_commands, "Client", _FakeClient)


def _api_key_environment() -> dict[str, str]:
    return {
        "DICEHUB_API_KEY": "sentinel-api-key",
        "DICEHUB_URL": "https://dicehub.test",
    }


def _invoke(arguments: list[str], environment: dict[str, str] | None = None) -> Any:
    return runner.invoke(
        cli_module.app,
        arguments,
        env=_api_key_environment() if environment is None else environment,
    )


def _json(result: Any) -> dict[str, Any]:
    assert result.stderr == ""
    assert result.stdout.count("\n") == 1
    payload = json.loads(result.stdout)
    assert isinstance(payload, dict)
    return cast(dict[str, Any], payload)


def test_list_and_get_emit_clean_json_and_forward_exact_values() -> None:
    listed = _invoke(
        [
            "resource",
            "list",
            NAMESPACE_ID,
            "--path",
            "meshes",
            "--type",
            "file",
            "--recursive",
            "--offset",
            "2",
            "--limit",
            "5",
            "--cursor",
            "opaque",
        ]
    )
    fetched = _invoke(["resource", "get", RESOURCE_ID])

    assert listed.exit_code == fetched.exit_code == 0
    assert _FakeResources.calls == [
        (
            "list",
            {
                "namespace_id": NAMESPACE_ID,
                "path": "meshes",
                "resource_type": ResourceType.FILE,
                "recursive": True,
                "offset": 2,
                "limit": 5,
                "cursor": "opaque",
            },
        ),
        ("get", {"resource_id": RESOURCE_ID}),
    ]
    assert _json(listed) == {
        "schema_version": "dicehub.cli/v1",
        "ok": True,
        "data": {
            "resources": [_resource().model_dump(mode="json")],
            "page": {"offset": 2, "count": 1, "cursor": "next"},
        },
        "error": None,
    }
    assert _json(fetched) == {
        "schema_version": "dicehub.cli/v1",
        "ok": True,
        "data": {"resource": _resource().model_dump(mode="json")},
        "error": None,
    }
    assert "sentinel-api-key" not in listed.stdout + listed.stderr + fetched.stdout + fetched.stderr


@pytest.mark.parametrize(
    ("credential_name", "credential_value", "client_field"),
    [
        ("DICEHUB_API_KEY", "sentinel-api-key", "api_key"),
        ("DICEHUB_SESSION_COOKIE", "sentinel-session-cookie", "session_cookie"),
    ],
)
def test_resource_commands_accept_api_key_or_session_cookie(
    credential_name: str,
    credential_value: str,
    client_field: str,
) -> None:
    result = _invoke(
        ["resource", "get", RESOURCE_ID],
        environment={credential_name: credential_value, "DICEHUB_URL": "https://dicehub.test"},
    )

    assert result.exit_code == 0, result.output
    assert _FakeClient.constructions == [
        {
            "base_url": "https://dicehub.test",
            "api_key": credential_value if client_field == "api_key" else None,
            "session_cookie": credential_value if client_field == "session_cookie" else None,
        }
    ]
    assert _json(result)["data"]["resource"] == _resource().model_dump(mode="json")


def test_upload_and_download_route_receipts_with_exact_parameters(tmp_path: Path) -> None:
    source = tmp_path / "cube.stl"
    source.write_bytes(b"mesh")
    destination = tmp_path / "downloaded.stl"

    uploaded = _invoke(["resource", "upload", NAMESPACE_ID, "meshes/cube.stl", str(source)])
    downloaded = _invoke(
        [
            "resource",
            "download",
            NAMESPACE_ID,
            "meshes/cube.stl",
            str(destination),
            "--overwrite",
            "--max-bytes",
            "4096",
        ]
    )

    assert uploaded.exit_code == downloaded.exit_code == 0
    assert _FakeStorage.calls == [
        (
            "upload_file",
            {
                "namespace_id": NAMESPACE_ID,
                "path": "meshes/cube.stl",
                "source_path": source,
            },
        ),
        (
            "download_file",
            {
                "namespace_id": NAMESPACE_ID,
                "path": "meshes/cube.stl",
                "destination_path": destination,
                "overwrite": True,
                "max_bytes": 4096,
            },
        ),
    ]
    assert _json(uploaded)["data"]["upload"] == {
        "namespace_id": NAMESPACE_ID,
        "path": "meshes/cube.stl",
        "sha256": SHA256,
        "server_verified": True,
        "bytes_sent": 12,
    }
    assert _json(downloaded)["data"]["download"] == {
        "namespace_id": NAMESPACE_ID,
        "path": "meshes/cube.stl",
        "sha256": SHA256,
        "server_verified": True,
        "bytes_received": 12,
    }


def test_delete_requires_yes_before_client_construction() -> None:
    refused = _invoke(["resource", "delete", RESOURCE_ID])

    assert refused.exit_code == 2
    assert _FakeClient.constructions == []
    assert _FakeResources.calls == []
    assert _json(refused) == {
        "schema_version": "dicehub.cli/v1",
        "ok": False,
        "data": None,
        "error": {
            "code": "CONFIGURATION_ERROR",
            "message": "Resource deletion requires --yes.",
            "retryable": False,
        },
    }

    confirmed = _invoke(["resource", "delete", RESOURCE_ID, "--yes"])

    assert confirmed.exit_code == 0
    assert _FakeResources.calls == [("delete", {"resource_id": RESOURCE_ID})]
    assert _json(confirmed)["data"] == {"resource_id": RESOURCE_ID}


def test_text_output_escapes_untrusted_resource_fields() -> None:
    _FakeResources.get_result = _UnsafeResource(
        resource_id=f"{RESOURCE_ID}\n",
        namespace_id="101\t",
        key="data/unsafe\x1b]8;;spoof\x07",
        resource_type="FILE\r",
    )

    result = _invoke(["resource", "get", RESOURCE_ID, "--output", "text"])

    assert result.exit_code == 0
    assert result.stdout == (f"{RESOURCE_ID}\\n\t101\\t\tdata/unsafe\\x1b]8;;spoof\\x07\tFILE\\r\n")
    assert "\x1b" not in result.stdout
    assert result.stdout.count("\n") == 1


@pytest.mark.parametrize(
    ("option", "value"),
    [
        ("--api-key", "sentinel-api-key"),
        ("--session-cookie", "sentinel-session-cookie"),
        ("--url", "https://attacker.test"),
    ],
)
def test_credentials_and_url_are_not_command_arguments(option: str, value: str) -> None:
    result = _invoke(
        ["resource", "get", RESOURCE_ID, option, value],
        environment=_api_key_environment(),
    )

    assert result.exit_code == 2
    assert _FakeClient.constructions == []
    assert _FakeResources.calls == []
    assert value not in result.stdout + result.stderr + repr(result.exception)
