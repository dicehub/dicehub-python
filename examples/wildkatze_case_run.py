"""Upload a prepared Wildkatze case, run it on dicehub, and download the results."""

from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path
from urllib.parse import urlsplit

import yaml

import dicehub as dh

MAX_CASE_FILES = 256
MAX_CASE_FILE_BYTES = 64 * 1024 * 1024
MAX_CASE_BYTES = 128 * 1024 * 1024
MAX_RESULT_BYTES = 512 * 1024 * 1024


def collect_case_files(case_path: Path) -> tuple[Path, ...]:
    """Check a small prepared case before creating or uploading anything."""

    if case_path.is_symlink() or not case_path.is_dir():
        raise SystemExit("DICEHUB_WILDKATZE_CASE_PATH must be a directory, not a symbolic link.")

    files: list[Path] = []
    total_bytes = 0
    for path in case_path.rglob("*"):
        if path.is_symlink() or not (path.is_dir() or path.is_file()):
            raise SystemExit("The case must contain only regular files and directories.")
        if path.is_dir():
            continue
        relative_path = path.relative_to(case_path)
        if any(part.startswith(".") for part in relative_path.parts):
            raise SystemExit("Use a case directory without hidden files or directories.")
        size = path.stat().st_size
        if size > MAX_CASE_FILE_BYTES:
            raise SystemExit("A case file exceeds the 64 MiB limit.")
        total_bytes += size
        files.append(path)
        if len(files) > MAX_CASE_FILES or total_bytes > MAX_CASE_BYTES:
            raise SystemExit("The case exceeds 256 files or 128 MiB in total.")

    for name in ("Allrun", "o.txt", "run.txt"):
        if case_path / name not in files or (case_path / name).stat().st_size == 0:
            raise SystemExit(f"The case needs a non-empty {name} at its root.")
    meshes = [
        path for path in files if path.suffix == ".bmsh" and not path.name.endswith(".info.bmsh")
    ]
    if not meshes or any(
        path.stat().st_size == 0
        or path.with_suffix(".info.bmsh") not in files
        or path.with_suffix(".info.bmsh").stat().st_size == 0
        for path in meshes
    ):
        raise SystemExit("The case needs a non-empty .bmsh mesh and matching .info.bmsh file.")
    return tuple(sorted(files))


def prepare_result_path(result_path: Path) -> Path:
    """Reserve no files yet; check that both download paths are unused."""

    partial_path = result_path.with_name(f"{result_path.name}.partial")
    if not result_path.parent.is_dir():
        raise SystemExit("The DICEHUB_RESULT_PATH parent directory does not exist.")
    if any(path.exists() or path.is_symlink() for path in (result_path, partial_path)):
        raise SystemExit("The result path or its partial path already exists.")
    return partial_path


def resolve_project(client: dh.Client, project_url: str) -> dh.ProjectDetail:
    """Find a private project using its dicehub.com browser URL."""

    parsed = urlsplit(project_url)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "dicehub.com"
        or len(parsed.path.strip("/").split("/")) < 2
        or parsed.query
        or parsed.fragment
    ):
        raise SystemExit("DICEHUB_PROJECT_URL must be a dicehub.com HTTPS project URL.")
    project = client.projects.get_by_route(route=parsed.path.rstrip("/"))
    if project.visibility is not dh.ProjectVisibility.PRIVATE:
        raise SystemExit("Select a private project for this example.")
    return project


def select_machine(client: dh.Client, machine_type_id: str) -> dh.MachineType:
    """Show compatible CPU machines and select the user's exact machine ID."""

    selected: dh.MachineType | None = None
    print("Wildkatze CPU machines (net EUR per machine-hour):")
    for machine in client.runs.list_machine_types():
        compatible = machine.machine_type_id == "local" or (
            machine.machine_type_id.startswith("wk1_")
            and not machine.machine_type_id.endswith("_vnc")
            and machine.gpu_count == 0
            and machine.cpu_count is not None
            and machine.cpu_count >= 1
            and machine.price is not None
        )
        if compatible:
            print(machine.model_dump_json())
            if machine.machine_type_id == machine_type_id:
                selected = machine
    if selected is None:
        raise SystemExit("Choose an available Wildkatze CPU machine from the list.")
    print("Selected machine:")
    print(selected.model_dump_json())
    return selected


def create_case_run_app(client: dh.Client, project_id: str) -> dh.AppDetail:
    """Resolve the Wildkatze template and create one temporary private app."""

    template = client.templates.get_by_route(route="/templates/wildkatze_case_run")
    if template.slug != "wildkatze_case_run" or template.client_type != "openfoam":
        raise SystemExit("The Wildkatze Case Run template has an unexpected identity.")
    app = client.apps.create(
        project_id=project_id,
        template_id=template.template_id,
        name=f"Wildkatze example {uuid.uuid4().hex[:8]}",
        description="Prepared Wildkatze case from the Python tutorial",
    )
    print(f"Created app {app.app_id}")
    if app.visibility is not dh.AppVisibility.PRIVATE:
        client.apps.delete(app_id=app.app_id)
        raise SystemExit("The created app must be private.")
    return app


def get_default_config(client: dh.Client, app_id: str) -> dh.Config:
    """Find the default configuration supplied by the template."""

    for config in client.configs.list(app_id=app_id, limit=20).configs:
        if config.is_default:
            return config
    raise SystemExit("The Wildkatze app has no default configuration.")


