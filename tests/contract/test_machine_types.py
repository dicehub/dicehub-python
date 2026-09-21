from __future__ import annotations

import asyncio
import json
from decimal import Decimal

import httpx
import pytest

from dicehub import AsyncClient, Client, MachinePrice, MachineType, ProtocolError

_STATUS: dict[str, object] = {"succeeded": True, "error": None}
_MACHINES: list[dict[str, object]] = [
    {
        "machineTypeId": "dh1_36x",
        "productId": "cpu_product",
        "cpuCount": 36,
        "gpuCount": 0,
        "amountOfRAM": 192,
    },
    {
        "machineTypeId": "dh_2x_1gpu",
        "productId": "gpu_product",
        "cpuCount": 2,
        "gpuCount": 1,
        "amountOfRAM": 16,
    },
    {
        "machineTypeId": "local",
        "productId": "gpu_product",
        "cpuCount": None,
        "gpuCount": None,
        "amountOfRAM": None,
    },
]
_PRODUCTS: list[dict[str, object]] = [
    {
        "productId": "gpu_product",
        "productType": "machine",
        "price": {"amount": "0.039444444444", "currency": "credits", "vatRate": "0"},
    },
    {
        "productId": "cpu_product",
        "productType": "machine",
        "price": {"amount": "0.157222222222", "currency": "credits", "vatRate": "0"},
    },
]


def _machine_response() -> dict[str, object]:
    return {
        "data": {
            "runs": {
                "listMachineTypes": {
                    "status": _STATUS,
                    "machineTypes": _MACHINES,
                }
            }
        }
    }


def _price_response(products: list[dict[str, object]]) -> dict[str, object]:
    return {
        "data": {
            "products": {
                "listProducts": {
                    "status": _STATUS,
                    "products": products,
                }
            }
        }
    }


def _handler(
    products: list[dict[str, object]],
) -> tuple[httpx.MockTransport, list[dict[str, object]]]:
    requests: list[dict[str, object]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert isinstance(payload, dict)
        requests.append(payload)
        if payload["operationName"] == "ListMachineTypes":
            return httpx.Response(200, json=_machine_response())
        assert payload["operationName"] == "ListMachinePrices"
        return httpx.Response(200, json=_price_response(products))

    return httpx.MockTransport(handle), requests


def test_list_machine_types_joins_net_prices_without_exposing_internal_data() -> None:
    transport, requests = _handler(_PRODUCTS)
    with Client(
        base_url="https://dicehub.test",
        api_key="test-api-key",
        transport=transport,
    ) as client:
        machine_types = client.runs.list_machine_types()

    assert machine_types == (
        MachineType(
            machine_type_id="dh1_36x",
            cpu_count=36,
            gpu_count=0,
            ram_gb=192,
            description="36 CPU cores, 192 GB RAM",
            price=MachinePrice(amount=Decimal("5.66"), currency="EUR"),
        ),
        MachineType(
            machine_type_id="dh_2x_1gpu",
            cpu_count=2,
            gpu_count=1,
            ram_gb=16,
            description="2 CPU cores, 1 GPU, 16 GB RAM",
            price=MachinePrice(amount=Decimal("1.42"), currency="EUR"),
        ),
        MachineType(
            machine_type_id="local",
            cpu_count=None,
            gpu_count=None,
            ram_gb=None,
            description="Local machine",
            price=None,
        ),
    )
    assert [request["operationName"] for request in requests] == [
        "ListMachineTypes",
        "ListMachinePrices",
    ]
    assert requests[0]["variables"] == {}
    assert requests[1]["variables"] == {"productIds": ["cpu_product", "gpu_product"]}
    machine_query = str(requests[0]["query"])
    assert all(
        field not in machine_query
        for field in ("provider", "usageMultiplier", "amountOfStorage", "hasEFA", "hasLustre")
    )
    assert machine_types[0].model_dump(mode="json") == {
        "machine_type_id": "dh1_36x",
        "cpu_count": 36,
        "gpu_count": 0,
        "ram_gb": 192,
        "description": "36 CPU cores, 192 GB RAM",
        "price": {"amount": "5.66", "currency": "EUR"},
    }


def test_list_machine_types_rejects_a_missing_product() -> None:
    transport, _ = _handler(_PRODUCTS[:1])
    with Client(
        base_url="https://dicehub.test",
        api_key="test-api-key",
        transport=transport,
    ) as client:
        with pytest.raises(ProtocolError, match="incompatible machine type data"):
            client.runs.list_machine_types()


def test_async_list_machine_types_uses_the_same_contract() -> None:
    transport, requests = _handler(_PRODUCTS)

    async def run() -> tuple[MachineType, ...]:
        async with AsyncClient(
            base_url="https://dicehub.test",
            api_key="test-api-key",
            transport=transport,
        ) as client:
            return await client.runs.list_machine_types()

    machine_types = asyncio.run(run())

    assert machine_types[0].price == MachinePrice(amount=Decimal("5.66"), currency="EUR")
    assert [request["operationName"] for request in requests] == [
        "ListMachineTypes",
        "ListMachinePrices",
    ]
