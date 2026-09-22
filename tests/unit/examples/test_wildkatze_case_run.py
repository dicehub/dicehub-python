from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import BinaryIO
from unittest.mock import MagicMock, Mock

import pytest

import dicehub as dh
from examples import wildkatze_case_run as example

RUN_ID = "12345678-1234-5678-9234-567812345678"
VERSION = "4.2030.01.02"  # Deliberately different from any deployed template default.
APPLICATION = (
    "metadata:\n  application: wildkatzeCaseRun\n  software: wildkatze\n"
    f"  wildkatze: wildkatze-{VERSION}\n"
)
ENVIRONMENT = (
    "environment:\n  WILDKATZE_CONTAINER_REGISTRY: dicehub/wildkatze\n"
    f"  WILDKATZE_VERSION: '{VERSION}'\n"
)


def status(state: dh.RunState) -> dh.RunStatus:
    return dh.RunStatus(
        run_id=RUN_ID,
        state=state,
        execution_status=None,
        error=None,
        flags=(),
        updated_at=datetime(2026, 9, 22, tzinfo=timezone.utc),
    )


def machine(machine_id: str = "wk1_1x", gpu_count: int = 0) -> dh.MachineType:
    return dh.MachineType(
        machine_type_id=machine_id,
        cpu_count=1,
        gpu_count=gpu_count,
        ram_gb=4,
        description="Test machine",
        price=dh.MachinePrice(amount=Decimal("0.14"), currency="EUR"),
    )


@pytest.fixture
def client() -> MagicMock:
    client = MagicMock(spec=dh.Client)
    for name in ("projects", "templates", "apps", "configs", "runs"):
        client.attach_mock(MagicMock(), name)
    client.__enter__.return_value = client
    client.projects.get_by_route.return_value = dh.ProjectDetail(
        project_id="301",
        group_id="101",
        name="Examples",
        display_route="/person/examples",
        route="/person/examples",
        visibility=dh.ProjectVisibility.PRIVATE,
        description=None,
        avatar_url=None,
    )
    client.templates.get_by_route.return_value = dh.Template(
        template_id="201",
        name="Wildkatze case run",
        slug="wildkatze_case_run",
        client_type="openfoam",
        route="/templates/wildkatze_case_run",
        description=None,
        image_path=None,
        icon_path=None,
        tags=(),
        created_at=None,
        updated_at=None,
    )
    client.apps.create.return_value = dh.AppDetail(
        app_id="401",
        project_id="301",
        name="Wildkatze example",
        display_route="/app/example",
        route="/app/example",
        visibility=dh.AppVisibility.PRIVATE,
        app_type=dh.AppType.REGULAR,
        description=None,
        template_id="201",
        template_name="Wildkatze case run",
        template_version="6",
        template_slug="wildkatze_case_run",
        icon_path=None,
        preview_url=None,
    )
    client.configs.list.return_value = dh.ConfigPage(
        configs=(
            dh.Config(
                config_id="501",
                app_id="401",
                config_internal_id="1",
                name="default",
                description=None,
                is_default=True,
                updating=False,
            ),
        ),
        offset=0,
        count=1,
        cursor="",
    )
    client.configs.get_text.side_effect = [APPLICATION, ENVIRONMENT, ENVIRONMENT]
    client.runs.list_machine_types.return_value = (machine(),)
    client.runs.start.return_value = status(dh.RunState.PREPARING)
    client.runs.wait.return_value = status(dh.RunState.FINISHED)

    def download(*, run_id: str, destination: BinaryIO, max_bytes: int) -> int:
        assert run_id == RUN_ID and max_bytes == example.MAX_RESULT_BYTES
        return destination.write(b"test result archive")

    client.runs.download_results.side_effect = download
    return client


@pytest.fixture
def case_path(tmp_path: Path) -> Path:
    case = tmp_path / "case"
    case.mkdir()
    # These are input-shape fixtures, not runnable solver data.
    for name in ("Allrun", "o.txt", "run.txt", "mesh.bmsh", "mesh.info.bmsh"):
        (case / name).write_bytes(b"test input")
    return case


