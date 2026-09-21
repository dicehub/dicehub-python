"""Bounded run polling and local result files for the car mesh example."""

from __future__ import annotations

import tempfile
from pathlib import Path

import dicehub as dh


def wait_for_run(client: dh.Client, run_id: str) -> dh.RunStatus:
    """Report state changes for up to 30 minutes; propagate timeout and read errors."""
    last_status: dh.RunStatus | None = None
    for status in client.runs.watch(run_id=run_id, timeout_seconds=1800, poll_seconds=2):
        print(f"Run {run_id}: {status.state.value}")
        last_status = status
    if last_status is None:
        raise dh.ProtocolError("Run watching returned no status.")
    if last_status.state is not dh.RunState.FINISHED:
        raise dh.RunFailedError(last_status)
    return last_status


def result_directory(root: Path) -> Path:
    """Create a private result directory named locally, independent of server data."""
    root.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix="car-mesh-", dir=root))


def download_result(client: dh.Client, run_id: str, directory: Path) -> Path:
    """Keep an interrupted download marked as partial in the new result directory."""
    destination = directory / "run-results.zip"
    if destination.exists():
        raise FileExistsError(destination)
    partial = directory / "run-results.zip.partial"
    with partial.open("xb") as stream:
        client.runs.download_results(run_id=run_id, destination=stream)
    partial.rename(destination)
    return destination
