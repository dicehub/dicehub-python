from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import BinaryIO, cast

import pytest

import dicehub as dh
from examples import openfoam_case_run

APP_ID = "401"
CONFIG_ID = "501"
PROJECT_ID = "301"
RUN_ID = "12345678-1234-5678-9234-567812345678"
TEMPLATE_ID = "201"


def _status(state: dh.RunState) -> dh.RunStatus:
    return dh.RunStatus(
        run_id=RUN_ID,
        state=state,
        execution_status=None,
        error=None,
        flags=(),
        updated_at=datetime(2026, 9, 21, tzinfo=timezone.utc),
    )


class _Projects:
    def __init__(
        self,
        calls: list[tuple[str, object]],
        visibility: dh.ProjectVisibility,
    ) -> None:
        self.calls = calls
        self.visibility = visibility

    def get_by_route(self, *, route: str) -> dh.ProjectDetail:
        self.calls.append(("project", route))
        return dh.ProjectDetail(
            project_id=PROJECT_ID,
            group_id="101",
            name="OpenFOAM examples",
            display_route=route,
            route=route,
            visibility=self.visibility,
            description=None,
            avatar_url=None,
        )


class _Templates:
    def __init__(self, calls: list[tuple[str, object]]) -> None:
        self.calls = calls

    def get_by_route(self, *, route: str) -> dh.Template:
        self.calls.append(("template", route))
        return dh.Template(
            template_id=TEMPLATE_ID,
            name="OpenFOAM Case Run",
            slug="case_run",
            description=None,
            client_type="openfoam",
            route=route,
            image_path=None,
            icon_path=None,
            tags=(),
            created_at=None,
            updated_at=None,
        )


class _Apps:
    def __init__(
        self,
        calls: list[tuple[str, object]],
        visibility: dh.AppVisibility,
    ) -> None:
        self.calls = calls
        self.visibility = visibility

    def create(
        self,
        *,
        project_id: str,
        template_id: str,
        name: str,
        description: str | None = None,
    ) -> dh.AppDetail:
        self.calls.append(
            (
                "app_create",
                {
                    "project_id": project_id,
                    "template_id": template_id,
                    "name": name,
                    "description": description,
                },
            )
        )
        return dh.AppDetail(
            app_id=APP_ID,
            project_id=project_id,
            name=name,
            display_route="/app/example",
            route="/app/example",
            visibility=self.visibility,
            app_type=dh.AppType.REGULAR,
            description=description,
            template_id=template_id,
            template_name="OpenFOAM Case Run",
            template_version="66",
            template_slug="case_run",
            icon_path=None,
            preview_url=None,
        )

    def delete(self, *, app_id: str) -> None:
        self.calls.append(("app_delete", app_id))


class _Configs:
    def __init__(self, calls: list[tuple[str, object]]) -> None:
        self.calls = calls

    def list(self, *, app_id: str, limit: int) -> dh.ConfigPage:
        self.calls.append(("config_list", {"app_id": app_id, "limit": limit}))
        config = dh.Config(
            config_id=CONFIG_ID,
            app_id=app_id,
            config_internal_id="1",
            name="default",
            description=None,
            is_default=True,
            template_version="66",
            updating=False,
        )
        return dh.ConfigPage(configs=(config,), offset=0, count=1, cursor="")

    def upload_file(
        self,
        *,
        config_id: str,
        path: str,
        source: BinaryIO,
        max_bytes: int,
    ) -> None:
        self.calls.append(
            (
                "upload",
                {
                    "config_id": config_id,
                    "path": path,
                    "content": source.read(),
                    "max_bytes": max_bytes,
                },
            )
        )

    def set_values(
        self,
        *,
        config_id: str,
        path: str,
        updates: tuple[dh.ConfigValueUpdate, ...],
    ) -> None:
        self.calls.append(
            (
                "set_values",
                {
                    "config_id": config_id,
                    "path": path,
                    "updates": tuple((update.path, update.value) for update in updates),
                },
            )
        )

    def get_text(self, *, config_id: str, path: str) -> str:
        self.calls.append(("get_text", {"config_id": config_id, "path": path}))
        return {
            "application.yaml": "metadata:\n  software: openfoam_foundation\n",
            ".dicehub/flows/environment.yaml": (
                "environment:\n"
                "  OPENFOAM_CONTAINER_REGISTRY: 'dicehub/openfoam-runner'\n"
                "  OPENFOAM_VERSION: '14'\n"
            ),
            ".dicehub/settings.yaml": (
                "run:\n"
                "  machine_type_id: c6a_large\n"
                "  node_count: 1\n"
                "  cpu_count: 1\n"
                "  flow: single-core-flow\n"
            ),
        }[path]


class _Runs:
    def __init__(self, calls: list[tuple[str, object]]) -> None:
        self.calls = calls

    def list_machine_types(self) -> tuple[dh.MachineType, ...]:
        self.calls.append(("machine_list", None))
        return (
            dh.MachineType(
                machine_type_id="c6a_large",
                cpu_count=2,
                gpu_count=0,
                ram_gb=4,
                description="Two CPU cores and 4 GB RAM",
                price=dh.MachinePrice(amount=Decimal("0.11"), currency="EUR"),
            ),
        )

    def start(
        self,
        *,
        config_id: str,
        machine_type_id: str,
        node_count: int,
        cpu_count: int | None,
        notify: bool,
    ) -> dh.RunStatus:
        self.calls.append(
            (
                "run_start",
                {
                    "config_id": config_id,
                    "machine_type_id": machine_type_id,
                    "node_count": node_count,
                    "cpu_count": cpu_count,
                    "notify": notify,
                },
            )
        )
        return _status(dh.RunState.PREPARING)

    def wait(self, *, run_id: str, timeout_seconds: float, poll_seconds: float) -> dh.RunStatus:
        self.calls.append(
            (
                "run_wait",
                {
                    "run_id": run_id,
                    "timeout_seconds": timeout_seconds,
                    "poll_seconds": poll_seconds,
                },
            )
        )
        return _status(dh.RunState.FINISHED)

    def download_results(
        self,
        *,
        run_id: str,
        destination: BinaryIO,
        max_bytes: int,
    ) -> int:
        self.calls.append(("result_download", {"run_id": run_id, "max_bytes": max_bytes}))
        return destination.write(b"example result")


