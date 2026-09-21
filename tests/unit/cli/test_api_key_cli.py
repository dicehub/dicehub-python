from __future__ import annotations

import json
import os
from collections.abc import Sequence
from datetime import datetime, timezone
from types import TracebackType
from typing import Any, ClassVar, cast

import pytest
from pydantic import SecretStr
from typer.testing import CliRunner

from dicehub import ApiKey, CreatedApiKey, NamespacePermission
from dicehub import cli as cli_module
from dicehub.api_keys.models import ApiKeyStatus, ApiKeyValidityStatus
from dicehub.cli.commands import api_key as api_key_commands

runner = CliRunner()

SECRET = "cfat_sentinelSecretValue"
SESSION = "sentinel-session-secret"
BASE_URL = "https://dicehub.test"


def _api_key(*, name: str = "gentle-sun-1bce") -> ApiKey:
    return ApiKey(
        api_key_id="71",
        name=name,
        prefix="cfat_sent",
        permissions=(
            NamespacePermission.VIEW_PROJECT_INFO,
            NamespacePermission.VIEW_RUN_INFO,
        ),
        created_at=datetime(2026, 8, 11, 9, 10, 11, 123000, tzinfo=timezone.utc),
        updated_at=datetime(2026, 8, 11, 10, 11, 12, 456000, tzinfo=timezone.utc),
        last_used_at=None,
        status=ApiKeyStatus.ACTIVE,
        not_before=None,
        expires_at=None,
        validity_status=ApiKeyValidityStatus.ACTIVE,
    )


def _created_api_key() -> CreatedApiKey:
    return CreatedApiKey(
        **_api_key().model_dump(),
        value=SecretStr(SECRET),
    )


