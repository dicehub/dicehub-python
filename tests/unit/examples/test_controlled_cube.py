from __future__ import annotations

import zipfile
from collections import Counter
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

import pytest

import dicehub as dh
from examples import controlled_cube_workflow
from examples._controlled_cube import (
    CUBE_STL,
    ControlledCubeError,
    validate_result_archive,
    wait_for_finished,
    wait_for_terminal,
)

RUN_ID = "12345678-1234-5678-9234-567812345678"
Vertex = tuple[float, float, float]
Triangle = tuple[Vertex, Vertex, Vertex]


def _status(state: dh.RunState) -> dh.RunStatus:
    return dh.RunStatus(
        run_id=RUN_ID,
        state=state,
        execution_status=None,
        error=None,
        flags=(),
        updated_at=datetime(2026, 8, 12, tzinfo=timezone.utc),
    )


def _write_archive(path: Path, entries: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)


def _cube_triangles() -> list[Triangle]:
    vertices = [
        cast(Vertex, tuple(float(value) for value in line.split()[1:]))
        for line in CUBE_STL.decode("ascii").splitlines()
        if line.strip().startswith("vertex ")
    ]
    return [
        (vertices[index], vertices[index + 1], vertices[index + 2])
        for index in range(0, len(vertices), 3)
    ]


def test_cube_is_deterministic_closed_unit_surface() -> None:
    triangles = _cube_triangles()

    assert len(triangles) == 12
    assert {
        coordinate for triangle in triangles for vertex in triangle for coordinate in vertex
    } == {
        0.0,
        1.0,
    }
    edges: Counter[tuple[Vertex, Vertex]] = Counter()
    for triangle in triangles:
        for start, end in zip(triangle, (*triangle[1:], triangle[0]), strict=True):
            edge = (start, end) if start < end else (end, start)
            edges[edge] += 1
    assert set(edges.values()) == {2}


class _FakeTemplates:
    def __init__(self, template: dh.Template | None) -> None:
        self.template = template
        self.routes: list[str] = []

    def get_by_route(self, *, route: str) -> dh.Template | None:
        self.routes.append(route)
        return self.template


class _TemplateClient:
    def __init__(self, template: dh.Template | None) -> None:
        self.templates = _FakeTemplates(template)


def _snappy_template(*, route: str = "/templates/openfoam_snappyhexmesh") -> dh.Template:
    return dh.Template(
        template_id="12",
        name="Hex-dominant meshing (OpenFOAM)",
        slug="openfoam_snappyhexmesh",
        description="Hexahedral meshing",
        client_type="openfoam",
        route=route,
        image_path=None,
        icon_path=None,
        tags=(),
        created_at=None,
        updated_at=None,
    )


def test_example_resolves_stable_route_to_deployment_specific_id() -> None:
    client = _TemplateClient(_snappy_template())

    template = controlled_cube_workflow._snappy_template(client)  # type: ignore[arg-type]

    assert client.templates.routes == ["/templates/openfoam_snappyhexmesh"]
    assert template.template_id == "12"


@pytest.mark.parametrize(
    "template",
    [None, _snappy_template(route="/templates/different")],
)
def test_example_rejects_missing_or_mismatched_snappy_template(
    template: dh.Template | None,
) -> None:
    with pytest.raises(ControlledCubeError, match=r"required .* template is unavailable"):
        controlled_cube_workflow._snappy_template(_TemplateClient(template))  # type: ignore[arg-type]


def test_wait_for_finished_polls_to_success_with_bounded_sleeps() -> None:
    statuses = iter(
        [
            _status(dh.RunState.PREPARING),
            _status(dh.RunState.RUNNING),
            _status(dh.RunState.FINISHED),
        ]
    )
    now = [10.0]
    sleeps: list[float] = []
    seen: list[dh.RunState] = []

    def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        now[0] += seconds

    result = wait_for_finished(
        lambda: next(statuses),
        timeout_seconds=10,
        poll_seconds=2,
        on_status=lambda status: seen.append(status.state),
        monotonic=lambda: now[0],
        sleep=sleep,
    )

    assert result.state is dh.RunState.FINISHED
    assert seen == [dh.RunState.PREPARING, dh.RunState.RUNNING, dh.RunState.FINISHED]
    assert sleeps == [2, 2]


def test_wait_for_finished_fails_on_terminal_error_without_sleeping() -> None:
    with pytest.raises(ControlledCubeError, match="ended in FAILED"):
        wait_for_finished(
            lambda: _status(dh.RunState.FAILED),
            timeout_seconds=10,
            poll_seconds=2,
            sleep=lambda _seconds: pytest.fail("failed run must not sleep"),
        )


