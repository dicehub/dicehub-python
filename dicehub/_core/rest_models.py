"""Strict REST representations and safe conversion helpers."""

from __future__ import annotations

import json
from typing import TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from dicehub._core.rest_v2 import RestParams
from dicehub.errors import (
    ConfigurationError,
    ProtocolError,
)

ModelT = TypeVar("ModelT", bound=BaseModel)


class WireModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class WirePage(WireModel):
    limit: int = Field(ge=1, le=50)
    offset: int = Field(ge=0, le=2**31 - 1)
    count: int = Field(ge=0)
    cursor: str = Field(max_length=16_384)
    has_more: bool


def parse_model(model: type[ModelT], value: object) -> ModelT:
    result: ModelT | None = None
    try:
        result = model.model_validate_json(json.dumps(value, allow_nan=False))
    except (ValidationError, ValueError, TypeError, RecursionError):
        pass
    if result is None:
        raise ProtocolError("dicehub returned an incompatible REST v2 response.")
    return result


def convert(model: type[ModelT], wire: BaseModel, fields: tuple[str, ...]) -> ModelT:
    data = wire.model_dump(mode="json")
    return parse_model(model, {name: data[name] for name in fields})


def identifier(value: object, *, uuid: bool = False) -> str:
    valid = False
    if isinstance(value, str):
        if uuid:
            try:
                return str(UUID(value))
            except ValueError:
                pass
        else:
            valid = (
                value.isascii()
                and value.isdecimal()
                and len(value) <= 19
                and 1 <= int(value) <= 2**63 - 1
            )
    if not valid:
        raise ConfigurationError("REST v2 identifier is invalid.")
    return str(value)


def query_params(values: dict[str, object]) -> RestParams:
    result: RestParams = {}
    for key, value in values.items():
        if value is None:
            continue
        if key.endswith("_id") and key != "machine_type_id":
            value = identifier(value, uuid=key in {"resource_id", "run_id", "study_id"})
        if key in {"limit", "offset"}:
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or value != int(value)
                or not 0 <= value <= 2**31 - 1
            ):
                raise ConfigurationError("REST v2 pagination is invalid.")
            value = int(value)
        if isinstance(value, bool):
            result[key] = "true" if value else "false"
        elif isinstance(value, (str, int)):
            result[key] = value
        elif isinstance(value, (list, tuple)) and all(isinstance(item, str) for item in value):
            result[key] = [str(item) for item in value]
        else:
            raise ConfigurationError("REST v2 query parameters are invalid.")
    return result


def request_body(values: dict[str, object]) -> dict[str, object]:
    result = {key: value for key, value in values.items() if value is not None}
    for key, value in result.items():
        if key.endswith("_id") and key != "machine_type_id":
            result[key] = identifier(value, uuid=key in {"resource_id", "run_id", "study_id"})
    return result


def validate_page(
    *,
    size: int,
    limit: int,
    offset: int,
    count: int,
    has_more: bool,
    requested_limit: object,
    requested_offset: object,
) -> None:
    if (
        limit != requested_limit
        or offset != requested_offset
        or size > limit
        or count < 0
        or (size > 0 and count < offset + size)
        or has_more != (count > offset + size)
    ):
        raise ProtocolError("dicehub returned inconsistent REST pagination.")
