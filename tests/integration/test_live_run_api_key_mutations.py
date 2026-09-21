from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

from dicehub import APIError, Client, MutationOutcomeUnknownError, NamespacePermission


def _required_environment(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        pytest.skip(f"{name} is not set for the explicit disposable run target.")
    return value


@pytest.mark.integration
@pytest.mark.live
@pytest.mark.mutating
def test_live_project_keys_start_and_stop_one_disposable_config_run() -> None:
    if os.environ.get("DICEHUB_LIVE_TEST") != "1":
        pytest.skip("Set DICEHUB_LIVE_TEST=1 to run the local API smoke test.")
    if os.environ.get("DICEHUB_LIVE_RUN_API_KEY_MUTATION_TEST") != "1":
        pytest.skip("Set DICEHUB_LIVE_RUN_API_KEY_MUTATION_TEST=1 to allow a charged run mutation.")

    cookie = os.environ.get("DICEHUB_SESSION_COOKIE")
    if cookie is None:
        pytest.skip("DICEHUB_SESSION_COOKIE is not set.")

    project_id = _required_environment("DICEHUB_LIVE_RUN_PROJECT_ID")
    app_id = _required_environment("DICEHUB_LIVE_RUN_APP_ID")
    config_id = _required_environment("DICEHUB_LIVE_RUN_CONFIG_ID")
    machine_type_id = _required_environment("DICEHUB_LIVE_RUN_MACHINE_TYPE_ID")
    base_url = os.environ.get("DICEHUB_URL", "http://127.0.0.1:8080")
    executable = Path(sys.executable).with_name("dicehub")
    if not executable.is_file() or not os.access(executable, os.X_OK):
        pytest.skip("The installed dicehub CLI is unavailable for the live mutation test.")
    marker = uuid.uuid4().hex
    key_names = {
        "start": f"dicehub-python-start-run-{marker}",
        "stop": f"dicehub-python-stop-run-{marker}",
    }
    key_ids: dict[str, str] = {}
    key_delete_outcomes_unknown: set[str] = set()
    run_id: str | None = None
    stop_request_sent = False
    stop_outcome_unknown = False
    cleanup_failures: list[str] = []

    with Client(base_url=base_url, session_cookie=cookie) as session_client:
        baseline_key_ids = {
            key.api_key_id for key in session_client.api_keys.list(namespace_id=project_id)
        }
        baseline_run_ids = {
            run.run_id
            for run in session_client.runs.list(
                namespace_id=app_id,
                app_id=app_id,
                limit=50,
            ).runs
        }

        try:
            start_key = session_client.api_keys.create(
                namespace_id=project_id,
                name=key_names["start"],
                permissions=[NamespacePermission.START_RUN],
            )
            key_ids["start"] = start_key.api_key_id
            stop_key = session_client.api_keys.create(
                namespace_id=project_id,
                name=key_names["stop"],
                permissions=[NamespacePermission.STOP_RUN],
            )
            key_ids["stop"] = stop_key.api_key_id

            with Client(
                base_url=base_url,
                api_key=start_key.value.get_secret_value(),
            ) as start_client:
                try:
                    started = start_client.runs.start(
                        config_id=config_id,
                        machine_type_id=machine_type_id,
                        notify=False,
                    )
                except MutationOutcomeUnknownError:
                    candidates = {
                        run.run_id
                        for run in session_client.runs.list(
                            namespace_id=app_id,
                            app_id=app_id,
                            limit=50,
                        ).runs
                        if run.run_id not in baseline_run_ids
                    }
                    if len(candidates) == 1:
                        run_id = candidates.pop()
                    pytest.fail(
                        "Start outcome unknown; reconcile config ID "
                        f"{config_id!r} and candidate run ID {run_id!r}.",
                        pytrace=False,
                    )
                run_id = started.run_id
                try:
                    start_client.runs.stop(run_id=run_id)
                except APIError:
                    pass
                except MutationOutcomeUnknownError:
                    stop_request_sent = True
                    stop_outcome_unknown = True
                    pytest.fail(
                        f"START_RUN-only key stop outcome unknown; reconcile run ID {run_id!r}.",
                        pytrace=False,
                    )
                else:
                    stop_request_sent = True
                    pytest.fail(
                        f"START_RUN-only key unexpectedly stopped run ID {run_id!r}.",
                        pytrace=False,
                    )

            stop_secret = stop_key.value.get_secret_value()
            stop_request_sent = True
            stop_outcome_unknown = True
            try:
                result = subprocess.run(
                    [
                        str(executable),
                        "run",
                        "stop",
                        run_id,
                        "--yes",
                        "--output",
                        "json",
                    ],
                    capture_output=True,
                    check=False,
                    env={"DICEHUB_API_KEY": stop_secret, "DICEHUB_URL": base_url},
                    text=True,
                    timeout=30,
                )
            except OSError:
                stop_request_sent = False
                stop_outcome_unknown = False
                raise
            assert stop_secret not in result.stdout + result.stderr
            if result.returncode == 5:
                pytest.fail(
                    f"Stop outcome unknown; reconcile run ID {run_id!r}.",
                    pytrace=False,
                )
            if result.returncode != 0:
                if result.returncode in {2, 3, 4}:
                    stop_request_sent = False
                    stop_outcome_unknown = False
                pytest.fail(
                    f"Stop request failed; reconcile run ID {run_id!r}.",
                    pytrace=False,
                )
            stop_outcome_unknown = False
            payload = json.loads(result.stdout)
            assert payload["ok"] is True
            assert payload["data"] == {"run_id": run_id}

            for kind in ("start", "stop"):
                try:
                    session_client.api_keys.delete(api_key_id=key_ids[kind])
                except MutationOutcomeUnknownError:
                    key_delete_outcomes_unknown.add(kind)
                    raise
                else:
                    key_ids.pop(kind)
        finally:
            if run_id is not None and not stop_request_sent:
                try:
                    session_client.runs.stop(run_id=run_id)
                except MutationOutcomeUnknownError:
                    cleanup_failures.append(
                        f"Run cleanup outcome unknown; reconcile run ID {run_id!r}."
                    )
                except Exception:
                    cleanup_failures.append(f"Run cleanup failed; reconcile run ID {run_id!r}.")
            elif run_id is not None and stop_outcome_unknown:
                cleanup_failures.append(
                    f"Stop outcome remains unknown; do not replay run ID {run_id!r} blindly."
                )

            try:
                keys = session_client.api_keys.list(namespace_id=project_id)
            except Exception:
                for key_id in key_ids.values():
                    cleanup_failures.append(f"API-key cleanup failed; reconcile key ID {key_id!r}.")
            else:
                for kind, name in key_names.items():
                    matches = [
                        key
                        for key in keys
                        if key.name == name and key.api_key_id not in baseline_key_ids
                    ]
                    known_id = key_ids.get(kind)
                    if kind in key_delete_outcomes_unknown:
                        if any(key.api_key_id == known_id for key in matches):
                            cleanup_failures.append(
                                "API-key deletion outcome unknown; do not replay key ID "
                                f"{known_id!r} blindly."
                            )
                        continue
                    if known_id is not None:
                        matches = [key for key in matches if key.api_key_id == known_id]
                    if not matches:
                        continue
                    if len(matches) != 1:
                        cleanup_failures.append(
                            f"API-key cleanup could not verify {kind} key {known_id!r}."
                        )
                        continue
                    try:
                        session_client.api_keys.delete(api_key_id=matches[0].api_key_id)
                    except Exception:
                        cleanup_failures.append(
                            f"API-key cleanup failed; reconcile key ID {matches[0].api_key_id!r}."
                        )

            if cleanup_failures:
                pytest.fail(" ".join(cleanup_failures), pytrace=False)
