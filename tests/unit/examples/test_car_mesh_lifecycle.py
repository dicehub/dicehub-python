from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, cast

import pytest

import dicehub as dh
from examples.car_mesh.lifecycle import download_result, result_directory, wait_for_run


class _Runs:
    fail_download = False
    seen_run_id: str | None = None

    def __init__(self) -> None:
        self.statuses: tuple[dh.RunStatus, ...] = ()

    def download_results(self, *, run_id: str, destination: BinaryIO) -> int:
        self.seen_run_id = run_id
        destination.write(b"result")
        if self.fail_download:
            raise dh.TransportError("Transfer failed.")
        return 6

    def watch(
        self, *, run_id: str, timeout_seconds: float, poll_seconds: float
    ) -> Iterator[dh.RunStatus]:
        assert timeout_seconds == 1800
        assert poll_seconds == 2
        if self.statuses:
            yield from self.statuses
            return
        raise dh.RunTimeoutError(run_id=run_id, timeout_seconds=timeout_seconds, last_status=None)


class _Client:
    def __init__(self) -> None:
        self.runs = _Runs()


def test_result_path_does_not_use_server_run_id(tmp_path: Path) -> None:
    client = _Client()
    directory = result_directory(tmp_path)
    destination = download_result(cast(dh.Client, client), "../../server-value", directory)

    assert destination.parent == directory
    assert directory.parent == tmp_path
    assert destination.read_bytes() == b"result"
    assert client.runs.seen_run_id == "../../server-value"
    assert not (directory / "run-results.zip.partial").exists()


def test_interrupted_result_stays_partial(tmp_path: Path) -> None:
    client = _Client()
    client.runs.fail_download = True

    with pytest.raises(dh.TransportError):
        download_result(cast(dh.Client, client), "run", tmp_path)

    assert not (tmp_path / "run-results.zip").exists()
    assert (tmp_path / "run-results.zip.partial").read_bytes() == b"result"
    with pytest.raises(FileExistsError):
        download_result(cast(dh.Client, client), "run", tmp_path)


def test_existing_result_is_preserved(tmp_path: Path) -> None:
    client = _Client()
    destination = tmp_path / "run-results.zip"
    destination.write_bytes(b"previous")

    with pytest.raises(FileExistsError):
        download_result(cast(dh.Client, client), "run", tmp_path)

    assert destination.read_bytes() == b"previous"
    assert client.runs.seen_run_id is None


def test_wait_keeps_the_sdk_timeout() -> None:
    with pytest.raises(dh.RunTimeoutError):
        wait_for_run(cast(dh.Client, _Client()), "run")


def test_wait_raises_when_run_ends_without_success() -> None:
    client = _Client()
    client.runs.statuses = (
        dh.RunStatus(
            run_id="12345678-1234-5678-9234-567812345678",
            state=dh.RunState.FAILED,
            execution_status=dh.RunExecutionStatus.FAILED,
            error=dh.RunError.PROCESSING_FAILED,
            flags=(),
            updated_at=datetime(2026, 9, 19, tzinfo=timezone.utc),
        ),
    )

    with pytest.raises(dh.RunFailedError):
        wait_for_run(cast(dh.Client, client), "run")
