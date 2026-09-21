from __future__ import annotations

import io
from typing import BinaryIO, cast

import httpx
import pytest

from dicehub import Client, ConfigurationError, MembershipVisibility
from dicehub.groups._validation import MAX_GROUP_AVATAR_BYTES


def _api_key_client(handler: httpx.MockTransport) -> Client:
    return Client(
        base_url="https://dicehub.test",
        api_key="test-api-key",
        transport=handler,
    )


def _session_client(handler: httpx.MockTransport) -> Client:
    return Client(
        base_url="https://dicehub.test",
        session_cookie="test-session-cookie",
        transport=handler,
    )


def _counting_transport() -> tuple[httpx.MockTransport, list[httpx.Request]]:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(500, request=request)

    return httpx.MockTransport(handler), requests


@pytest.mark.parametrize(
    "kwargs",
    [
        {"name": "", "slug": "valid-slug"},
        {"name": "Group", "slug": "ab"},
        {"name": "Group", "slug": "bad slug"},
        {"name": "Group", "slug": "valid-slug", "description": "bad\0description"},
        {"name": "Group", "slug": "valid-slug", "visibility": "PRIVATE"},
    ],
)
def test_top_level_create_validates_inputs_before_transport(kwargs: dict[str, object]) -> None:
    transport, requests = _counting_transport()

    with _session_client(transport) as client, pytest.raises(ConfigurationError):
        client.groups.create(**kwargs)  # type: ignore[arg-type]

    assert requests == []


def test_subgroup_create_validates_parent_id_before_transport() -> None:
    transport, requests = _counting_transport()

    with _api_key_client(transport) as client, pytest.raises(ConfigurationError):
        client.groups.create(name="Group", slug="valid-slug", parent_id="01")

    assert requests == []


def test_top_level_create_and_move_reject_api_key_identity_before_transport() -> None:
    transport, requests = _counting_transport()

    with _api_key_client(transport) as client:
        with pytest.raises(ConfigurationError, match="Top-level group creation"):
            client.groups.create(name="Group", slug="valid-slug")
        with pytest.raises(ConfigurationError, match="Group move"):
            client.groups.move(group_id="73", to_group_id="42")

    assert requests == []


@pytest.mark.parametrize(
    "source",
    [
        io.BytesIO(b""),
        io.BytesIO(b"not-png"),
        io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"x" * MAX_GROUP_AVATAR_BYTES),
        cast(BinaryIO, object()),
    ],
)
def test_avatar_rejects_invalid_input_before_transport(source: BinaryIO) -> None:
    transport, requests = _counting_transport()

    with _api_key_client(transport) as client, pytest.raises(ConfigurationError):
        client.groups.set_avatar(group_id="73", source=source)

    assert requests == []


def test_avatar_rejects_text_and_read_errors_without_leaking_details() -> None:
    class TextSource:
        def read(self, size: int) -> str:
            return "sentinel"

    class BrokenSource:
        def read(self, size: int) -> bytes:
            raise OSError("sentinel filesystem details")

    transport, requests = _counting_transport()
    for source in (TextSource(), BrokenSource()):
        with _api_key_client(transport) as client, pytest.raises(ConfigurationError) as captured:
            client.groups.set_avatar(group_id="73", source=cast(BinaryIO, source))
        assert "sentinel" not in str(captured.value)
        assert captured.value.__context__ is None

    assert requests == []


def test_avatar_rejects_a_stream_chunk_larger_than_requested() -> None:
    class OversizedChunkSource:
        def read(self, size: int) -> bytes:
            return b"\x89PNG\r\n\x1a\n" + b"x" * MAX_GROUP_AVATAR_BYTES

    transport, requests = _counting_transport()

    with (
        _api_key_client(transport) as client,
        pytest.raises(
            ConfigurationError,
            match="must not exceed 10 MiB",
        ),
    ):
        client.groups.set_avatar(
            group_id="73",
            source=cast(BinaryIO, OversizedChunkSource()),
        )

    assert requests == []


@pytest.mark.parametrize(
    "kwargs",
    [
        {"group_id": "01"},
        {"group_id": "73", "include_inherited": 1},
        {"group_id": "73", "deduplicate": "false"},
        {"group_id": "73", "search_filter": "bad\nfilter"},
        {"group_id": "73", "offset": True},
        {"group_id": "73", "limit": 51},
        {"group_id": "73", "cursor": "bad cursor"},
    ],
)
def test_membership_list_validates_inputs_before_transport(kwargs: dict[str, object]) -> None:
    transport, requests = _counting_transport()

    with _api_key_client(transport) as client, pytest.raises(ConfigurationError):
        client.groups.list_user_members(**kwargs)  # type: ignore[arg-type]

    assert requests == []


def test_member_update_requires_a_change_before_transport() -> None:
    transport, requests = _counting_transport()

    with _api_key_client(transport) as client, pytest.raises(ConfigurationError):
        client.groups.update_member(group_id="73", member_id="7")

    assert requests == []


@pytest.mark.parametrize(
    "kwargs",
    [
        {"group_id": "0", "member_id": "7", "role_id": "3"},
        {"group_id": "73", "member_id": "member", "role_id": "3"},
        {"group_id": "73", "member_id": "7", "role_id": "01"},
        {
            "group_id": "73",
            "member_id": "7",
            "role_id": "3",
            "visibility": "PUBLIC",
        },
    ],
)
def test_member_add_validates_inputs_before_transport(kwargs: dict[str, object]) -> None:
    transport, requests = _counting_transport()

    with _api_key_client(transport) as client, pytest.raises(ConfigurationError):
        client.groups.add_member(**kwargs)  # type: ignore[arg-type]

    assert requests == []


def test_member_methods_accept_all_visibility_enums() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            json={
                "data": {
                    "groups": {"addMemberToGroup": {"status": {"succeeded": True, "error": None}}}
                }
            },
            request=request,
        )

    with _api_key_client(httpx.MockTransport(handler)) as client:
        for visibility in MembershipVisibility:
            client.groups.add_member(
                group_id="73",
                member_id="7",
                role_id="3",
                visibility=visibility,
            )

    assert calls == len(MembershipVisibility)
