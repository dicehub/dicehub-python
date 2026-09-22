"""Run the bundled OpenFOAM 14 cavity case on dicehub."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from urllib.parse import urlsplit

import dicehub as dh

MAX_CASE_FILES = 256
MAX_CASE_FILE_BYTES = 8 * 1024 * 1024
MAX_CASE_BYTES = 32 * 1024 * 1024
MAX_RESULT_BYTES = 256 * 1024 * 1024


def collect_case_files(case_path: Path) -> tuple[Path, ...]:
    """Validate the local case and return its files in a stable order."""

    if case_path.is_symlink() or not case_path.is_dir():
        raise SystemExit("DICEHUB_OPENFOAM_CASE_PATH must be a directory, not a symbolic link.")

    entries = sorted(case_path.rglob("*"))
    if any(path.is_symlink() for path in entries):
        raise SystemExit("The OpenFOAM case must not contain symbolic links.")

    files = tuple(path for path in entries if path.is_file())
    if len(files) > MAX_CASE_FILES:
        raise SystemExit(f"The OpenFOAM case must contain at most {MAX_CASE_FILES} files.")
    if any(path.stat().st_size > MAX_CASE_FILE_BYTES for path in files):
        raise SystemExit("An OpenFOAM case file exceeds the 8 MiB limit.")
    if sum(path.stat().st_size for path in files) > MAX_CASE_BYTES:
        raise SystemExit("The OpenFOAM case exceeds the 32 MiB limit.")
    return files


def prepare_result_path(result_path: Path) -> Path:
    """Check the result destination and return its temporary download path."""

    partial_path = result_path.with_name(f"{result_path.name}.partial")
    if not result_path.parent.is_dir():
        raise SystemExit("The DICEHUB_RESULT_PATH parent directory does not exist.")
    if result_path.exists() or partial_path.exists():
        raise SystemExit("The result path or its partial path already exists.")
    return partial_path


def resolve_project(client: dh.Client, project_url: str) -> dh.ProjectDetail:
    """Resolve a private dicehub project from the URL shown in the browser."""

    parsed = urlsplit(project_url)
    route = parsed.path.rstrip("/")
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or not route
        or parsed.query
        or parsed.fragment
    ):
        raise SystemExit("DICEHUB_PROJECT_URL must be a complete HTTPS project URL.")

    project = client.projects.get_by_route(route=route)
    if project.visibility is not dh.ProjectVisibility.PRIVATE:
        raise SystemExit("DICEHUB_PROJECT_URL must identify a private project.")
    return project


def create_case_run_app(client: dh.Client, project_id: str) -> dh.AppDetail:
    """Resolve the Case Run template and create one temporary private app."""

    template = client.templates.get_by_route(route="/templates/case_run")
    if template.slug != "case_run":
        raise RuntimeError("The Case Run template has an unexpected identity.")
    app = client.apps.create(
        project_id=project_id,
        template_id=template.template_id,
        name=f"OpenFOAM cavity {uuid.uuid4().hex[:8]}",
        description="OpenFOAM 14 cavity example",
    )
    if app.visibility is not dh.AppVisibility.PRIVATE:
        client.apps.delete(app_id=app.app_id)
        raise SystemExit("DICEHUB_PROJECT_URL must identify a private project.")
    return app


def get_default_config(client: dh.Client, app_id: str) -> dh.Config:
    """Return the default configuration created with the app."""

    configs = client.configs.list(app_id=app_id, limit=20).configs
    for config in configs:
        if config.is_default:
            return config
    raise RuntimeError("The Case Run app has no default configuration.")


def upload_case(
    client: dh.Client,
    config_id: str,
    case_path: Path,
    case_files: tuple[Path, ...],
) -> None:
    """Upload each local case file below the configuration's uploads directory."""

    for source_path in case_files:
        relative_path = source_path.relative_to(case_path).as_posix()
        with source_path.open("rb") as source:
            client.configs.upload_file(
                config_id=config_id,
                path=f"uploads/{relative_path}",
                source=source,
                max_bytes=MAX_CASE_FILE_BYTES,
            )


