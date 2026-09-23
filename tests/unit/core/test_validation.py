from __future__ import annotations

from enum import Enum
from typing import Any

import pytest

from dicehub._core import validation
from dicehub.errors import ConfigurationError


class _Mode(Enum):
    FIRST = "FIRST"


def test_enum_requires_its_declared_type() -> None:
    assert validation.validated_enum(_Mode.FIRST, _Mode, "mode") is _Mode.FIRST
    with pytest.raises(ConfigurationError, match=r"^Mode is invalid\.$"):
        validation.validated_enum("FIRST", _Mode, "mode")  # type: ignore[type-var]


@pytest.mark.parametrize("value", ["1", "42", "9" * 256])
def test_id_accepts_canonical_decimal(value: str) -> None:
    assert validation.validated_id(value, "project ID") == value


@pytest.mark.parametrize(
    "value",
    ["", "0", "01", "+1", "-1", "1.0", " 1", "1 ", "\u0661", "1" * 257, 1, True, None],
)
def test_id_rejects_other_values(value: Any) -> None:
    with pytest.raises(ConfigurationError, match=r"^Project id is invalid\.$"):
        validation.validated_id(value, "project ID")


def test_optional_id_uses_the_same_rule() -> None:
    assert validation.validated_optional_id(None, "group ID") is None
    with pytest.raises(ConfigurationError, match=r"^Group id is invalid\.$"):
        validation.validated_optional_id("01", "group ID")


@pytest.mark.parametrize("value", ["/", "/rös/project", "/a//b", "/" + "x" * 16_383])
def test_route_accepts_server_shapes(value: str) -> None:
    assert validation.validated_route(value, "Project") == value


@pytest.mark.parametrize(
    "value", ["", "relative", "/bad\nroute", "/bad\0route", "/" + "x" * 16_384, 1]
)
def test_route_rejects_unsafe_or_oversized_values(value: Any) -> None:
    with pytest.raises(ConfigurationError, match=r"^Project route is invalid\.$"):
        validation.validated_route(value, "Project")


@pytest.mark.parametrize("value", ["abc", " é ", "x" * 128])
def test_name_accepts_printable_values_within_bounds(value: str) -> None:
    assert validation.validated_name(value, "App", min_length=3) == value


@pytest.mark.parametrize("value", ["", "ab", "   ", "bad\nname", "x" * 129, 1])
def test_name_rejects_values_outside_domain_bounds(value: Any) -> None:
    with pytest.raises(
        ConfigurationError, match=r"^App name must be 3 to 128 printable characters\.$"
    ):
        validation.validated_name(value, "App", min_length=3)


def test_group_name_allows_one_character() -> None:
    assert validation.validated_name("x", "Group", min_length=1) == "x"


@pytest.mark.parametrize("value", ["", " role", "role ", "bad\nrole", "x" * 129, 1])
def test_role_name_rejects_invalid_values(value: Any) -> None:
    with pytest.raises(
        ConfigurationError, match=r"^Group role name must be 1 to 128 printable characters\.$"
    ):
        validation.validated_role_name(value, "Group")


def test_role_name_accepts_exact_boundary() -> None:
    assert validation.validated_role_name("x" * 128, "Group") == "x" * 128


@pytest.mark.parametrize("value", [None, "", "line one\nline two"])
def test_description_accepts_none_empty_and_multiline(value: str | None) -> None:
    assert validation.validated_description(value, "Project") == value


@pytest.mark.parametrize("value", ["bad\0description", 1])
def test_description_rejects_nul_and_non_string(value: Any) -> None:
    with pytest.raises(ConfigurationError, match=r"^Project description is invalid\.$"):
        validation.validated_description(value, "Project")


@pytest.mark.parametrize("value", [None, "", "é", "x" * 256])
def test_search_filter_accepts_printable_values(value: str | None) -> None:
    assert validation.validated_search_filter(value, "App") == value


@pytest.mark.parametrize("value", ["bad\nfilter", "x" * 257, 1])
def test_search_filter_rejects_unsafe_values(value: Any) -> None:
    with pytest.raises(ConfigurationError, match=r"^App search filter is invalid\.$"):
        validation.validated_search_filter(value, "App")


@pytest.mark.parametrize("value", [1, 50])
def test_page_size_accepts_bounds(value: int) -> None:
    assert validation.validated_page_size(value, "App") == value


@pytest.mark.parametrize("value", [0, 51, -1, True, 1.0, None])
def test_page_size_rejects_other_values(value: Any) -> None:
    with pytest.raises(ConfigurationError, match=r"^App page size must be between 1 and 50\.$"):
        validation.validated_page_size(value, "App")


@pytest.mark.parametrize("value", [0, 2**31, 2**53 - 1])
def test_float_offset_accepts_safe_integers(value: int) -> None:
    assert validation.validated_offset(value, "App") == value


@pytest.mark.parametrize("value", [-1, 2**53, True, 1.0, None])
def test_float_offset_rejects_other_values(value: Any) -> None:
    with pytest.raises(
        ConfigurationError, match=r"^App offset must be a non-negative safe integer\.$"
    ):
        validation.validated_offset(value, "App")


def test_graphql_int_offset_has_its_own_boundary() -> None:
    assert validation.validated_offset(2**31 - 1, "Run", graphql_int=True) == 2**31 - 1
    with pytest.raises(
        ConfigurationError, match=r"^Run offset must be a non-negative GraphQL integer\.$"
    ):
        validation.validated_offset(2**31, "Run", graphql_int=True)


@pytest.mark.parametrize("value", [None, "", "next", "x" * 16_384])
def test_cursor_accepts_visible_ascii_or_empty(value: str | None) -> None:
    assert validation.validated_cursor(value, "App") == value


@pytest.mark.parametrize("value", ["has space", "bad\ncursor", "é", "x" * 16_385, 1])
def test_cursor_rejects_non_visible_ascii(value: Any) -> None:
    with pytest.raises(ConfigurationError, match=r"^App cursor is invalid\.$"):
        validation.validated_cursor(value, "App")


@pytest.mark.parametrize("value", [None, "has space", "é", "x" * 16_384])
def test_resource_cursor_accepts_printable_characters(value: str | None) -> None:
    assert validation.validated_cursor(value, "Resource", printable=True) == value


@pytest.mark.parametrize("value", ["", "bad\ncursor", "x" * 16_385, 1])
def test_resource_cursor_rejects_empty_or_unprintable_values(value: Any) -> None:
    with pytest.raises(ConfigurationError, match=r"^Resource cursor is invalid\.$"):
        validation.validated_cursor(value, "Resource", printable=True)