def read_config_section(
    client: dh.Client, config_id: str, path: str, section: str
) -> dict[str, object]:
    """Read a YAML section without printing configuration content on failure."""

    content = client.configs.get_text(config_id=config_id, path=path)
    try:
        document = yaml.safe_load(content)
    except (yaml.YAMLError, RecursionError):
        raise SystemExit("The template returned invalid configuration YAML.") from None
    values = document.get(section) if isinstance(document, dict) else None
    if not isinstance(values, dict) or any(not isinstance(key, str) for key in values):
        raise SystemExit("The template configuration is missing a required section.")
    return dict(values)


def select_wildkatze_version(
    client: dh.Client, config_id: str, requested_version: str | None = None
) -> str:
    """Select the version supplied by the template, or check an explicit match."""

    metadata = read_config_section(client, config_id, "application.yaml", "metadata")
    environment_path = ".dicehub/flows/environment.yaml"
    environment = read_config_section(client, config_id, environment_path, "environment")
    version = environment.get("WILDKATZE_VERSION")
    if (
        metadata.get("application") != "wildkatzeCaseRun"
        or metadata.get("software") != "wildkatze"
        or environment.get("WILDKATZE_CONTAINER_REGISTRY") != "dicehub/wildkatze"
        or not isinstance(version, str)
        or re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}", version) is None
        or metadata.get("wildkatze") != f"wildkatze-{version}"
    ):
        raise SystemExit("The template does not provide a consistent Wildkatze version.")
    if requested_version is not None and requested_version != version:
        raise SystemExit("DICEHUB_WILDKATZE_VERSION must match the template's supplied version.")

    client.configs.set_values(
        config_id=config_id,
        path=environment_path,
        updates=(dh.ConfigValueUpdate(path=("environment", "WILDKATZE_VERSION"), value=version),),
    )
    confirmed = read_config_section(client, config_id, environment_path, "environment")
    if confirmed.get("WILDKATZE_VERSION") != version:
        raise SystemExit("The Wildkatze version update was not confirmed.")
    print(f"Selected Wildkatze {version}")
    return version


def upload_case(
    client: dh.Client, config_id: str, case_path: Path, case_files: tuple[Path, ...]
) -> None:
    """Stream case files into uploads, with Allrun directly below that directory."""

    for path in case_files:
        with path.open("rb") as source:
            client.configs.upload_file(
                config_id=config_id,
                path=f"uploads/{path.relative_to(case_path).as_posix()}",
                source=source,
                max_bytes=MAX_CASE_FILE_BYTES,
            )


def configure_machine(client: dh.Client, config_id: str, machine_type_id: str) -> None:
    """Configure one node and one CPU process using the template's single-node flow."""

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
    """Submit the run once, with one node, one CPU, and notifications disabled."""

    return client.runs.start(
        config_id=config_id,
        machine_type_id=machine_type_id,
        node_count=1,
        cpu_count=1,
        notify=False,
    )


def wait_for_run(client: dh.Client, run_id: str) -> dh.RunStatus:
    """Wait at most 30 minutes and accept only a successfully finished run."""

    finished = client.runs.wait(run_id=run_id, timeout_seconds=1800, poll_seconds=5)
    if finished.state is not dh.RunState.FINISHED:
        raise SystemExit(f"Run ended in state {finished.state.value}.")
    return finished


def download_results(client: dh.Client, run_id: str, result_path: Path, partial_path: Path) -> int:
    """Download the ZIP to a new file, then publish it without overwriting anything."""

    with partial_path.open("xb") as destination:
        byte_count = client.runs.download_results(
            run_id=run_id, destination=destination, max_bytes=MAX_RESULT_BYTES
        )
    os.link(partial_path, result_path)
    partial_path.unlink()
    return byte_count


def delete_example_app(client: dh.Client, app_id: str) -> None:
    """Delete only the app created by this example after its results are saved."""

    client.apps.delete(app_id=app_id)
    print(f"Deleted app {app_id}")


def main() -> None:
    """Run each tutorial step in order, from local case checks to app cleanup."""

    case_path = Path(os.environ["DICEHUB_WILDKATZE_CASE_PATH"])
    result_path = Path(os.environ["DICEHUB_RESULT_PATH"])
    machine_type_id = os.environ["DICEHUB_MACHINE_TYPE_ID"]
    keep_app = os.environ.get("DICEHUB_KEEP_APP") == "1"

    case_files = collect_case_files(case_path)
    partial_path = prepare_result_path(result_path)

    with dh.Client(api_key=os.environ["DICEHUB_API_KEY"]) as client:
        project = resolve_project(client, os.environ["DICEHUB_PROJECT_URL"])
        machine = select_machine(client, machine_type_id)
        app = create_case_run_app(client, project.project_id)
        config = get_default_config(client, app.app_id)

        select_wildkatze_version(
            client, config.config_id, os.environ.get("DICEHUB_WILDKATZE_VERSION")
        )
        upload_case(client, config.config_id, case_path, case_files)
        print(f"Uploaded {len(case_files)} case files")
        configure_machine(client, config.config_id, machine.machine_type_id)

        started = start_run(client, config.config_id, machine.machine_type_id)
        print(f"Started run {started.run_id}")
        finished = wait_for_run(client, started.run_id)
        byte_count = download_results(client, finished.run_id, result_path, partial_path)
        print(json.dumps({"result": str(result_path), "bytes": byte_count}))

        if keep_app:
            print(f"Kept app {app.app_id}")
        else:
            delete_example_app(client, app.app_id)


if __name__ == "__main__":
    main()
