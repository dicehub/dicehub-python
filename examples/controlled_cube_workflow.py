"""Create, mesh, validate, and clean up one deterministic cube through public APIs."""

from __future__ import annotations

import io
import json
import os
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TypeVar

import dicehub as dh
from examples._controlled_cube import (
    CONFIG_CAMERA_ROLL_DEGREES,
    CUBE_STL,
    MAX_RESULT_ARCHIVE_BYTES,
    SCENE_SETTINGS_PATH,
    TERMINAL_RUN_STATES,
    ControlledCubeError,
    config_camera_roll,
    rotate_config_camera,
    validate_result_archive,
    wait_for_finished,
)
from examples._controlled_cube_cleanup import cleanup_failed as _cleanup_failed
from examples._controlled_cube_cleanup import stop_for_cleanup as _stop_for_cleanup_impl
from examples._controlled_cube_geometry import (
    GEOMETRY_FILENAME,
    GEOMETRY_VTP_PATH,
    GEOMETRY_YAML_PATH,
    refine_imported_geometry,
    validate_refined_geometry_yaml,
    verify_imported_geometry,
)
from examples._controlled_cube_setup import validate_scene_settings, verify_generated_setup

ResultT = TypeVar("ResultT")
SNAPPY_TEMPLATE_ROUTE = "/templates/openfoam_snappyhexmesh"


@dataclass(frozen=True)
class Settings:
    base_url: str
    api_key: str = field(repr=False)
    result_zip: Path
    timeout_seconds: float
    poll_seconds: float
    stop_timeout_seconds: float


def load_settings() -> Settings:
    """Load and validate all operator input before making any mutation."""

    if os.environ.get("DICEHUB_LIVE_TEST") != "1":
        raise ControlledCubeError("Set DICEHUB_LIVE_TEST=1 to enable live requests.")
    if os.environ.get("DICEHUB_LIVE_CONTROLLED_CUBE_TEST") != "1":
        raise ControlledCubeError(
            "Set DICEHUB_LIVE_CONTROLLED_CUBE_TEST=1 to approve the charged run and cleanup."
        )
    base_url = os.environ.get("DICEHUB_URL", "https://dicehub.com")
    api_key = _required_environment("DICEHUB_API_KEY")
    result_zip = Path(_required_environment("DICEHUB_CONTROLLED_CUBE_RESULT_ZIP"))
    if not result_zip.parent.is_dir():
        raise ControlledCubeError("The result ZIP parent directory does not exist.")
    if result_zip.exists():
        raise ControlledCubeError("The result ZIP destination already exists.")

    timeout_seconds = _positive_seconds("DICEHUB_RUN_TIMEOUT_SECONDS", "1800")
    poll_seconds = _positive_seconds("DICEHUB_RUN_POLL_SECONDS", "5")
    stop_timeout_seconds = _positive_seconds("DICEHUB_RUN_STOP_TIMEOUT_SECONDS", "300")
    if poll_seconds > timeout_seconds:
        raise ControlledCubeError("The poll interval cannot exceed the run timeout.")
    if poll_seconds > stop_timeout_seconds:
        raise ControlledCubeError("The poll interval cannot exceed the run stop timeout.")
    return Settings(
        base_url=base_url,
        api_key=api_key,
        result_zip=result_zip,
        timeout_seconds=timeout_seconds,
        poll_seconds=poll_seconds,
        stop_timeout_seconds=stop_timeout_seconds,
    )


