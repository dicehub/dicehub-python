from __future__ import annotations

import json
import os
import stat
import tempfile
from datetime import datetime, timezone
from types import SimpleNamespace, TracebackType
from typing import Any, ClassVar, cast

import pytest
from pydantic import SecretStr
from typer.testing import CliRunner

from dicehub import CreatedApiKey, NamespacePermission
from dicehub import cli as cli_module
from dicehub.api_keys.models import ApiKeyStatus
from dicehub.cli.commands import api_key as api_key_commands

runner = CliRunner()

SECRET = "cfat_sentinelSecretValue"
SESSION = "sentinel-session-secret"
BASE_URL = "https://dicehub.test"


def _created_api_key() -> CreatedApiKey:
    timestamp = datetime(2026, 8, 11, 9, 10, 11, tzinfo=timezone.utc)
    return CreatedApiKey(
        api_key_id="71",
        name="gentle-sun-1bce",
        prefix="cfat_sent",
        permissions=(NamespacePermission.VIEW_RUN_INFO,),
        created_at=timestamp,
        updated_at=timestamp,
        last_used_at=None,
        status=ApiKeyStatus.ACTIVE,
        value=SecretStr(SECRET),
    )


class _FakeApiKeys:
    calls: ClassVar[list[tuple[str, dict[str, object]]]] = []

    def create(
        self,
        *,
        namespace_id: str,
        name: str,
        permissions: list[NamespacePermission],
        not_before: datetime | None = None,
        expires_at: datetime | None = None,
    ) -> CreatedApiKey:
        self.calls.append(
            (
                "create",
                {
                    "namespace_id": namespace_id,
                    "name": name,
                    "permissions": permissions,
                    "not_before": not_before,
                    "expires_at": expires_at,
                },
            )
        )
        return _created_api_key()


class _FakeClient:
    api_keys = _FakeApiKeys()
    constructions: ClassVar[list[dict[str, object]]] = []

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None = None,
        session_cookie: str | None = None,
    ) -> None:
        self.constructions.append(
            {
                "base_url": base_url,
                "api_key": api_key,
                "session_cookie": session_cookie,
            }
        )

    def __enter__(self) -> _FakeClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None