def select_openfoam_14(client: dh.Client, config_id: str) -> None:
    """Configure the app to use OpenFOAM Foundation version 14."""

    client.configs.set_values(
        config_id=config_id,
        path="application.yaml",
        updates=(
            dh.ConfigValueUpdate(
                path=("metadata", "software"),
                value="openfoam_foundation",
            ),
        ),
    )
    client.configs.set_values(
        config_id=config_id,
        path=".dicehub/flows/environment.yaml",
        updates=(
            dh.ConfigValueUpdate(
                path=("environment", "OPENFOAM_CONTAINER_REGISTRY"),
                value="dicehub/openfoam-runner",
            ),
            dh.ConfigValueUpdate(
                path=("environment", "OPENFOAM_VERSION"),
                value="14",
            ),
        ),
    )


def select_machine(client: dh.Client, machine_type_id: str) -> dh.MachineType:
    """Show available machines and return the machine selected by its exact ID."""

    machine_types = client.runs.list_machine_types()
    selected: dh.MachineType | None = None
    print("Available machines:")
    for machine_type in machine_types:
        print(machine_type.model_dump_json())
        if machine_type.machine_type_id == machine_type_id:
            selected = machine_type

    if selected is None:
        raise SystemExit(f"Machine type {machine_type_id!r} is not available.")
    return selected


def configure_machine(client: dh.Client, config_id: str, machine_type_id: str) -> None:
    """Configure one node and one OpenFOAM process on the selected machine."""

    flow = "single-core-flow-docker" if machine_type_id == "local" else "single-core-flow"
    client.configs.set_values(
        config_id=config_id,
        path=".dicehub/settings.yaml",
        updates=(
            dh.ConfigValueUpdate(path=("run", "machine_type_id"), value=machine_type_id),
            dh.ConfigValueUpdate(path=("run", "node_count"), value=1),
            dh.ConfigValueUpdate(path=("run", "cpu_count"), value=1),
            dh.ConfigValueUpdate(path=("run", "flow"), value=flow),
        ),
    )


def start_run(client: dh.Client, config_id: str, machine_type_id: str) -> dh.RunStatus:
    """Start one run on the selected machine without user notifications."""

    return client.runs.start(
        config_id=config_id,
        machine_type_id=machine_type_id,
        node_count=1,
        cpu_count=1,
        notify=False,
    )


def wait_for_run(client: dh.Client, run_id: str) -> dh.RunStatus:
    """Wait for the run to finish for at most 30 minutes."""

    finished = client.runs.wait(
        run_id=run_id,
        timeout_seconds=1800,
        poll_seconds=5,
    )
    if finished.state is not dh.RunState.FINISHED:
        raise RuntimeError(f"Run ended in state {finished.state.value}.")
    return finished


def download_results(
    client: dh.Client,
    run_id: str,
    result_path: Path,
    partial_path: Path,
) -> int:
    """Download the result ZIP without replacing an existing file."""

    with partial_path.open("xb") as destination:
        byte_count = client.runs.download_results(
            run_id=run_id,
            destination=destination,
            max_bytes=MAX_RESULT_BYTES,
        )
    os.link(partial_path, result_path)
    partial_path.unlink()
    return byte_count


def main() -> None:
    """Run the complete OpenFOAM case workflow in tutorial order."""

    case_path = Path(os.environ["DICEHUB_OPENFOAM_CASE_PATH"])
    result_path = Path(os.environ["DICEHUB_RESULT_PATH"])
    machine_type_id = os.environ["DICEHUB_MACHINE_TYPE_ID"]

    case_files = collect_case_files(case_path)
    partial_path = prepare_result_path(result_path)

    with dh.Client(api_key=os.environ["DICEHUB_API_KEY"]) as client:
        project = resolve_project(client, os.environ["DICEHUB_PROJECT_URL"])
        app = create_case_run_app(client, project.project_id)
        print(f"Created app {app.app_id}")

        config = get_default_config(client, app.app_id)
        upload_case(client, config.config_id, case_path, case_files)
        print(f"Uploaded {len(case_files)} case files")

        select_openfoam_14(client, config.config_id)
        machine = select_machine(client, machine_type_id)
        print("Selected machine:")
        print(machine.model_dump_json())
        configure_machine(client, config.config_id, machine.machine_type_id)

        started = start_run(client, config.config_id, machine.machine_type_id)
        print(f"Started run {started.run_id}")
        finished = wait_for_run(client, started.run_id)

        byte_count = download_results(client, finished.run_id, result_path, partial_path)
        print(json.dumps({"result": str(result_path), "bytes": byte_count}))

        client.apps.delete(app_id=app.app_id)
        print(f"Deleted app {app.app_id}")


if __name__ == "__main__":
    main()