def run(settings: Settings) -> None:
    """Execute the six-step lifecycle and delete only its returned project ID."""

    marker = uuid.uuid4().hex
    project_id: str | None = None
    conversion_run_id: str | None = None
    conversion_run_state: dh.RunState | None = None
    setup_run_id: str | None = None
    setup_run_state: dh.RunState | None = None
    run_id: str | None = None
    last_run_state: dh.RunState | None = None
    untracked_run_possible = False
    primary_error: BaseException | None = None

    with dh.Client(base_url=settings.base_url, api_key=settings.api_key) as client:
        try:
            template = _snappy_template(client)
            _emit(
                "0_template_resolved",
                template_id=template.template_id,
                route=template.route,
            )

            project = _mutation(
                "project creation",
                f"personal project marker {marker!r}",
                lambda: client.projects.create(
                    name=f"dicehub controlled cube {marker}",
                    slug=f"dh-controlled-cube-{marker}",
                    description="Temporary SDK example; safe to delete after the run",
                    visibility=dh.ProjectVisibility.PRIVATE,
                ),
            )
            project_id = project.project_id
            _emit("1_project_created", project_id=project_id)

            app = _mutation(
                "app creation",
                f"project ID {project_id!r} and app marker {marker!r}",
                lambda: client.apps.create(
                    project_id=project_id,
                    template_id=template.template_id,
                    name=f"Controlled cube mesh {marker}",
                    description="Deterministic one-metre watertight cube",
                ),
            )
            config_id = _default_config_id(client, app.app_id)
            _emit("1_app_created", app_id=app.app_id, config_id=config_id)

            _mutation(
                "cube upload",
                f"config ID {config_id!r}, path 'case/constant/triSurface/cube.stl'",
                lambda: client.configs.upload_file(
                    config_id=config_id,
                    path="case/constant/triSurface/cube.stl",
                    source=io.BytesIO(CUBE_STL),
                ),
            )
            _emit("2_cube_uploaded", bytes=len(CUBE_STL))

            try:
                geometry_import = _mutation(
                    "geometry import",
                    f"config ID {config_id!r}; inspect its run history before any manual retry",
                    lambda: client.configs.import_geometry(
                        config_id=config_id,
                        filename=GEOMETRY_FILENAME,
                    ),
                )
            except ControlledCubeError as error:
                untracked_run_possible = isinstance(error.__cause__, dh.MutationOutcomeUnknownError)
                raise
            conversion = geometry_import.conversion_run
            conversion_run_id = conversion.run_id
            conversion_run_state = conversion.state
            setup = geometry_import.setup_run
            if setup is None:
                raise ControlledCubeError(
                    "The fresh app did not schedule its required background-mesh setup run."
                )
            setup_run_id = setup.run_id
            setup_run_state = setup.state
            _emit(
                "3_geometry_conversion_started",
                run_id=conversion.run_id,
                state=conversion.state.value,
            )
            _emit(
                "3_geometry_setup_queued",
                run_id=setup.run_id,
                state=setup.state.value,
            )

            def report_conversion(status: dh.RunStatus) -> None:
                nonlocal conversion_run_state
                if status.state is not conversion_run_state:
                    _emit(
                        "3_geometry_conversion_status",
                        run_id=status.run_id,
                        state=status.state.value,
                    )
                    conversion_run_state = status.state

            converted = wait_for_finished(
                lambda: client.runs.status(run_id=conversion.run_id),
                timeout_seconds=settings.timeout_seconds,
                poll_seconds=settings.poll_seconds,
                on_status=report_conversion,
            )
            conversion_run_state = converted.state

            def report_setup(status: dh.RunStatus) -> None:
                nonlocal setup_run_state
                if status.state is not setup_run_state:
                    _emit(
                        "3_geometry_setup_status",
                        run_id=status.run_id,
                        state=status.state.value,
                    )
                    setup_run_state = status.state

            configured = wait_for_finished(
                lambda: client.runs.status(run_id=setup.run_id),
                timeout_seconds=settings.timeout_seconds,
                poll_seconds=settings.poll_seconds,
                on_status=report_setup,
            )
            setup_run_state = configured.state
            geometry_yaml = verify_imported_geometry(client, config_id)
            generated_setup = verify_generated_setup(client, config_id)
            _emit(
                "3_geometry_import_validated",
                bounds_max=generated_setup.bounds_max,
                bounds_min=generated_setup.bounds_min,
                cells=generated_setup.cells,
                material_point=generated_setup.material_point,
                path=GEOMETRY_YAML_PATH,
                vtp_path=GEOMETRY_VTP_PATH,
            )

            _configure_geometry_refinement(client, config_id, geometry_yaml)
            _emit(
                "4_refinement_configured",
                feature_levels=(0, 1),
                path=GEOMETRY_YAML_PATH,
                surface_level=(1, 1),
            )
            _rotate_camera(client, config_id, original=generated_setup.scene_settings)
            _emit(
                "4_camera_rotated",
                path=SCENE_SETTINGS_PATH,
                roll_degrees=CONFIG_CAMERA_ROLL_DEGREES,
                scene="config",
            )

            try:
                started = _mutation(
                    "run start",
                    f"config ID {config_id!r}; inspect its run history before any manual retry",
                    lambda: client.runs.start(
                        config_id=config_id,
                        machine_type_id="local",
                        node_count=1,
                        cpu_count=1,
                        notify=False,
                    ),
                )
            except ControlledCubeError as error:
                untracked_run_possible = isinstance(error.__cause__, dh.MutationOutcomeUnknownError)
                raise
            run_id = started.run_id
            last_run_state = started.state
            _emit("5_run_started", run_id=started.run_id, state=started.state.value)

            def report(status: dh.RunStatus) -> None:
                nonlocal last_run_state
                if status.state is not last_run_state:
                    _emit("6_run_status", run_id=status.run_id, state=status.state.value)
                    last_run_state = status.state

            finished = wait_for_finished(
                lambda: client.runs.status(run_id=started.run_id),
                timeout_seconds=settings.timeout_seconds,
                poll_seconds=settings.poll_seconds,
                on_status=report,
            )
            last_run_state = finished.state
            _download_results(client, finished.run_id, settings.result_zip)
            summary = validate_result_archive(settings.result_zip)
            _emit(
                "6_results_validated",
                run_id=finished.run_id,
                destination=str(settings.result_zip),
                **asdict(summary),
            )
        except BaseException as error:
            primary_error = error
            raise
        finally:
            if project_id is not None:
                ready_to_delete = (
                    _stop_tracked_runs_for_cleanup(
                        client,
                        (
                            (conversion_run_id, conversion_run_state),
                            (setup_run_id, setup_run_state),
                            (run_id, last_run_state),
                        ),
                        settings=settings,
                        primary_error=primary_error,
                    )
                    and not untracked_run_possible
                )
                if ready_to_delete:
                    _delete_project(client, project_id, primary_error)
                elif untracked_run_possible:
                    _emit("cleanup_project_preserved", project_id=project_id)


