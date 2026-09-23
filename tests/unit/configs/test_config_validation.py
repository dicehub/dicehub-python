from __future__ import annotations

import httpx
import pytest
from pydantic import ValidationError

from dicehub import (
    Client,
    ConfigContentArea,
    ConfigurationError,
    ConfigValueUpdate,
    SortOrder,
)
from dicehub.configs._validation import validated_config_value_updates


def _client() -> Client:
    def forbidden(request: httpx.Request) -> httpx.Response:
        raise AssertionError("Invalid config input must fail before HTTP.")

    return Client(
        base_url="https://dicehub.test",
        api_key="test-api-key",
        transport=httpx.MockTransport(forbidden),
    )


def test_list_rejects_invalid_app_id() -> None:
    with _client() as client, pytest.raises(ConfigurationError):
        client.configs.list(app_id="01")


def test_get_rejects_invalid_config_id() -> None:
    with _client() as client, pytest.raises(ConfigurationError):
        client.configs.get(config_id="01")


def test_delete_rejects_invalid_config_id() -> None:
    with _client() as client, pytest.raises(ConfigurationError):
        client.configs.delete(config_id="01")


def test_create_rejects_invalid_app_id() -> None:
    with _client() as client, pytest.raises(ConfigurationError):
        client.configs.create(app_id="01")


def test_create_rejects_invalid_source_config_id() -> None:
    with _client() as client, pytest.raises(ConfigurationError):
        client.configs.create(app_id="101", source_config_id="01")


def test_create_rejects_invalid_name() -> None:
    with _client() as client, pytest.raises(ConfigurationError):
        client.configs.create(app_id="101", name="bad\nname")


def test_create_rejects_nul_description() -> None:
    with _client() as client, pytest.raises(ConfigurationError):
        client.configs.create(app_id="101", description="bad\0description")


@pytest.mark.parametrize(
    "values",
    [
        {"search_filter": "bad\nfilter"},
        {"offset": 2**53},
        {"limit": 51},
        {"cursor": "bad cursor"},
    ],
)
def test_list_rejects_invalid_filters_and_pagination(values: dict[str, object]) -> None:
    with _client() as client, pytest.raises(ConfigurationError):
        client.configs.list(app_id="101", **values)  # type: ignore[arg-type]


def test_list_rejects_untyped_sort_order() -> None:
    with _client() as client, pytest.raises(ConfigurationError):
        client.configs.list(app_id="101", order="ASC")  # type: ignore[arg-type]


def test_list_accepts_both_sort_directions() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            json={
                "data": {
                    "configs": {
                        "listConfigs": {
                            "status": {"succeeded": True, "error": None},
                            "info": {"offset": 0.0, "count": 0.0, "cursor": ""},
                            "configs": [],
                        }
                    }
                }
            },
            request=request,
        )

    with Client(
        base_url="https://dicehub.test",
        api_key="test-api-key",
        transport=httpx.MockTransport(handler),
    ) as client:
        for order in SortOrder:
            client.configs.list(app_id="101", order=order)

    assert calls == len(SortOrder)


@pytest.mark.parametrize(
    "values",
    [
        {},
        {"name": ""},
        {"name": "bad\nname"},
        {"description": "bad\0description"},
    ],
)
def test_update_rejects_missing_or_invalid_changes(values: dict[str, object]) -> None:
    with _client() as client, pytest.raises(ConfigurationError):
        client.configs.update(config_id="301", **values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "path",
    ["/absolute", "trailing/", "../escape", "a/./b", "a//b", "back\\slash"],
)
def test_content_operations_reject_unsafe_paths(path: str) -> None:
    with _client() as client, pytest.raises(ConfigurationError):
        client.configs.get_text(config_id="301", path=path)


def test_content_list_rejects_untyped_area_and_recursive_flag() -> None:
    with _client() as client, pytest.raises(ConfigurationError):
        client.configs.list_content(
            config_id="301",
            area="TEXTS",  # type: ignore[arg-type]
        )
    with _client() as client, pytest.raises(ConfigurationError):
        client.configs.list_content(
            config_id="301",
            area=ConfigContentArea.TEXTS,
            recursive=1,  # type: ignore[arg-type]
        )


def test_text_write_rejects_content_larger_than_two_mib() -> None:
    with _client() as client, pytest.raises(ConfigurationError):
        client.configs.set_text(
            config_id="301",
            path="input.yaml",
            content="x" * (2 * 1024 * 1024 + 1),
        )


