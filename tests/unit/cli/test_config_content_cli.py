from __future__ import annotations

import json
from pathlib import Path
from types import TracebackType
from typing import Any, BinaryIO, ClassVar, cast

import pytest
from typer.testing import CliRunner

from dicehub import (
    ConfigContentArea,
    ConfigContentEntry,
    ConfigContentPage,
    ConfigContentType,
)
from dicehub import cli as cli_module
from dicehub.cli.commands import config as config_commands
from dicehub.projects import SortOrder

runner = CliRunner()


class _FakeConfigs:
    calls: ClassVar[list[tuple[str, dict[str, object]]]] = []
    file_content = b"downloaded-file"

    def update(
        self,
        *,
        config_id: str,
        name: str | None = None,
        description: str | None = None,
    ) -> None:
        self.calls.append(
            (
                "update",
                {"config_id": config_id, "name": name, "description": description},
            )
        )

    def list_content(
        self,
        *,
        config_id: str,
        area: ConfigContentArea,
        path: str = "",
        recursive: bool = False,
        order: SortOrder = SortOrder.ASC,
        offset: int = 0,
        limit: int = 20,
        cursor: str | None = None,
    ) -> ConfigContentPage:
        self.calls.append(
            (
                "list_content",
                {
                    "config_id": config_id,
                    "area": area,
                    "path": path,
                    "recursive": recursive,
                    "offset": offset,
                    "limit": limit,
                    "cursor": cursor,
                },
            )
        )
        return ConfigContentPage(
            entries=(
                ConfigContentEntry(
                    path="boundary/inlet.yaml",
                    resource_type=ConfigContentType.TEXT,
                ),
            ),
            offset=offset,
            count=1,
            cursor="next",
        )

    def get_text(self, *, config_id: str, path: str) -> str:
        self.calls.append(("get_text", {"config_id": config_id, "path": path}))
        return "value: 7\n"

    def set_text(self, *, config_id: str, path: str, content: str) -> None:
        self.calls.append(
            (
                "set_text",
                {"config_id": config_id, "path": path, "content": content},
            )
        )

    def delete_content(
        self,
        *,
        config_id: str,
        area: ConfigContentArea,
        path: str,
    ) -> None:
        self.calls.append(
            (
                "delete_content",
                {"config_id": config_id, "area": area, "path": path},
            )
        )

    def upload_file(
        self,
        *,
        config_id: str,
        path: str,
        source: BinaryIO,
    ) -> None:
        self.calls.append(
            (
                "upload_file",
                {"config_id": config_id, "path": path, "content": source.read()},
            )
        )

    def download_file(
        self,
        *,
        config_id: str,
        path: str,
        destination: BinaryIO,
    ) -> int:
        destination.write(self.file_content)
        self.calls.append(("download_file", {"config_id": config_id, "path": path}))
        return len(self.file_content)


class _FakeClient:
    configs = _FakeConfigs()

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None = None,
        session_cookie: str | None = None,
    ) -> None:
        pass

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
    _FakeConfigs.calls = []
    monkeypatch.setattr(config_commands, "Client", _FakeClient)


def _invoke(arguments: list[str]) -> Any:
    return runner.invoke(
        cli_module.app,
        arguments,
        env={
            "DICEHUB_API_KEY": "sentinel-api-key",
            "DICEHUB_URL": "https://dicehub.test",
        },
    )


def _json(result: Any) -> dict[str, Any]:
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    return cast(dict[str, Any], payload)


def test_update_and_content_list_route_exact_values() -> None:
    update = _invoke(
        [
            "config",
            "update",
            "301",
            "--name",
            "Renamed",
            "--description",
            "Automated",
        ]
    )
    listed = _invoke(
        [
            "config",
            "content",
            "list",
            "301",
            "--area",
            "texts",
            "--path",
            "boundary",
            "--recursive",
        ]
    )

    assert update.exit_code == listed.exit_code == 0
    assert _FakeConfigs.calls == [
        (
            "update",
            {"config_id": "301", "name": "Renamed", "description": "Automated"},
        ),
        (
            "list_content",
            {
                "config_id": "301",
                "area": ConfigContentArea.TEXTS,
                "path": "boundary",
                "recursive": True,
                "offset": 0,
                "limit": 20,
                "cursor": None,
            },
        ),
    ]
    assert _json(listed)["data"]["entries"] == [
        {"path": "boundary/inlet.yaml", "resource_type": "TEXT"}
    ]


def test_text_get_set_and_confirmed_delete(tmp_path: Path) -> None:
    source = tmp_path / "input.yaml"
    source.write_text("value: 8\n", encoding="utf-8")

    read = _invoke(["config", "content", "get-text", "301", "input.yaml"])
    written = _invoke(["config", "content", "set-text", "301", "input.yaml", str(source)])
    refused = _invoke(["config", "content", "delete", "301", "input.yaml", "--area", "texts"])
    deleted = _invoke(
        [
            "config",
            "content",
            "delete",
            "301",
            "input.yaml",
            "--area",
            "texts",
            "--yes",
        ]
    )

    assert read.exit_code == written.exit_code == deleted.exit_code == 0
    assert _json(read)["data"]["content"] == "value: 7\n"
    assert refused.exit_code == 2
    assert _json(refused)["error"]["code"] == "CONFIGURATION_ERROR"
    assert _FakeConfigs.calls == [
        ("get_text", {"config_id": "301", "path": "input.yaml"}),
        (
            "set_text",
            {"config_id": "301", "path": "input.yaml", "content": "value: 8\n"},
        ),
        (
            "delete_content",
            {
                "config_id": "301",
                "area": ConfigContentArea.TEXTS,
                "path": "input.yaml",
            },
        ),
    ]


def test_file_upload_and_atomic_download(tmp_path: Path) -> None:
    source = tmp_path / "source.bin"
    source.write_bytes(b"uploaded-file")
    destination = tmp_path / "destination.bin"

    uploaded = _invoke(["config", "content", "upload", "301", "mesh/input.bin", str(source)])
    downloaded = _invoke(
        [
            "config",
            "content",
            "download",
            "301",
            "mesh/output.bin",
            str(destination),
        ]
    )
    refused = _invoke(
        [
            "config",
            "content",
            "download",
            "301",
            "mesh/output.bin",
            str(destination),
        ]
    )

    assert uploaded.exit_code == downloaded.exit_code == 0
    assert _json(uploaded)["data"]["bytes"] == len(b"uploaded-file")
    assert destination.read_bytes() == b"downloaded-file"
    assert refused.exit_code == 2
    assert _json(refused)["error"]["code"] == "CONFIGURATION_ERROR"
    assert _FakeConfigs.calls == [
        (
            "upload_file",
            {
                "config_id": "301",
                "path": "mesh/input.bin",
                "content": b"uploaded-file",
            },
        ),
        (
            "download_file",
            {"config_id": "301", "path": "mesh/output.bin"},
        ),
    ]