def _default_config_id(client: dh.Client, app_id: str) -> str:
    configs = client.configs.list(app_id=app_id, limit=50).configs
    defaults = [config.config_id for config in configs if config.is_default]
    if len(defaults) != 1:
        raise ControlledCubeError(
            f"App {app_id} returned {len(defaults)} default configurations; expected exactly one."
        )
    return defaults[0]


def _snappy_template(client: dh.Client) -> dh.Template:
    template = client.templates.get_by_route(route=SNAPPY_TEMPLATE_ROUTE)
    if (
        template is None
        or template.route is None
        or template.route.lower() != SNAPPY_TEMPLATE_ROUTE
        or template.slug != "openfoam_snappyhexmesh"
    ):
        raise ControlledCubeError(f"The required {SNAPPY_TEMPLATE_ROUTE} template is unavailable.")
    return template


def _set_text(client: dh.Client, config_id: str, path: str, content: str) -> None:
    _mutation(
        "config text update",
        f"config ID {config_id!r}, path {path!r}",
        lambda: client.configs.set_text(config_id=config_id, path=path, content=content),
    )


def _rotate_camera(client: dh.Client, config_id: str, *, original: str | None = None) -> None:
    if original is None:
        original = client.configs.get_text(config_id=config_id, path=SCENE_SETTINGS_PATH)
    validate_scene_settings(original)
    updated = rotate_config_camera(original)
    _set_text(client, config_id, SCENE_SETTINGS_PATH, updated)
    persisted = client.configs.get_text(config_id=config_id, path=SCENE_SETTINGS_PATH)
    if persisted != updated or config_camera_roll(persisted) != CONFIG_CAMERA_ROLL_DEGREES:
        raise ControlledCubeError(
            f"The {SCENE_SETTINGS_PATH} camera rotation did not persist exactly."
        )