@pytest.fixture
def result_path(
    tmp_path: Path, case_path: Path, client: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> Path:
    result = tmp_path / "results.zip"
    monkeypatch.setenv("DICEHUB_API_KEY", "test-key")
    monkeypatch.setenv("DICEHUB_PROJECT_URL", "https://dicehub.com/person/examples")
    monkeypatch.setenv("DICEHUB_WILDKATZE_CASE_PATH", str(case_path))
    monkeypatch.setenv("DICEHUB_MACHINE_TYPE_ID", "wk1_1x")
    monkeypatch.setenv("DICEHUB_RESULT_PATH", str(result))
    monkeypatch.delenv("DICEHUB_WILDKATZE_VERSION", raising=False)
    monkeypatch.delenv("DICEHUB_KEEP_APP", raising=False)
    monkeypatch.setattr(dh, "Client", Mock(return_value=client))
    return result


def test_prepared_case_workflow(
    client: MagicMock, result_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    uploaded: dict[str, bytes] = {}

    def upload(*, config_id: str, path: str, source: BinaryIO, max_bytes: int) -> None:
        assert config_id == "501" and max_bytes == example.MAX_CASE_FILE_BYTES
        uploaded[path] = source.read()

    client.configs.upload_file.side_effect = upload
    example.main()

    assert set(uploaded) == {
        "uploads/Allrun",
        "uploads/o.txt",
        "uploads/run.txt",
        "uploads/mesh.bmsh",
        "uploads/mesh.info.bmsh",
    }
    client.projects.get_by_route.assert_called_once_with(route="/person/examples")
    client.templates.get_by_route.assert_called_once_with(route="/templates/wildkatze_case_run")
    assert client.apps.create.call_args.kwargs["template_id"] == "201"
    updates = client.configs.set_values.call_args_list
    assert len(updates) == 2
    assert updates[0].kwargs == {
        "config_id": "501",
        "path": ".dicehub/flows/environment.yaml",
        "updates": (
            dh.ConfigValueUpdate(path=("environment", "WILDKATZE_VERSION"), value=VERSION),
        ),
    }
    assert {update.path: update.value for update in updates[1].kwargs["updates"]} == {
        ("run", "machine_type_id"): "wk1_1x",
        ("run", "node_count"): 1,
        ("run", "cpu_count"): 1,
        ("run", "flow"): "single-core-flow",
    }
    client.runs.start.assert_called_once_with(
        config_id="501",
        machine_type_id="wk1_1x",
        node_count=1,
        cpu_count=1,
        notify=False,
    )
    client.runs.wait.assert_called_once_with(run_id=RUN_ID, timeout_seconds=1800, poll_seconds=5)
    names = [call[0] for call in client.mock_calls]
    assert names.index("runs.list_machine_types") < names.index("apps.create")
    assert names.index("configs.set_values") < names.index("configs.upload_file")
    assert (
        names.index("runs.wait") < names.index("runs.download_results") < names.index("apps.delete")
    )
    assert result_path.read_bytes() == b"test result archive"
    assert not result_path.with_suffix(".zip.partial").exists()
    client.apps.delete.assert_called_once_with(app_id="401")
    output = capsys.readouterr().out
    assert VERSION in output and "test-key" not in output
    records = [json.loads(line) for line in output.splitlines() if line.startswith("{")]
    assert set(records[0]) == {
        "machine_type_id",
        "cpu_count",
        "gpu_count",
        "ram_gb",
        "description",
        "price",
    }
    assert records[0]["price"] == {"amount": "0.14", "currency": "EUR"}


def test_keep_app(client: MagicMock, result_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DICEHUB_KEEP_APP", "1")
    example.main()
    assert result_path.exists()
    client.apps.delete.assert_not_called()


@pytest.mark.parametrize("machine_id,gpus", [("dh1_1x", 0), ("wk1_2x_1gpu", 1), ("wk1_4x_vnc", 0)])
def test_unsuitable_machine_fails_before_app_creation(
    client: MagicMock,
    result_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    machine_id: str,
    gpus: int,
) -> None:
    client.runs.list_machine_types.return_value = (machine(machine_id, gpus),)
    monkeypatch.setenv("DICEHUB_MACHINE_TYPE_ID", machine_id)
    with pytest.raises(SystemExit, match="Wildkatze CPU machine"):
        example.main()
    client.apps.create.assert_not_called()
    assert not result_path.exists()


def test_local_machine_uses_docker_flow(client: MagicMock) -> None:
    local = dh.MachineType(machine_type_id="local", description="Local", price=None)
    client.runs.list_machine_types.return_value = (local,)
    assert example.select_machine(client, "local") == local
    example.configure_machine(client, "501", "local")
    assert (
        client.configs.set_values.call_args.kwargs["updates"][-1].value == "single-core-flow-docker"
    )


@pytest.mark.parametrize("change", ["metadata", "registry", "version", "readback", "malformed"])
def test_version_contract_is_checked_before_upload_or_start(
    client: MagicMock,
    result_path: Path,
    change: str,
) -> None:
    application, environment, readback = APPLICATION, ENVIRONMENT, ENVIRONMENT
    if change == "metadata":
        application = application.replace(f"wildkatze-{VERSION}", "wildkatze-other")
    elif change == "registry":
        environment = environment.replace("dicehub/wildkatze", "unknown/image")
    elif change == "version":
        environment = environment.replace(VERSION, "$(untrusted)")
    elif change == "readback":
        readback = environment.replace(VERSION, "other")
    else:
        environment = "environment: [secret-body: ["
    client.configs.get_text.side_effect = [application, environment, readback]
    with pytest.raises(SystemExit) as error:
        example.main()
    assert "secret-body" not in str(error.value)
    client.configs.upload_file.assert_not_called()
    client.runs.start.assert_not_called()
    assert not result_path.exists()


def test_requested_version_must_match_template(client: MagicMock) -> None:
    with pytest.raises(SystemExit, match="must match"):
        example.select_wildkatze_version(client, "501", "unavailable")
    client.configs.set_values.assert_not_called()


@pytest.mark.parametrize("public_target", ["project", "app"])
def test_public_targets_never_receive_case_files(
    client: MagicMock,
    result_path: Path,
    public_target: str,
) -> None:
    target = client.projects.get_by_route if public_target == "project" else client.apps.create
    visibility = (
        dh.ProjectVisibility.PUBLIC if public_target == "project" else dh.AppVisibility.PUBLIC
    )
    target.return_value = target.return_value.model_copy(update={"visibility": visibility})
    with pytest.raises(SystemExit, match="private"):
        example.main()
    client.configs.upload_file.assert_not_called()
    client.runs.start.assert_not_called()
    if public_target == "app":
        client.apps.delete.assert_called_once_with(app_id="401")
    else:
        client.apps.create.assert_not_called()
    assert not result_path.exists()


@pytest.mark.parametrize("failure", ["unknown", "timeout", "failed", "stopped", "active"])
def test_unsuccessful_runs_are_not_downloaded_deleted_or_retried(
    client: MagicMock,
    result_path: Path,
    failure: str,
) -> None:
    if failure == "unknown":
        client.runs.start.side_effect = dh.MutationOutcomeUnknownError("Run outcome is unknown.")
    elif failure == "timeout":
        client.runs.wait.side_effect = dh.RunTimeoutError(
            run_id=RUN_ID, timeout_seconds=1800, last_status=status(dh.RunState.RUNNING)
        )
    elif failure == "failed":
        client.runs.wait.side_effect = dh.RunFailedError(status=status(dh.RunState.FAILED))
    else:
        client.runs.wait.return_value = status(
            dh.RunState.STOPPED if failure == "stopped" else dh.RunState.RUNNING
        )
    with pytest.raises((dh.DiceHubError, SystemExit)):
        example.main()
    client.runs.start.assert_called_once()
    client.runs.download_results.assert_not_called()
    client.apps.delete.assert_not_called()
    assert not result_path.exists()


def test_partial_download_never_publishes_result_or_deletes_app(
    client: MagicMock,
    result_path: Path,
) -> None:
    def fail(*, run_id: str, destination: BinaryIO, max_bytes: int) -> int:
        destination.write(b"partial")
        raise dh.TransportError("Download failed.")

    client.runs.download_results.side_effect = fail
    with pytest.raises(dh.TransportError):
        example.main()
    assert not result_path.exists()
    assert result_path.with_suffix(".zip.partial").read_bytes() == b"partial"
    client.apps.delete.assert_not_called()


def test_result_created_during_download_is_not_overwritten(
    client: MagicMock, tmp_path: Path
) -> None:
    result = tmp_path / "result.zip"
    partial = example.prepare_result_path(result)
    result.write_bytes(b"existing")
    with pytest.raises(FileExistsError):
        example.download_results(client, RUN_ID, result, partial)
    assert result.read_bytes() == b"existing"


@pytest.mark.parametrize(
    "bad_input", ["missing", "mesh_pair", "symlink", "hidden", "size", "count"]
)
def test_invalid_case_fails_before_any_api_call(
    case_path: Path,
    client: MagicMock,
    result_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    bad_input: str,
) -> None:
    if bad_input == "missing":
        (case_path / "Allrun").write_bytes(b"")
    elif bad_input == "mesh_pair":
        (case_path / "mesh.info.bmsh").rename(case_path / "other.info.bmsh")
    elif bad_input == "symlink":
        (case_path / "link").symlink_to(case_path / "o.txt")
    elif bad_input == "hidden":
        (case_path / ".env").write_text("test input")
    elif bad_input == "size":
        monkeypatch.setattr(example, "MAX_CASE_FILE_BYTES", 1)
    else:
        monkeypatch.setattr(example, "MAX_CASE_FILES", 1)
    with pytest.raises(SystemExit):
        example.main()
    assert client.mock_calls == []
    assert not result_path.exists()


def test_prepared_case_accepts_a_46_mib_mesh(case_path: Path) -> None:
    mesh = case_path / "mesh.bmsh"
    with mesh.open("wb") as destination:
        destination.truncate(46 * 1024 * 1024)
    assert mesh in example.collect_case_files(case_path)
