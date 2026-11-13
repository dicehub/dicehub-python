"""Fixed REST calls and mappings for this domain."""

from __future__ import annotations

import dicehub.runs._rest_models as wire_models
import dicehub.runs.models as models
from dicehub._core.rest_models import (
    convert,
    identifier,
    parse_model,
    query_params,
    request_body,
    validate_page,
)
from dicehub._core.rest_mutations import async_mutation_outcome
from dicehub._core.rest_request import async_request as request
from dicehub._core.rest_v2 import AsyncRestV2Executor
from dicehub.errors import ProtocolError
from dicehub.runs._machine_types import (
    MachineProductPayload,
    MachineTypePayload,
    machine_product_ids,
    machine_types_from_payloads,
)


async def list(rest: AsyncRestV2Executor, variables: dict[str, object]) -> models.RunPage:
    wire = await request(
        rest,
        wire_models.RunList,
        method="GET",
        path="api/v2/runs",
        params=query_params(
            {
                "namespace_id": variables.get("namespaceId"),
                "deep": variables.get("includeDescendants"),
                "app_id": variables.get("appId"),
                "run_type": variables.get("runTypes"),
                "state": variables.get("states"),
                "order_by": variables.get("orderBy"),
                "order": variables.get("order"),
                "offset": variables.get("offset"),
                "limit": variables.get("limit"),
                "cursor": variables.get("cursor"),
            }
        ),
    )
    validate_page(
        size=len(wire.items),
        limit=wire.limit,
        offset=wire.offset,
        count=wire.count,
        has_more=wire.has_more,
        requested_limit=variables.get("limit"),
        requested_offset=variables.get("offset"),
    )
    return models.RunPage(
        runs=tuple(
            convert(
                models.Run,
                item,
                ("run_id", "namespace_id", "name", "state", "run_type", "created_at", "updated_at"),
            )
            for item in wire.items
        ),
        offset=wire.offset,
        count=wire.count,
        cursor=wire.cursor,
    )


async def get(rest: AsyncRestV2Executor, variables: dict[str, object]) -> models.RunDetail:
    wire = await request(
        rest,
        wire_models.RunDetail,
        method="GET",
        path=f"api/v2/runs/{identifier(variables['runId'], uuid=True)}",
        params=query_params({}),
    )
    data = wire.model_dump(mode="json")
    data["run_internal_id"] = int(wire.run_internal_id)
    return parse_model(models.RunDetail, data)


async def _status(
    rest: AsyncRestV2Executor, variables: dict[str, object], *, timeout_cap: float | None = None
) -> models.RunStatus:
    wire = await request(
        rest,
        wire_models.StartedRun,
        method="GET",
        path=f"api/v2/runs/{identifier(variables['runId'], uuid=True)}/status",
        params=query_params({}),
        timeout_cap=timeout_cap,
    )
    status = convert(
        models.RunStatus,
        wire,
        ("run_id", "state", "execution_status", "error", "flags", "updated_at"),
    )
    if status.run_id != variables["runId"]:
        raise ProtocolError("dicehub returned status for a different run.")
    return status


@async_mutation_outcome
async def start(rest: AsyncRestV2Executor, variables: dict[str, object]) -> models.RunStatus:
    wire = await request(
        rest,
        wire_models.StartedRun,
        method="POST",
        path=f"api/v2/configs/{identifier(variables['configId'])}/runs",
        body=request_body(
            {
                "machine_type_id": variables.get("machineTypeId"),
                "node_count": variables.get("nodeCount"),
                "cpu_count": variables.get("cpuCount"),
                "notify": variables.get("notify"),
            }
        ),
    )
    status = convert(
        models.RunStatus,
        wire,
        ("run_id", "state", "execution_status", "error", "flags", "updated_at"),
    )
    return status


@async_mutation_outcome
async def stop(rest: AsyncRestV2Executor, variables: dict[str, object]) -> None:
    await request(
        rest,
        wire_models.Done,
        method="POST",
        path=f"api/v2/runs/{identifier(variables['runId'], uuid=True)}/stop",
        body=request_body({}),
    )
    return None


async def list_machine_types(rest: AsyncRestV2Executor) -> tuple[models.MachineType, ...]:
    wire = await request(rest, wire_models.MachineList, method="GET", path="api/v2/machine-types")
    machines = tuple(
        parse_model(
            MachineTypePayload,
            {
                "machineTypeId": item.machine_type_id,
                "productId": item.product_id,
                "cpuCount": item.cpu_count,
                "gpuCount": item.gpu_count,
                "amountOfRAM": item.amount_of_ram,
            },
        )
        for item in wire.items
    )
    product_ids = machine_product_ids(machines)
    if not product_ids:
        return machine_types_from_payloads(machines, ())
    products = await request(
        rest,
        wire_models.ProductList,
        method="GET",
        path="api/v2/products",
        params={"product_ids": product_ids},
    )
    prices = tuple(
        parse_model(
            MachineProductPayload,
            {
                "productId": item.product_id,
                "productType": item.product_type,
                "price": {
                    "amount": item.price.amount,
                    "currency": item.price.currency,
                    "vatRate": item.price.vat_rate,
                },
            },
        )
        for item in products.items
    )
    return machine_types_from_payloads(machines, prices)


async def get_result_s3_credentials(
    rest: AsyncRestV2Executor, app_id: str, run_id: str, regenerate: bool
) -> models.RunResultS3Credentials:
    folder = await request(
        rest,
        wire_models.ResourceDetail,
        method="GET",
        path="api/v2/resources/by-key",
        params={"namespace_id": identifier(app_id), "key": f"data/run/{run_id}/result"},
    )
    return await _create_result_credentials(rest, str(folder.resource_id), regenerate)


@async_mutation_outcome
async def _create_result_credentials(
    rest: AsyncRestV2Executor, resource_id: str, regenerate: bool
) -> models.RunResultS3Credentials:
    wire = await request(
        rest,
        wire_models.StorageCredentials,
        method="POST",
        path=f"api/v2/resources/{identifier(resource_id, uuid=True)}/credentials",
        body={"generate_new_key": regenerate},
    )
    return models.RunResultS3Credentials(
        bucket=wire.bucket,
        access_key_id=wire.access_key_id,
        secret_access_key=wire.secret_access_key,
    )