class _Client:
    def __init__(
        self,
        app_visibility: dh.AppVisibility = dh.AppVisibility.PRIVATE,
        project_visibility: dh.ProjectVisibility = dh.ProjectVisibility.PRIVATE,
    ) -> None:
        self.calls: list[tuple[str, object]] = []
        self.projects = _Projects(self.calls, project_visibility)
        self.templates = _Templates(self.calls)
        self.apps = _Apps(self.calls, app_visibility)
        self.configs = _Configs(self.calls)
        self.runs = _Runs(self.calls)

    def __enter__(self) -> _Client:
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: object,
    ) -> None:
        return None


def test_case_run_orders_public_operations_and_cleans_up(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _Client()
    root = Path(__file__).parents[3]
    result_path = tmp_path / "result.zip"
    monkeypatch.setenv("DICEHUB_API_KEY", "sentinel-secret")
    monkeypatch.setenv("DICEHUB_PROJECT_URL", "https://dicehub.test/owner/openfoam-examples")
    monkeypatch.setenv("DICEHUB_MACHINE_TYPE_ID", "c6a_large")
    monkeypatch.setenv(
        "DICEHUB_OPENFOAM_CASE_PATH",
        str(root / "examples/openfoam_case_run_case"),
    )
    monkeypatch.setenv("DICEHUB_RESULT_PATH", str(result_path))
    monkeypatch.setattr(dh, "Client", lambda **_values: client)

    openfoam_case_run.main()

    call_names = [name for name, _value in client.calls]
    assert call_names == [
        "project",
        "template",
        "app_create",
        "config_list",
        *("upload" for _index in range(9)),
        "set_values",
        "set_values",
        "machine_list",
        "set_values",
        "run_start",
        "run_wait",
        "result_download",
        "app_delete",
    ]
    uploads = [value for name, value in client.calls if name == "upload"]
    upload_paths = {cast(dict[str, object], value)["path"] for value in uploads}
    assert upload_paths == {
        "uploads/Allrun",
        "uploads/0/U",
        "uploads/0/p",
        "uploads/constant/momentumTransport",
        "uploads/constant/physicalProperties",
        "uploads/system/blockMeshDict",
        "uploads/system/controlDict",
        "uploads/system/fvSchemes",
        "uploads/system/fvSolution",
    }
    start = cast(
        dict[str, object], next(value for name, value in client.calls if name == "run_start")
    )
    assert start == {
        "config_id": CONFIG_ID,
        "machine_type_id": "c6a_large",
        "node_count": 1,
        "cpu_count": 1,
        "notify": False,
    }
    assert result_path.read_bytes() == b"example result"
    assert not result_path.with_name("result.zip.partial").exists()

    output = capsys.readouterr().out
    machine_lines = [
        json.loads(line)
        for line in output.splitlines()
        if line.startswith("{") and "machine_type_id" in line
    ]
    assert len(machine_lines) == 2
    assert all(machine["machine_type_id"] == "c6a_large" for machine in machine_lines)
    assert "sentinel-secret" not in output


def test_case_run_rejects_public_app_before_upload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _Client(app_visibility=dh.AppVisibility.PUBLIC)
    root = Path(__file__).parents[3]
    monkeypatch.setenv("DICEHUB_API_KEY", "sentinel-secret")
    monkeypatch.setenv("DICEHUB_PROJECT_URL", "https://dicehub.test/owner/openfoam-examples")
    monkeypatch.setenv("DICEHUB_MACHINE_TYPE_ID", "c6a_large")
    monkeypatch.setenv(
        "DICEHUB_OPENFOAM_CASE_PATH",
        str(root / "examples/openfoam_case_run_case"),
    )
    monkeypatch.setenv("DICEHUB_RESULT_PATH", str(tmp_path / "result.zip"))
    monkeypatch.setattr(dh, "Client", lambda **_values: client)

    with pytest.raises(SystemExit, match="private project"):
        openfoam_case_run.main()

    assert [name for name, _value in client.calls] == [
        "project",
        "template",
        "app_create",
        "app_delete",
    ]


def test_case_run_rejects_public_project_before_app_creation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _Client(project_visibility=dh.ProjectVisibility.PUBLIC)
    root = Path(__file__).parents[3]
    monkeypatch.setenv("DICEHUB_API_KEY", "sentinel-secret")
    monkeypatch.setenv("DICEHUB_PROJECT_URL", "https://dicehub.test/owner/openfoam-examples")
    monkeypatch.setenv("DICEHUB_MACHINE_TYPE_ID", "c6a_large")
    monkeypatch.setenv(
        "DICEHUB_OPENFOAM_CASE_PATH",
        str(root / "examples/openfoam_case_run_case"),
    )
    monkeypatch.setenv("DICEHUB_RESULT_PATH", str(tmp_path / "result.zip"))
    monkeypatch.setattr(dh, "Client", lambda **_values: client)

    with pytest.raises(SystemExit, match="private project"):
        openfoam_case_run.main()

    assert [name for name, _value in client.calls] == ["project"]
