from __future__ import annotations

import json
from pathlib import Path
from types import TracebackType
from typing import Any, BinaryIO, ClassVar, cast

import pytest
from typer.testing import CliRunner

from dicehub import ProtocolError
from dicehub import cli as cli_module
from dicehub.cli.commands import run as run_commands

runner = CliRunner()
RUN_ID = "12345678-1234-5678-9234-567812345678"


class _FakeRuns:
    calls: ClassVar[list[str]] = []
    error_after_write: ClassVar[Exception | None] = None
    content = b"PK\x03\x04result-archive"

    def download_results(self, *, run_id: str, destination: BinaryIO) -> int:
        self.calls.append(run_id)
        destination.write(self.content)
        if self.error_after_write is not None:
            raise self.error_after_write
        return len(self.content)


class _FakeClient:
    runs = _FakeRuns()

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
    _FakeRuns.calls = []
    _FakeRuns.error_after_write = None
    monkeypatch.setattr(run_commands, "Client", _FakeClient)


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


def test_download_results_writes_explicit_destination_and_reports_bytes(tmp_path: Path) -> None:
    destination = tmp_path / "results.zip"

    result = _invoke(["run", "download-results", RUN_ID, str(destination)])

    assert result.exit_code == 0, result.output
    assert destination.read_bytes() == _FakeRuns.content
    assert _FakeRuns.calls == [RUN_ID]
    assert _json(result) == {
        "schema_version": "dicehub.cli/v1",
        "ok": True,
        "data": {
            "run_id": RUN_ID,
            "destination": str(destination),
            "bytes": len(_FakeRuns.content),
        },
        "error": None,
    }
    assert "sentinel-api-key" not in result.stdout + result.stderr


def test_download_results_refuses_existing_destination_without_overwrite(tmp_path: Path) -> None:
    destination = tmp_path / "results.zip"
    destination.write_bytes(b"existing")

    result = _invoke(["run", "download-results", RUN_ID, str(destination)])

    assert result.exit_code == 2
    assert destination.read_bytes() == b"existing"
    assert _FakeRuns.calls == []
    assert _json(result)["error"]["code"] == "CONFIGURATION_ERROR"


def test_download_results_overwrite_is_atomic_on_failure(tmp_path: Path) -> None:
    destination = tmp_path / "results.zip"
    destination.write_bytes(b"existing")
    _FakeRuns.error_after_write = ProtocolError("download failed")

    result = _invoke(["run", "download-results", RUN_ID, str(destination), "--overwrite"])

    assert result.exit_code == 1
    assert destination.read_bytes() == b"existing"
    assert list(tmp_path.glob(f".{destination.name}.*")) == []
    assert "sentinel-api-key" not in result.stdout + result.stderr


def test_download_results_removes_new_partial_file_on_failure(tmp_path: Path) -> None:
    destination = tmp_path / "results.zip"
    _FakeRuns.error_after_write = ProtocolError("download failed")

    result = _invoke(["run", "download-results", RUN_ID, str(destination)])

    assert result.exit_code == 1
    assert not destination.exists()


def test_download_results_overwrite_replaces_symlink_not_its_target(tmp_path: Path) -> None:
    target = tmp_path / "target.zip"
    target.write_bytes(b"keep-me")
    destination = tmp_path / "results.zip"
    destination.symlink_to(target)

    result = _invoke(["run", "download-results", RUN_ID, str(destination), "--overwrite"])

    assert result.exit_code == 0, result.output
    assert target.read_bytes() == b"keep-me"
    assert not destination.is_symlink()
    assert destination.read_bytes() == _FakeRuns.content


def test_download_results_requires_existing_destination_directory(tmp_path: Path) -> None:
    destination = tmp_path / "missing" / "results.zip"

    result = _invoke(["run", "download-results", RUN_ID, str(destination)])

    assert result.exit_code == 2
    assert _FakeRuns.calls == []
    assert _json(result)["error"]["code"] == "CONFIGURATION_ERROR"