class _FakeApiKeys:
    calls: ClassVar[list[tuple[str, dict[str, object]]]] = []
    get_result: ClassVar[ApiKey | None] = _api_key()

    def list(self, *, namespace_id: str) -> tuple[ApiKey, ...]:
        self.calls.append(("list", {"namespace_id": namespace_id}))
        return (_api_key(),)

    def get(self, *, namespace_id: str, api_key_id: str) -> ApiKey | None:
        self.calls.append(
            (
                "get",
                {"namespace_id": namespace_id, "api_key_id": api_key_id},
            )
        )
        return self.get_result

    def list_permissions(self, *, namespace_id: str) -> tuple[NamespacePermission, ...]:
        self.calls.append(("list_permissions", {"namespace_id": namespace_id}))
        return (
            NamespacePermission.VIEW_PROJECT_INFO,
            NamespacePermission.VIEW_RUN_INFO,
        )

    def create(
        self,
        *,
        namespace_id: str,
        name: str,
        permissions: Sequence[NamespacePermission],
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

    def update(
        self,
        *,
        namespace_id: str,
        api_key_id: str,
        name: str,
        permissions: Sequence[NamespacePermission] | None = None,
    ) -> ApiKey:
        self.calls.append(
            (
                "update",
                {
                    "namespace_id": namespace_id,
                    "api_key_id": api_key_id,
                    "name": name,
                    "permissions": permissions,
                },
            )
        )
        return _api_key(name=name)

    def delete(self, *, api_key_id: str) -> None:
        self.calls.append(("delete", {"api_key_id": api_key_id}))


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
    _FakeApiKeys.get_result = _api_key()
    _FakeClient.constructions = []
    monkeypatch.delenv("DICEHUB_API_KEY", raising=False)
    monkeypatch.delenv("DICEHUB_SESSION_COOKIE", raising=False)
    monkeypatch.delenv("DICEHUB_URL", raising=False)
    monkeypatch.setattr(api_key_commands, "Client", _FakeClient)


def _session_environment() -> dict[str, str]:
    return {
        "DICEHUB_SESSION_COOKIE": SESSION,
        "DICEHUB_URL": BASE_URL,
    }


def _json(result: Any) -> dict[str, Any]:
    assert result.stderr == ""
    assert result.stdout.count("\n") == 1
    payload = json.loads(result.stdout)
    assert isinstance(payload, dict)
    return cast(dict[str, Any], payload)


def _assert_session_client() -> None:
    assert _FakeClient.constructions == [
        {
            "base_url": BASE_URL,
            "api_key": None,
            "session_cookie": SESSION,
        }
    ]


def test_list_uses_session_and_emits_complete_metadata() -> None:
    result = runner.invoke(
        cli_module.app,
        ["api-key", "list", "41"],
        env=_session_environment(),
    )

    assert result.exit_code == 0, result.output
    _assert_session_client()
    assert _FakeApiKeys.calls == [("list", {"namespace_id": "41"})]
    assert _json(result) == {
        "schema_version": "dicehub.cli/v1",
        "ok": True,
        "data": {
            "api_keys": [
                {
                    "api_key_id": "71",
                    "name": "gentle-sun-1bce",
                    "prefix": "cfat_sent",
                    "permissions": ["VIEW_PROJECT_INFO", "VIEW_RUN_INFO"],
                    "created_at": "2026-08-11T09:10:11.123000Z",
                    "updated_at": "2026-08-11T10:11:12.456000Z",
                    "last_used_at": None,
                    "status": "ACTIVE",
                    "not_before": None,
                    "expires_at": None,
                    "validity_status": "ACTIVE",
                }
            ]
        },
        "error": None,
    }
    assert SESSION not in result.stdout + result.stderr


def test_get_passes_scope_and_key_ids() -> None:
    result = runner.invoke(
        cli_module.app,
        ["api-key", "get", "41", "71"],
        env=_session_environment(),
    )

    assert result.exit_code == 0, result.output
    assert _FakeApiKeys.calls == [("get", {"namespace_id": "41", "api_key_id": "71"})]
    assert _json(result)["data"]["api_key"]["api_key_id"] == "71"


@pytest.mark.parametrize(
    ("output", "expected"),
    [
        ("json", {"api_key": None}),
        ("text", "No API key found.\n"),
    ],
)
def test_get_missing_is_a_successful_null_read(output: str, expected: object) -> None:
    _FakeApiKeys.get_result = None
    result = runner.invoke(
        cli_module.app,
        ["api-key", "get", "41", "999", "--output", output],
        env=_session_environment(),
    )

    assert result.exit_code == 0, result.output
    if output == "json":
        assert _json(result)["data"] == expected
    else:
        assert result.stdout == expected


def test_permissions_emits_server_assignable_catalog() -> None:
    result = runner.invoke(
        cli_module.app,
        ["api-key", "permissions", "41"],
        env=_session_environment(),
    )

    assert result.exit_code == 0, result.output
    assert _FakeApiKeys.calls == [("list_permissions", {"namespace_id": "41"})]
    assert _json(result)["data"] == {"permissions": ["VIEW_PROJECT_INFO", "VIEW_RUN_INFO"]}


@pytest.mark.parametrize("output", ["json", "text"])
def test_create_delivers_secret_only_to_explicit_fd(output: str) -> None:
    read_fd, write_fd = os.pipe()
    try:
        result = runner.invoke(
            cli_module.app,
            [
                "api-key",
                "create",
                "41",
                "--name",
                "gentle-sun-1bce",
                "--secret-fd",
                str(write_fd),
                "--permission",
                "view_project_info",
                "--permission",
                "VIEW_RUN_INFO",
                "--output",
                output,
            ],
            env=_session_environment(),
        )
        os.close(write_fd)
        write_fd = -1
        delivered_secret = os.read(read_fd, 4096).decode("ascii")
    finally:
        os.close(read_fd)
        if write_fd >= 0:
            os.close(write_fd)

    assert result.exit_code == 0, result.output
    assert _FakeApiKeys.calls == [
        (
            "create",
            {
                "namespace_id": "41",
                "name": "gentle-sun-1bce",
                "permissions": [
                    NamespacePermission.VIEW_PROJECT_INFO,
                    NamespacePermission.VIEW_RUN_INFO,
                ],
                "not_before": None,
                "expires_at": None,
            },
        )
    ]
    assert delivered_secret == f"{SECRET}\n"
    assert result.stdout.count(SECRET) == 0
    assert "**********" not in result.stdout
    assert SESSION not in result.stdout + result.stderr
    if output == "json":
        assert "value" not in _json(result)["data"]["api_key"]
    else:
        assert result.stdout.count("\n") == 1


def test_create_passes_validity_timestamps() -> None:
    read_fd, write_fd = os.pipe()
    try:
        result = runner.invoke(
            cli_module.app,
            [
                "api-key",
                "create",
                "41",
                "--name",
                "scheduled agent",
                "--secret-fd",
                str(write_fd),
                "--permission",
                "VIEW_PROJECT_INFO",
                "--not-before",
                "2026-08-17T09:00:00+02:00",
                "--expires-at",
                "2026-09-17T09:00:00+02:00",
            ],
            env=_session_environment(),
        )
        os.close(write_fd)
        write_fd = -1
        os.read(read_fd, 4096)
    finally:
        os.close(read_fd)
        if write_fd >= 0:
            os.close(write_fd)

    assert result.exit_code == 0, result.output
    assert _FakeApiKeys.calls[0] == (
        "create",
        {
            "namespace_id": "41",
            "name": "scheduled agent",
            "permissions": [NamespacePermission.VIEW_PROJECT_INFO],
            "not_before": datetime(2026, 8, 17, 7, tzinfo=timezone.utc),
            "expires_at": datetime(2026, 9, 17, 7, tzinfo=timezone.utc),
        },
    )


def test_create_requires_permission_before_client_construction() -> None:
    read_fd, write_fd = os.pipe()
    try:
        result = runner.invoke(
            cli_module.app,
            [
                "api-key",
                "create",
                "41",
                "--name",
                "gentle-sun-1bce",
                "--secret-fd",
                str(write_fd),
            ],
            env=_session_environment(),
        )
    finally:
        os.close(read_fd)
        os.close(write_fd)

    assert result.exit_code == 2
    assert _FakeClient.constructions == []
    assert _json(result)["error"]["message"] == "At least one --permission is required."


@pytest.mark.parametrize(
    ("permission_arguments", "expected_permissions"),
    [
        ([], None),
        (
            ["--permission", "VIEW_PROJECT_INFO", "--permission", "VIEW_RUN_INFO"],
            [
                NamespacePermission.VIEW_PROJECT_INFO,
                NamespacePermission.VIEW_RUN_INFO,
            ],
        ),
    ],
)
def test_update_preserves_or_replaces_complete_permission_set(
    permission_arguments: list[str],
    expected_permissions: list[NamespacePermission] | None,
) -> None:
    result = runner.invoke(
        cli_module.app,
        [
            "api-key",
            "update",
            "41",
            "71",
            "--name",
            "bold-mountain-22f4",
            *permission_arguments,
        ],
        env=_session_environment(),
    )

    assert result.exit_code == 0, result.output
    assert _FakeApiKeys.calls == [
        (
            "update",
            {
                "namespace_id": "41",
                "api_key_id": "71",
                "name": "bold-mountain-22f4",
                "permissions": expected_permissions,
            },
        )
    ]
    assert _json(result)["data"]["api_key"]["name"] == "bold-mountain-22f4"


def test_duplicate_permissions_fail_before_client_construction() -> None:
    result = runner.invoke(
        cli_module.app,
        [
            "api-key",
            "update",
            "41",
            "71",
            "--name",
            "bold-mountain-22f4",
            "--permission",
            "VIEW_RUN_INFO",
            "--permission",
            "VIEW_RUN_INFO",
        ],
        env=_session_environment(),
    )

    assert result.exit_code == 2
    assert _FakeClient.constructions == []
    assert _json(result)["error"]["message"] == "--permission values must be unique."


def test_revoke_requires_yes_before_client_construction() -> None:
    result = runner.invoke(
        cli_module.app,
        ["api-key", "revoke", "71"],
        env=_session_environment(),
    )

    assert result.exit_code == 2
    assert _FakeClient.constructions == []
    assert _FakeApiKeys.calls == []
    assert _json(result)["error"]["message"] == "API-key revocation requires --yes."


def test_revoke_uses_exact_id_and_explicit_confirmation() -> None:
    result = runner.invoke(
        cli_module.app,
        ["api-key", "revoke", "71", "--yes"],
        env=_session_environment(),
    )

    assert result.exit_code == 0, result.output
    _assert_session_client()
    assert _FakeApiKeys.calls == [("delete", {"api_key_id": "71"})]
    assert _json(result)["data"] == {"api_key_id": "71"}