def test_wait_for_finished_honors_deadline() -> None:
    now = [0.0]
    sleeps: list[float] = []
    reads = 0

    def status() -> dh.RunStatus:
        nonlocal reads
        reads += 1
        return _status(dh.RunState.RUNNING)

    def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        now[0] += seconds

    with pytest.raises(ControlledCubeError, match="within 3 seconds"):
        wait_for_finished(
            status,
            timeout_seconds=3,
            poll_seconds=2,
            monotonic=lambda: now[0],
            sleep=sleep,
        )
    assert sleeps == [2, 1]
    assert reads == 2


@pytest.mark.parametrize(
    ("waiter", "terminal_state"),
    [
        (wait_for_finished, dh.RunState.FINISHED),
        (wait_for_terminal, dh.RunState.STOPPED),
    ],
)
def test_wait_helpers_reject_terminal_status_read_after_deadline(
    waiter: Callable[..., dh.RunStatus],
    terminal_state: dh.RunState,
) -> None:
    now = [0.0]

    def late_status() -> dh.RunStatus:
        now[0] = 100.0
        return _status(terminal_state)

    with pytest.raises(ControlledCubeError, match="within 3 seconds"):
        waiter(
            late_status,
            timeout_seconds=3,
            poll_seconds=1,
            monotonic=lambda: now[0],
        )


def test_wait_for_terminal_accepts_stopped_cleanup_state() -> None:
    status = wait_for_terminal(
        lambda: _status(dh.RunState.STOPPED),
        timeout_seconds=10,
        poll_seconds=2,
        sleep=lambda _seconds: pytest.fail("terminal run must not sleep"),
    )

    assert status.state is dh.RunState.STOPPED


class _CleanupRuns:
    def __init__(
        self,
        statuses: list[dh.RunStatus],
        *,
        stop_error: Exception | None = None,
        initial_status_error: Exception | None = None,
    ) -> None:
        self._statuses = iter(statuses)
        self.stop_ids: list[str] = []
        self.stop_error = stop_error
        self.initial_status_error = initial_status_error
        self.status_calls = 0

    def status(self, *, run_id: str) -> dh.RunStatus:
        assert run_id == RUN_ID
        self.status_calls += 1
        if self.status_calls == 1 and self.initial_status_error is not None:
            raise self.initial_status_error
        return next(self._statuses)

    def stop(self, *, run_id: str) -> None:
        self.stop_ids.append(run_id)
        if self.stop_error is not None:
            raise self.stop_error


class _CleanupClient:
    def __init__(
        self,
        statuses: list[dh.RunStatus],
        *,
        stop_error: Exception | None = None,
        initial_status_error: Exception | None = None,
    ) -> None:
        self.runs = _CleanupRuns(
            statuses,
            stop_error=stop_error,
            initial_status_error=initial_status_error,
        )


def _settings(tmp_path: Path) -> controlled_cube_workflow.Settings:
    return controlled_cube_workflow.Settings(
        base_url="https://dicehub.test",
        api_key="sentinel-secret",
        result_zip=tmp_path / "result.zip",
        timeout_seconds=10,
        poll_seconds=1,
        stop_timeout_seconds=5,
    )


def test_cleanup_stops_exact_active_run_then_confirms_terminal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _CleanupClient([_status(dh.RunState.RUNNING), _status(dh.RunState.STOPPED)])
    events: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(
        controlled_cube_workflow,
        "_emit",
        lambda event, **values: events.append((event, values)),
    )

    assert controlled_cube_workflow._stop_for_cleanup(
        client,  # type: ignore[arg-type]
        RUN_ID,
        settings=_settings(tmp_path),
        primary_error=ControlledCubeError("original failure"),
    )

    assert client.runs.stop_ids == [RUN_ID]
    assert events[-1] == ("cleanup_run_terminal", {"run_id": RUN_ID, "state": "STOPPED"})


