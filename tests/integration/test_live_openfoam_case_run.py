from __future__ import annotations

import os
from pathlib import Path
from zipfile import ZipFile

import pytest

import dicehub as dh
from examples import openfoam_case_run


def _cleanup_live_resources(
    client: dh.Client,
    app_id: str,
    run_id: str | None,
    *,
    run_is_terminal: bool,
    start_outcome_unknown: bool,
) -> None:
    """Stop a known active run, then delete the exact app created by the test."""

    if start_outcome_unknown:
        return
    if run_id is not None and not run_is_terminal:
        try:
            client.runs.stop(run_id=run_id)
        except (dh.APIError, dh.MutationOutcomeUnknownError):
            pass
        try:
            client.runs.wait(run_id=run_id, timeout_seconds=300, poll_seconds=5)
        except dh.RunFailedError:
            pass
    client.apps.delete(app_id=app_id)


@pytest.mark.integration
@pytest.mark.live
@pytest.mark.mutating
def test_live_openfoam_case_run(tmp_path: Path) -> None:
    if os.environ.get("DICEHUB_LIVE_TEST") != "1":
        pytest.skip("Set DICEHUB_LIVE_TEST=1 to enable live tests.")
    if os.environ.get("DICEHUB_LIVE_OPENFOAM_CASE_RUN_TEST") != "1":
        pytest.skip(
            "Set DICEHUB_LIVE_OPENFOAM_CASE_RUN_TEST=1 to approve the charged run and cleanup."
        )

    root = Path(__file__).parents[2]
    case_path = root / "examples/openfoam_case_run_case"
    result_path = tmp_path / "openfoam-case-results.zip"
    case_files = openfoam_case_run.collect_case_files(case_path)
    partial_path = openfoam_case_run.prepare_result_path(result_path)

    with dh.Client(
        base_url=os.environ.get("DICEHUB_URL", "https://dicehub.com"),
        api_key=os.environ["DICEHUB_API_KEY"],
    ) as client:
        project = openfoam_case_run.resolve_project(
            client,
            os.environ["DICEHUB_PROJECT_URL"],
        )
        app = openfoam_case_run.create_case_run_app(
            client,
            project.project_id,
        )
        run_id: str | None = None
        run_is_terminal = False
        start_outcome_unknown = False

        try:
            config = openfoam_case_run.get_default_config(client, app.app_id)
            openfoam_case_run.upload_case(client, config.config_id, case_path, case_files)
            openfoam_case_run.select_openfoam_14(client, config.config_id)

            machine = openfoam_case_run.select_machine(
                client,
                os.environ["DICEHUB_MACHINE_TYPE_ID"],
            )
            openfoam_case_run.configure_machine(
                client,
                config.config_id,
                machine.machine_type_id,
            )

            try:
                started = openfoam_case_run.start_run(
                    client,
                    config.config_id,
                    machine.machine_type_id,
                )
            except dh.MutationOutcomeUnknownError:
                start_outcome_unknown = True
                raise
            run_id = started.run_id

            try:
                finished = openfoam_case_run.wait_for_run(client, run_id)
            except dh.RunFailedError:
                run_is_terminal = True
                raise
            run_is_terminal = True

            openfoam_case_run.download_results(
                client,
                finished.run_id,
                result_path,
                partial_path,
            )
        finally:
            _cleanup_live_resources(
                client,
                app.app_id,
                run_id,
                run_is_terminal=run_is_terminal,
                start_outcome_unknown=start_outcome_unknown,
            )

    with ZipFile(result_path) as results:
        assert {"case/0.1/U", "case/0.1/p", "case/0.1/phi"} <= set(results.namelist())