def test_text_write_rejects_unpaired_surrogate() -> None:
    with _client() as client, pytest.raises(ConfigurationError, match="valid UTF-8"):
        client.configs.set_text(
            config_id="301",
            path="input.yaml",
            content="\ud800",
        )


def test_file_operations_validate_streams_and_limits_before_http() -> None:
    with _client() as client, pytest.raises(ConfigurationError):
        client.configs.upload_file(
            config_id="301",
            path="mesh.bin",
            source=object(),  # type: ignore[arg-type]
        )
    with _client() as client, pytest.raises(ConfigurationError):
        client.configs.download_file(
            config_id="301",
            path="mesh.bin",
            destination=object(),  # type: ignore[arg-type]
        )
    with _client() as client, pytest.raises(ConfigurationError):
        client.configs.upload_file(
            config_id="301",
            path="mesh.bin",
            source=object(),  # type: ignore[arg-type]
            max_bytes=0,
        )


def test_config_value_update_is_strict_frozen_and_allows_yaml_slash_keys() -> None:
    update = ConfigValueUpdate(path=("root", "key/with/slashes"), value=1.5)

    assert update.path == ("root", "key/with/slashes")
    assert update.value == 1.5
    with pytest.raises(ValidationError):
        update.value = 2.0


@pytest.mark.parametrize(
    "path",
    [(), ("",), ("a", ""), ("a", "x" * 256), ("a\nb",)],
)
def test_config_value_update_rejects_invalid_segment_paths(path: tuple[str, ...]) -> None:
    with pytest.raises(ValidationError):
        ConfigValueUpdate(path=path, value=None)


def test_config_value_update_rejects_path_over_utf8_byte_limit() -> None:
    with pytest.raises(ValidationError):
        ConfigValueUpdate(path=("\u00e9" * 255, "\u00e9" * 255, "\u00e9" * 2), value=None)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf"), [], {}])
def test_config_value_update_rejects_non_scalar_or_non_finite_values(value: object) -> None:
    with pytest.raises(ValidationError):
        ConfigValueUpdate(path=("settings",), value=value)  # type: ignore[arg-type]


def test_config_value_update_rejects_unpaired_surrogate() -> None:
    with pytest.raises(ValidationError):
        ConfigValueUpdate(path=("settings",), value="\ud800")


@pytest.mark.parametrize("path", ["solver/control.yml", "solver/control", "solver/control.yaml/"])
def test_set_values_rejects_non_yaml_resource_before_http(path: str) -> None:
    with _client() as client, pytest.raises(ConfigurationError):
        client.configs.set_values(
            config_id="301",
            path=path,
            updates=(ConfigValueUpdate(path=("settings",), value=1),),
        )


@pytest.mark.parametrize(
    "updates",
    [
        (),
        (ConfigValueUpdate(path=("settings",), value=1),) * 2,
        (ConfigValueUpdate(path=("settings",), value=1), {"path": ("other",)}),
        tuple(ConfigValueUpdate(path=(str(index),), value=index) for index in range(101)),
    ],
)
def test_set_values_rejects_invalid_update_batches_before_http(updates: object) -> None:
    with _client() as client, pytest.raises(ConfigurationError):
        client.configs.set_values(
            config_id="301",
            path="solver/control.yaml",
            updates=updates,  # type: ignore[arg-type]
        )


def test_set_values_rejects_unbounded_string_batch_before_http() -> None:
    with _client() as client, pytest.raises(ConfigurationError):
        client.configs.set_values(
            config_id="301",
            path="solver/control.yaml",
            updates=(ConfigValueUpdate(path=("settings",), value="x" * (2 * 1024 * 1024 + 1)),),
        )


def test_set_values_rejects_serialized_batch_over_limit_before_http() -> None:
    with _client() as client, pytest.raises(ConfigurationError):
        client.configs.set_values(
            config_id="301",
            path="solver/control.yaml",
            updates=(ConfigValueUpdate(path=("settings",), value="x" * (2 * 1024 * 1024)),),
        )


def test_set_values_measures_serialized_batch_as_utf8() -> None:
    update = ConfigValueUpdate(path=("settings",), value="é" * 350_000)

    assert validated_config_value_updates((update,)) == [
        {"path": ["settings"], "value": "é" * 350_000}
    ]
