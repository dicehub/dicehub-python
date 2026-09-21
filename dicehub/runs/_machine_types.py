from __future__ import annotations

import re
from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from dicehub._core.status import ResponseStatus
from dicehub.errors import ProtocolError
from dicehub.runs.models import MachinePrice, MachineType

LIST_MACHINE_TYPES_QUERY = """
query ListMachineTypes {
  runs {
    listMachineTypes {
      status { succeeded error }
      machineTypes {
        machineTypeId
        productId
        cpuCount
        gpuCount
        amountOfRAM
      }
    }
  }
}
"""

LIST_MACHINE_PRICES_QUERY = """
query ListMachinePrices($productIds: [String]!) {
  products {
    listProducts(productIds: $productIds) {
      status { succeeded error }
      products {
        productId
        productType
        price {
          amount
          currency
          vatRate
        }
      }
    }
  }
}
"""

_LOCAL_MACHINE_TYPE_ID = "local"
_MACHINE_ID_PATTERN = r"^[A-Za-z][A-Za-z0-9_]{0,127}$"
_DECIMAL_PATTERN = re.compile(r"(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,12})?")
_HOURLY_PRICE_FACTOR = Decimal(3600) / Decimal(100)
_PRICE_QUANTUM = Decimal("0.01")
_INCOMPATIBLE_RESPONSE = "dicehub returned incompatible machine type data."


class MachineTypePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    machine_type_id: str = Field(
        alias="machineTypeId",
        pattern=_MACHINE_ID_PATTERN,
    )
    product_id: str | None = Field(
        alias="productId",
        default=None,
        pattern=_MACHINE_ID_PATTERN,
    )
    cpu_count: int | None = Field(alias="cpuCount", default=None, ge=0, le=2**31 - 1)
    gpu_count: int | None = Field(alias="gpuCount", default=None, ge=0, le=2**31 - 1)
    ram_gb: int | None = Field(alias="amountOfRAM", default=None, ge=0, le=2**31 - 1)


class ListMachineTypesPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: ResponseStatus
    machine_types: list[MachineTypePayload] | None = Field(
        alias="machineTypes",
        max_length=256,
    )


class RunsMachineTypesPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    list_machine_types: ListMachineTypesPayload = Field(alias="listMachineTypes")


class ListMachineTypesData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    runs: RunsMachineTypesPayload


class ProductPricePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    amount: str = Field(min_length=1, max_length=64)
    currency: str = Field(min_length=1, max_length=16)
    vat_rate: str = Field(alias="vatRate", min_length=1, max_length=64)


class MachineProductPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    product_id: str = Field(alias="productId", pattern=_MACHINE_ID_PATTERN)
    product_type: Literal["machine"] = Field(alias="productType")
    price: ProductPricePayload


class ListMachinePricesPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: ResponseStatus
    products: list[MachineProductPayload] | None = Field(max_length=256)


class ProductsMachinePricesPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    list_products: ListMachinePricesPayload = Field(alias="listProducts")


class ListMachinePricesData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    products: ProductsMachinePricesPayload


def machine_product_ids(machine_types: Sequence[MachineTypePayload]) -> list[str]:
    machine_ids: set[str] = set()
    product_ids: list[str] = []
    seen_product_ids: set[str] = set()
    for machine_type in machine_types:
        if machine_type.machine_type_id in machine_ids:
            raise ProtocolError(_INCOMPATIBLE_RESPONSE)
        machine_ids.add(machine_type.machine_type_id)
        if machine_type.machine_type_id == _LOCAL_MACHINE_TYPE_ID:
            continue
        if machine_type.product_id is None:
            raise ProtocolError(_INCOMPATIBLE_RESPONSE)
        if machine_type.product_id not in seen_product_ids:
            product_ids.append(machine_type.product_id)
            seen_product_ids.add(machine_type.product_id)
    return product_ids


def machine_types_from_payloads(
    machine_types: Sequence[MachineTypePayload],
    products: Sequence[MachineProductPayload],
) -> tuple[MachineType, ...]:
    requested_product_ids = set(machine_product_ids(machine_types))
    products_by_id: dict[str, MachineProductPayload] = {}
    for product in products:
        if product.product_id in products_by_id:
            raise ProtocolError(_INCOMPATIBLE_RESPONSE)
        products_by_id[product.product_id] = product
    if set(products_by_id) != requested_product_ids:
        raise ProtocolError(_INCOMPATIBLE_RESPONSE)

    result: list[MachineType] = []
    for machine_type in machine_types:
        if machine_type.machine_type_id == _LOCAL_MACHINE_TYPE_ID:
            if machine_type.cpu_count == 0 or machine_type.ram_gb == 0:
                raise ProtocolError(_INCOMPATIBLE_RESPONSE)
            result.append(
                MachineType(
                    machine_type_id=machine_type.machine_type_id,
                    cpu_count=machine_type.cpu_count,
                    gpu_count=machine_type.gpu_count,
                    ram_gb=machine_type.ram_gb,
                    description="Local machine",
                    price=None,
                )
            )
            continue

        if (
            machine_type.product_id is None
            or machine_type.cpu_count is None
            or machine_type.cpu_count <= 0
            or machine_type.gpu_count is None
            or machine_type.ram_gb is None
            or machine_type.ram_gb <= 0
        ):
            raise ProtocolError(_INCOMPATIBLE_RESPONSE)
        product = products_by_id[machine_type.product_id]
        result.append(
            MachineType(
                machine_type_id=machine_type.machine_type_id,
                cpu_count=machine_type.cpu_count,
                gpu_count=machine_type.gpu_count,
                ram_gb=machine_type.ram_gb,
                description=_description(machine_type),
                price=_machine_price(product.price),
            )
        )
    return tuple(result)


def _description(machine_type: MachineTypePayload) -> str:
    assert machine_type.cpu_count is not None
    assert machine_type.gpu_count is not None
    assert machine_type.ram_gb is not None
    parts = [f"{machine_type.cpu_count} CPU {'core' if machine_type.cpu_count == 1 else 'cores'}"]
    if machine_type.gpu_count:
        parts.append(f"{machine_type.gpu_count} {'GPU' if machine_type.gpu_count == 1 else 'GPUs'}")
    parts.append(f"{machine_type.ram_gb} GB RAM")
    return ", ".join(parts)


def _machine_price(payload: ProductPricePayload) -> MachinePrice:
    if payload.currency != "credits" or _decimal(payload.vat_rate) != 0:
        raise ProtocolError(_INCOMPATIBLE_RESPONSE)
    try:
        amount = (_decimal(payload.amount) * _HOURLY_PRICE_FACTOR).quantize(
            _PRICE_QUANTUM,
            rounding=ROUND_HALF_UP,
        )
    except InvalidOperation as error:
        raise ProtocolError(_INCOMPATIBLE_RESPONSE) from error
    return MachinePrice(amount=amount, currency="EUR")


def _decimal(value: str) -> Decimal:
    if _DECIMAL_PATTERN.fullmatch(value) is None:
        raise ProtocolError(_INCOMPATIBLE_RESPONSE)
    parsed = Decimal(value)
    if not parsed.is_finite() or parsed < 0:
        raise ProtocolError(_INCOMPATIBLE_RESPONSE)
    return parsed