def test_cleanup_does_not_repeat_stop_already_in_progress(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _CleanupClient([_status(dh.RunState.STOPPING), _status(dh.RunState.STOPPED)])
    monkeypatch.setattr(controlled_cube_workflow, "_emit", lambda _event, **_values: None)

    assert controlled_cube_workflow._stop_for_cleanup(
        client,  # type: ignore[arg-type]
        RUN_ID,
        settings=_settings(tmp_path),
        primary_error=ControlledCubeError("original failure"),
    )

    assert client.runs.stop_ids == []


def test_cleanup_waits_for_queued_setup_instead_of_stopping_idle_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _CleanupClient([_status(dh.RunState.IDLE), _status(dh.RunState.CANCELED)])
    events: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(
        controlled_cube_workflow,
        "_emit",
        lambda event, **values: events.append((event, values)),
    )

    assert controlled_cube_workflow._stop_for_cleanup(
        client,  # type: ignore[arg-type]
        RUN_ID,
        settings=_settings(tmp_path),
        primary_error=ControlledCubeError("original failure"),
    )

    assert client.runs.stop_ids == []
    assert events[0] == ("cleanup_run_waiting_for_queue", {"run_id": RUN_ID})
    assert events[-1] == ("cleanup_run_terminal", {"run_id": RUN_ID, "state": "CANCELED"})


def test_cleanup_reconciles_terminal_state_after_definitive_stop_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _CleanupClient(
        [_status(dh.RunState.RUNNING), _status(dh.RunState.FINISHED)],
        stop_error=dh.APIError("Run is already terminal."),
    )
    events: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(
        controlled_cube_workflow,
        "_emit",
        lambda event, **values: events.append((event, values)),
    )

    assert controlled_cube_workflow._stop_for_cleanup(
        client,  # type: ignore[arg-type]
        RUN_ID,
        settings=_settings(tmp_path),
        primary_error=ControlledCubeError("original failure"),
    )

    assert client.runs.stop_ids == [RUN_ID]
    assert events[-1] == ("cleanup_run_terminal", {"run_id": RUN_ID, "state": "FINISHED"})


def test_cleanup_reconciles_ambiguous_stop_through_status_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _CleanupClient(
        [_status(dh.RunState.STOPPED)],
        stop_error=dh.MutationOutcomeUnknownError("Stop outcome unknown."),
        initial_status_error=dh.TransportError("Initial status unavailable."),
    )
    events: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(
        controlled_cube_workflow,
        "_emit",
        lambda event, **values: events.append((event, values)),
    )

    assert controlled_cube_workflow._stop_for_cleanup(
        client,  # type: ignore[arg-type]
        RUN_ID,
        settings=_settings(tmp_path),
        primary_error=ControlledCubeError("original failure"),
    )

    assert client.runs.stop_ids == [RUN_ID]
    assert [event for event, _values in events].count("cleanup_run_stop_outcome_unknown") == 1
    assert events[-1] == ("cleanup_run_terminal", {"run_id": RUN_ID, "state": "STOPPED"})


def test_cleanup_checks_conversion_setup_and_mesh_runs_in_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversion_run_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    setup_run_id = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
    mesh_run_id = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
    stopped: list[str] = []

    def stop(_client: object, run_id: str, **_kwargs: object) -> bool:
        stopped.append(run_id)
        return run_id != conversion_run_id

    monkeypatch.setattr(controlled_cube_workflow, "_stop_for_cleanup", stop)

    ready = controlled_cube_workflow._stop_tracked_runs_for_cleanup(
        object(),  # type: ignore[arg-type]
        (
            (conversion_run_id, dh.RunState.RUNNING),
            (setup_run_id, dh.RunState.IDLE),
            (mesh_run_id, dh.RunState.PREPARING),
        ),
        settings=_settings(tmp_path),
        primary_error=ControlledCubeError("original failure"),
    )

    assert stopped == [conversion_run_id, setup_run_id, mesh_run_id]
    assert ready is False


def test_result_archive_is_crc_checked_without_requiring_nonempty_foam_marker(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "results.zip"
    _write_archive(
        destination,
        {
            "case/constant/polyMesh/boundary": b"FoamFile\n{\n}\n",
            "case/project.foam": b"",
            "case/log.snappyHexMesh": b"Meshing complete\n",
        },
    )

    summary = validate_result_archive(destination)

    assert summary.members == 3
    assert summary.boundary_bytes > 0
    assert summary.project_foam_bytes == 0


@pytest.mark.parametrize(
    "bad_name",
    ["../escape", "/absolute", "safe/../../escape", "C:/windows", "safe\\windows"],
)
def test_result_archive_rejects_unsafe_names(tmp_path: Path, bad_name: str) -> None:
    destination = tmp_path / "results.zip"
    _write_archive(
        destination,
        {
            "case/constant/polyMesh/boundary": b"boundary",
            "case/project.foam": b"",
            bad_name: b"unsafe",
        },
    )

    with pytest.raises(ControlledCubeError, match="unsafe member"):
        validate_result_archive(destination)


def test_result_archive_rejects_vtk_and_missing_mesh(tmp_path: Path) -> None:
    vtk_archive = tmp_path / "vtk.zip"
    _write_archive(
        vtk_archive,
        {
            "case/constant/polyMesh/boundary": b"boundary",
            "case/project.foam": b"",
            "VTK/cube.vtu": b"vtk",
        },
    )
    with pytest.raises(ControlledCubeError, match="VTK"):
        validate_result_archive(vtk_archive)

    empty_mesh_archive = tmp_path / "empty-mesh.zip"
    _write_archive(
        empty_mesh_archive,
        {"case/constant/polyMesh/boundary": b"", "case/project.foam": b""},
    )
    with pytest.raises(ControlledCubeError, match="case/constant/polyMesh/boundary"):
        validate_result_archive(empty_mesh_archive)