def _configure_geometry_refinement(
    client: dh.Client,
    config_id: str,
    original: str,
) -> None:
    updated = refine_imported_geometry(original)
    _set_text(client, config_id, GEOMETRY_YAML_PATH, updated)
    persisted = client.configs.get_text(config_id=config_id, path=GEOMETRY_YAML_PATH)
    if persisted != updated:
        raise ControlledCubeError("The geometry refinement update did not persist exactly.")
    validate_refined_geometry_yaml(persisted)


def _download_results(client: dh.Client, run_id: str, destination: Path) -> None:
    created = False
    try:
        with destination.open("xb") as stream:
            created = True
            client.runs.download_results(
                run_id=run_id,
                destination=stream,
                max_bytes=MAX_RESULT_ARCHIVE_BYTES,
            )
    except BaseException:
        if created:
            destination.unlink(missing_ok=True)
        raise


def _stop_tracked_runs_for_cleanup(
    client: dh.Client,
    tracked_runs: tuple[tuple[str | None, dh.RunState | None], ...],
    *,
    settings: Settings,
    primary_error: BaseException | None,
) -> bool:
    ready = True
    for run_id, state in tracked_runs:
        if run_id is not None and state not in TERMINAL_RUN_STATES:
            ready = (
                _stop_for_cleanup(
                    client,
                    run_id,
                    settings=settings,
                    primary_error=primary_error,
                )
                and ready
            )
    return ready


def _stop_for_cleanup(
    client: dh.Client,
    run_id: str,
    *,
    settings: Settings,
    primary_error: BaseException | None,
) -> bool:
    return _stop_for_cleanup_impl(
        client,
        run_id,
        settings=settings,
        primary_error=primary_error,
        emit=_emit,
    )


def _delete_project(
    client: dh.Client,
    project_id: str,
    primary_error: BaseException | None,
) -> None:
    try:
        client.projects.delete(project_id=project_id)
        _emit("cleanup_project_deleted", project_id=project_id)
    except dh.MutationOutcomeUnknownError as cleanup_error:
        _cleanup_failed(
            project_id,
            "cleanup outcome unknown; do not retry blindly",
            cleanup_error,
            primary_error,
            resource="project",
        )
    except Exception as cleanup_error:
        _cleanup_failed(
            project_id,
            "cleanup failed",
            cleanup_error,
            primary_error,
            resource="project",
        )


def _mutation(action: str, reconcile: str, operation: Callable[[], ResultT]) -> ResultT:
    try:
        return operation()
    except dh.MutationOutcomeUnknownError as error:
        raise ControlledCubeError(
            f"{action.capitalize()} outcome unknown; reconcile {reconcile}. Do not retry."
        ) from error


def _required_environment(name: str) -> str:
    value = os.environ.get(name)
    if value is None or not value:
        raise ControlledCubeError(f"{name} is required.")
    return value


def _positive_seconds(name: str, default: str) -> float:
    raw = os.environ.get(name, default)
    try:
        value = float(raw)
    except ValueError as error:
        raise ControlledCubeError(f"{name} must be a positive number of seconds.") from error
    if not 0 < value <= 14_400:
        raise ControlledCubeError(f"{name} must be greater than zero and at most 14400.")
    return value


def _emit(event: str, **values: object) -> None:
    print(json.dumps({"event": event, **values}, ensure_ascii=True, sort_keys=True), flush=True)


def main() -> None:
    run(load_settings())


if __name__ == "__main__":
    main()
