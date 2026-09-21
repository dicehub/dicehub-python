from __future__ import annotations

from pathlib import Path
from types import TracebackType
from typing import BinaryIO, cast

import pytest

import dicehub as dh
from examples import controlled_cube_workflow, download_run_results


class _Runs:
    def __init__(self, error: BaseException) -> None:
        self.error = error

    def download_results(
        self,
        *,
        run_id: str,
        destination: BinaryIO,
        max_bytes: int | None = None,
    ) -> int:
        del run_id, max_bytes
        destination.write(b"partial")
        raise self.error


class _Client:
    def __init__(self, error: BaseException) -> None:
        self.runs = _Runs(error)

    def __enter__(self) -> _Client:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc_value, traceback


@pytest.mark.parametrize(
    "error",
    [dh.TransportError("Transfer failed."), KeyboardInterrupt()],
)
def test_download_example_removes_partial_final_file(
    error: BaseException,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "result.zip"
    client = _Client(error)
    monkeypatch.setenv("DICEHUB_API_KEY", "sentinel-key")
    monkeypatch.setenv("DICEHUB_RUN_ID", "12345678-1234-5678-9234-567812345678")
    monkeypatch.setenv("DICEHUB_RUN_RESULTS_DESTINATION", str(destination))
    monkeypatch.setattr(dh, "Client", lambda **_kwargs: client)

    with pytest.raises(type(error)):
        download_run_results.main()

    assert not destination.exists()


@pytest.mark.parametrize(
    "error",
    [dh.TransportError("Transfer failed."), KeyboardInterrupt()],
)
def test_controlled_cube_removes_partial_final_file(
    error: BaseException,
    tmp_path: Path,
) -> None:
    destination = tmp_path / "result.zip"

    with pytest.raises(type(error)):
        controlled_cube_workflow._download_results(
            cast(dh.Client, _Client(error)),
            "12345678-1234-5678-9234-567812345678",
            destination,
        )

    assert not destination.exists()


def test_download_examples_preserve_existing_destinations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "result.zip"
    destination.write_bytes(b"existing")
    monkeypatch.setenv("DICEHUB_API_KEY", "sentinel-key")
    monkeypatch.setenv("DICEHUB_RUN_ID", "12345678-1234-5678-9234-567812345678")
    monkeypatch.setenv("DICEHUB_RUN_RESULTS_DESTINATION", str(destination))

    with pytest.raises(SystemExit, match="already exists"):
        download_run_results.main()
    with pytest.raises(FileExistsError):
        controlled_cube_workflow._download_results(
            cast(dh.Client, _Client(AssertionError("must not download"))),
            "12345678-1234-5678-9234-567812345678",
            destination,
        )

    assert destination.read_bytes() == b"existing"
