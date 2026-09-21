from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from pydantic import ValidationError

from dicehub.errors import ConfigurationError
from dicehub.runs._validation import (
    MAX_RESULT_ARCHIVE_BYTES,
    MAX_RUN_WAIT_SECONDS,
    validated_bool,
    validated_cursor,
    validated_enum_values,
    validated_id,
    validated_machine_type_id,
    validated_offset,
    validated_optional_positive_count,
    validated_page_size,
    validated_positive_count,
    validated_result_archive_limit,
    validated_uuid,
    validated_wait_settings,
)
from dicehub.runs.models import Run, RunState, RunType

RUN_ID = "12345678-1234-5678-9234-567812345678"


def _run(*, created_at: datetime, updated_at: datetime) -> Run:
    return Run(
        run_id=RUN_ID,
        namespace_id="101",
        name="test",
        state=RunState.RUNNING,
        run_type=RunType.REGULAR,
        created_at=created_at,
        updated_at=updated_at,
    )


def test_public_run_timestamps_are_normalized_to_utc() -> None:
    source_timezone = timezone(timedelta(hours=2))
    run = _run(
        created_at=datetime(2026, 8, 11, 12, tzinfo=source_timezone),
        updated_at=datetime(2026, 8, 11, 13, tzinfo=source_timezone),
    )

    assert run.created_at == datetime(2026, 8, 11, 10, tzinfo=timezone.utc)
    assert run.updated_at == datetime(2026, 8, 11, 11, tzinfo=timezone.utc)
    assert run.created_at.tzinfo is timezone.utc
    assert run.updated_at.tzinfo is timezone.utc


def test_public_run_rejects_naive_timestamps() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        _run(
            created_at=datetime(2026, 8, 11, 12),
            updated_at=datetime(2026, 8, 11, 13, tzinfo=timezone.utc),
        )


def test_uuid_is_canonicalized() -> None:
    value = "abcdefab-1234-5678-9234-567812345678"
    assert validated_uuid(value.upper(), "run ID") == value


@pytest.mark.parametrize(
    "value",
    [
        "",
        "not-a-uuid",
        "12345678123456789234567812345678",
        "{12345678-1234-5678-9234-567812345678}",
        42,
    ],
)
def test_uuid_rejects_noncanonical_values(value: Any) -> None:
    with pytest.raises(ConfigurationError, match="Run id is invalid"):
        validated_uuid(value, "run ID")


def test_wait_settings_normalize_valid_numbers() -> None:
    assert validated_wait_settings(10, 0.1) == (10.0, 0.1)


@pytest.mark.parametrize(
    ("timeout_seconds", "poll_seconds"),
    [
        (0, 1),
        (-1, 1),
        (float("nan"), 1),
        (float("inf"), 1),
        (True, 1),
        (10, 0),
        (10, 0.01),
        (10, 11),
        (MAX_RUN_WAIT_SECONDS + 1, 1),
    ],
)
def test_wait_settings_reject_unbounded_or_unsafe_values(
    timeout_seconds: Any,
    poll_seconds: Any,
) -> None:
    with pytest.raises(ConfigurationError):
        validated_wait_settings(timeout_seconds, poll_seconds)


@pytest.mark.parametrize("value", [1, MAX_RESULT_ARCHIVE_BYTES])
def test_result_archive_limit_accepts_bounded_integers(value: int) -> None:
    assert validated_result_archive_limit(value) == value


@pytest.mark.parametrize("value", [0, -1, True, 1.0, MAX_RESULT_ARCHIVE_BYTES + 1])
def test_result_archive_limit_rejects_invalid_values(value: Any) -> None:
    with pytest.raises(ConfigurationError, match="between 1 byte and 2 GiB"):
        validated_result_archive_limit(value)


@pytest.mark.parametrize("value", ["", "0", "01", "-1", "abc", 1, True])
def test_namespace_id_requires_positive_ascii_decimal(value: Any) -> None:
    with pytest.raises(ConfigurationError, match="Namespace id is invalid"):
        validated_id(value, "namespace ID")


@pytest.mark.parametrize("value", [0, 1, "true", None])
def test_include_descendants_requires_a_real_boolean(value: Any) -> None:
    with pytest.raises(ConfigurationError, match="Include-descendants flag is invalid"):
        validated_bool(value, "include-descendants flag")


def test_enum_filters_preserve_explicit_order() -> None:
    assert validated_enum_values(
        [RunState.RUNNING, RunState.PENDING],
        RunState,
        "run states",
    ) == ["RUNNING", "PENDING"]


@pytest.mark.parametrize(
    "value",
    [[], "RUNNING", ["RUNNING"], [RunType.REGULAR], None],
)
def test_invalid_state_filters_fail_closed(value: Any) -> None:
    if value is None:
        assert validated_enum_values(value, RunState, "run states") is None
        return
    with pytest.raises(ConfigurationError, match="Run states is invalid"):
        validated_enum_values(value, RunState, "run states")


def test_duplicate_filters_are_rejected() -> None:
    with pytest.raises(ConfigurationError, match="must not contain duplicates"):
        validated_enum_values(
            [RunState.RUNNING, RunState.RUNNING],
            RunState,
            "run states",
        )


@pytest.mark.parametrize("value", [0, 51, -1, True, 1.0])
def test_page_size_is_bounded(value: Any) -> None:
    with pytest.raises(ConfigurationError, match="Run page size"):
        validated_page_size(value)


@pytest.mark.parametrize("value", [-1, True, 1.0, 2**31])
def test_offset_is_a_nonnegative_graphql_integer(value: Any) -> None:
    with pytest.raises(ConfigurationError, match="Run offset"):
        validated_offset(value)


@pytest.mark.parametrize("value", ["has space", "line\nbreak", "x" * 16_385, 1])
def test_cursor_is_bounded_visible_ascii(value: Any) -> None:
    with pytest.raises(ConfigurationError, match="Run cursor"):
        validated_cursor(value)


@pytest.mark.parametrize("value", ["local", "dh1_4x", "A_1"])
def test_machine_type_id_accepts_server_enum_identifiers(value: str) -> None:
    assert validated_machine_type_id(value) == value


@pytest.mark.parametrize(
    "value",
    ["", "dh-4x", "two words", "1local", "\N{LATIN SMALL LETTER A WITH DIAERESIS}", 1],
)
def test_machine_type_id_rejects_values_outside_the_server_identifier_contract(
    value: Any,
) -> None:
    with pytest.raises(ConfigurationError, match="Machine type ID is invalid"):
        validated_machine_type_id(value)


@pytest.mark.parametrize("value", [1, 2**31 - 1])
def test_positive_run_counts_accept_graphql_integers(value: int) -> None:
    assert validated_positive_count(value, "node count") == value
    assert validated_optional_positive_count(value, "CPU count") == value


def test_optional_cpu_count_accepts_none() -> None:
    assert validated_optional_positive_count(None, "CPU count") is None


@pytest.mark.parametrize("value", [None, 0, -1, True, 1.0, 2**31])
def test_required_run_count_rejects_invalid_values(value: Any) -> None:
    with pytest.raises(ConfigurationError, match="positive GraphQL integer"):
        validated_positive_count(value, "node count")


def test_optional_run_count_uses_required_count_validation() -> None:
    with pytest.raises(ConfigurationError, match="positive GraphQL integer"):
        validated_optional_positive_count(True, "CPU count")