@pytest.fixture(autouse=True)
def reset_fakes(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeApiKeys.calls = []
    _FakeClient.constructions = []
    monkeypatch.delenv("DICEHUB_API_KEY", raising=False)
    monkeypatch.delenv("DICEHUB_SESSION_COOKIE", raising=False)
    monkeypatch.delenv("DICEHUB_URL", raising=False)
    monkeypatch.setattr(api_key_commands, "Client", _FakeClient)


def _json(result: Any) -> dict[str, Any]:
    assert result.stderr == ""
    assert result.stdout.count("\n") == 1
    payload = json.loads(result.stdout)
    assert isinstance(payload, dict)
    return cast(dict[str, Any], payload)


def _create_arguments(secret_fd: int) -> list[str]:
    return [
        "api-key",
        "create",
        "41",
        "--name",
        "gentle-sun-1bce",
        "--secret-fd",
        str(secret_fd),
        "--permission",
        "VIEW_RUN_INFO",
    ]


def _pipe_stat(secret_fd: int) -> SimpleNamespace:
    return SimpleNamespace(
        st_mode=stat.S_IFIFO,
        st_dev=1,
        st_ino=secret_fd + 100,
    )


def test_create_requires_explicit_non_stdio_secret_fd() -> None:
    missing = runner.invoke(
        cli_module.app,
        [
            "api-key",
            "create",
            "41",
            "--name",
            "gentle-sun-1bce",
            "--permission",
            "VIEW_RUN_INFO",
        ],
        env={"DICEHUB_SESSION_COOKIE": SESSION, "DICEHUB_URL": BASE_URL},
    )
    stdio = runner.invoke(
        cli_module.app,
        _create_arguments(1),
        env={"DICEHUB_SESSION_COOKIE": SESSION, "DICEHUB_URL": BASE_URL},
    )

    assert missing.exit_code == 2
    assert stdio.exit_code == 2
    assert _FakeClient.constructions == []
    assert _FakeApiKeys.calls == []
    assert SECRET not in missing.stdout + missing.stderr + stdio.stdout + stdio.stderr


def test_create_rejects_unwritable_secret_fd_before_client_construction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def reject_write(secret_fd: int, data: bytes | memoryview) -> int:
        raise OSError("descriptor is not writable")

    monkeypatch.setattr(
        os,
        "fstat",
        _pipe_stat,
    )
    monkeypatch.setattr(os, "isatty", lambda secret_fd: False)
    monkeypatch.setattr(os, "write", reject_write)
    result = runner.invoke(
        cli_module.app,
        _create_arguments(3),
        env={"DICEHUB_SESSION_COOKIE": SESSION, "DICEHUB_URL": BASE_URL},
    )

    assert result.exit_code == 2
    assert _FakeClient.constructions == []
    assert _FakeApiKeys.calls == []
    assert _json(result)["error"]["message"] == (
        "--secret-fd must reference an open writable non-stdio pipe or socket."
    )


def test_create_rejects_regular_file_secret_sink_before_client_construction() -> None:
    with tempfile.TemporaryFile(mode="w+b") as secret_file:
        result = runner.invoke(
            cli_module.app,
            _create_arguments(secret_file.fileno()),
            env={"DICEHUB_SESSION_COOKIE": SESSION, "DICEHUB_URL": BASE_URL},
        )

    assert result.exit_code == 2
    assert _FakeClient.constructions == []
    assert _FakeApiKeys.calls == []
    assert _json(result)["error"]["message"] == (
        "--secret-fd must reference an open writable non-stdio pipe or socket."
    )


def test_create_rejects_descriptor_aliased_to_stdout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def aliased_fstat(secret_fd: int) -> SimpleNamespace:
        inode = 101 if secret_fd in (1, 3) else secret_fd + 100
        return SimpleNamespace(st_mode=stat.S_IFIFO, st_dev=1, st_ino=inode)

    monkeypatch.setattr(os, "fstat", aliased_fstat)
    monkeypatch.setattr(os, "isatty", lambda secret_fd: False)
    result = runner.invoke(
        cli_module.app,
        _create_arguments(3),
        env={"DICEHUB_SESSION_COOKIE": SESSION, "DICEHUB_URL": BASE_URL},
    )

    assert result.exit_code == 2
    assert _FakeClient.constructions == []
    assert _FakeApiKeys.calls == []
    assert _json(result)["error"]["message"] == (
        "--secret-fd must reference an open writable non-stdio pipe or socket."
    )


def test_create_completes_partial_writes_without_echoing_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chunks: list[bytes] = []

    def partial_write(secret_fd: int, data: bytes | memoryview) -> int:
        if not data:
            return 0
        length = min(len(data), 4)
        chunks.append(bytes(data[:length]))
        return length

    monkeypatch.setattr(
        os,
        "fstat",
        _pipe_stat,
    )
    monkeypatch.setattr(os, "isatty", lambda secret_fd: False)
    monkeypatch.setattr(os, "write", partial_write)
    result = runner.invoke(
        cli_module.app,
        _create_arguments(3),
        env={"DICEHUB_SESSION_COOKIE": SESSION, "DICEHUB_URL": BASE_URL},
    )

    assert result.exit_code == 0, result.output
    assert b"".join(chunks).decode("ascii") == f"{SECRET}\n"
    combined = result.stdout + result.stderr + repr(result.exception)
    assert SECRET not in combined
    assert "**********" not in combined
    assert "value" not in _json(result)["data"]["api_key"]


def test_create_delivery_failure_reports_key_id_without_exposing_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_after_validation(secret_fd: int, data: bytes | memoryview) -> int:
        if not data:
            return 0
        raise OSError("delivery failed")

    monkeypatch.setattr(
        os,
        "fstat",
        _pipe_stat,
    )
    monkeypatch.setattr(os, "isatty", lambda secret_fd: False)
    monkeypatch.setattr(os, "write", fail_after_validation)
    result = runner.invoke(
        cli_module.app,
        _create_arguments(3),
        env={"DICEHUB_SESSION_COOKIE": SESSION, "DICEHUB_URL": BASE_URL},
    )

    assert result.exit_code == 1
    assert _FakeApiKeys.calls[0][0] == "create"
    assert _json(result)["error"]["message"] == (
        "API key 71 was created, but its secret could not be delivered. "
        "Revoke API key 71 before retrying."
    )
    combined = result.stdout + result.stderr + repr(result.exception)
    assert SECRET not in combined
    assert "**********" not in combined


@pytest.mark.parametrize(
    "arguments",
    [
        ["api-key", "list", "41"],
        ["api-key", "get", "41", "71"],
        ["api-key", "permissions", "41"],
        _create_arguments(3),
        ["api-key", "update", "41", "71", "--name", "bold-mountain-22f4"],
        ["api-key", "revoke", "71", "--yes"],
    ],
)
def test_every_command_rejects_api_key_authentication_before_client_construction(
    arguments: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        os,
        "fstat",
        _pipe_stat,
    )
    monkeypatch.setattr(os, "isatty", lambda secret_fd: False)
    monkeypatch.setattr(os, "write", lambda secret_fd, data: len(data))
    result = runner.invoke(
        cli_module.app,
        arguments,
        env={"DICEHUB_API_KEY": "sentinel-api-key", "DICEHUB_URL": BASE_URL},
    )

    assert result.exit_code == 3
    assert _FakeClient.constructions == []
    assert _FakeApiKeys.calls == []
    assert _json(result)["error"] == {
        "code": "AUTH_REQUIRED",
        "message": "API-key administration requires DICEHUB_SESSION_COOKIE.",
        "retryable": False,
    }
    assert "sentinel-api-key" not in result.stdout + result.stderr


def test_api_key_is_rejected_even_when_session_cookie_is_present() -> None:
    result = runner.invoke(
        cli_module.app,
        ["api-key", "list", "41"],
        env={
            "DICEHUB_API_KEY": "sentinel-api-key",
            "DICEHUB_SESSION_COOKIE": SESSION,
            "DICEHUB_URL": BASE_URL,
        },
    )

    assert result.exit_code == 2
    assert _FakeClient.constructions == []
    assert _json(result)["error"]["code"] == "CONFIGURATION_ERROR"
    assert "sentinel-api-key" not in result.stdout + result.stderr
    assert SESSION not in result.stdout + result.stderr
