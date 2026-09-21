from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Sequence
from time import monotonic
from typing import BinaryIO, TypeVar

from pydantic import BaseModel, SecretStr

from dicehub._core.async_graphql import AsyncGraphQLExecutor
from dicehub._core.status import raise_for_status
from dicehub.errors import (
    ConfigurationError,
    GraphQLError,
    HTTPError,
    MutationOutcomeUnknownError,
    ProtocolError,
    RunFailedError,
    RunTimeoutError,
    TransportError,
)
from dicehub.projects.models import SortOrder
from dicehub.runs._graphql import (
    GET_RUN_QUERY,
    GET_RUN_RESULT_FOLDER_QUERY,
    GET_RUN_RESULT_S3_CREDENTIALS_MUTATION,
    GET_RUN_STATUS_QUERY,
    LIST_RUNS_QUERY,
    START_RUN_MUTATION,
    STOP_RUN_MUTATION,
    GetRunData,
    GetRunResultFolderData,
    GetRunResultS3CredentialsData,
    GetRunStatusData,
    ListRunsData,
    StartRunData,
    StopRunData,
)
from dicehub.runs._machine_types import (
    LIST_MACHINE_PRICES_QUERY,
    LIST_MACHINE_TYPES_QUERY,
    ListMachinePricesData,
    ListMachineTypesData,
    machine_product_ids,
    machine_types_from_payloads,
)
from dicehub.runs._validation import (
    MAX_RESULT_ARCHIVE_BYTES,
    validated_bool,
    validated_cursor,
    validated_enum,
    validated_enum_values,
    validated_id,
    validated_machine_type_id,
    validated_offset,
    validated_optional_id,
    validated_optional_positive_count,
    validated_page_size,
    validated_positive_count,
    validated_result_archive_limit,
    validated_uuid,
    validated_wait_settings,
)
from dicehub.runs.models import (
    MachineType,
    RunDetail,
    RunOrderField,
    RunPage,
    RunResultS3Credentials,
    RunState,
    RunStatus,
    RunType,
)
from dicehub.runs.service import (
    _TERMINAL_FAILURE_STATES,
    _TERMINAL_STATES,
    _meaningful_status,
    _run_detail_from_payload,
    _run_from_payload,
    _run_status_from_payload,
    _run_timeout,
    _unknown_mutation_outcome,
    _validated_response,
)

WireModelT = TypeVar("WireModelT", bound=BaseModel)
_AMBIGUOUS_MUTATION_ERRORS = (TransportError, HTTPError, GraphQLError, ProtocolError)


class AsyncRunsService:
    def __init__(self, graphql: AsyncGraphQLExecutor) -> None:
        self._graphql = graphql

    async def list_machine_types(self) -> tuple[MachineType, ...]:
        result = await self._graphql.execute(
            operation_name="ListMachineTypes",
            query=LIST_MACHINE_TYPES_QUERY,
        )
        response = _validated_response(ListMachineTypesData, result.data)
        payload = response.runs.list_machine_types
        raise_for_status(payload.status)
        if payload.machine_types is None:
            raise ProtocolError("dicehub returned a successful response without machine types.")

        product_ids = machine_product_ids(payload.machine_types)
        if not product_ids:
            return machine_types_from_payloads(payload.machine_types, ())
        price_result = await self._graphql.execute(
            operation_name="ListMachinePrices",
            query=LIST_MACHINE_PRICES_QUERY,
            variables={"productIds": product_ids},
        )
        price_response = _validated_response(ListMachinePricesData, price_result.data)
        price_payload = price_response.products.list_products
        raise_for_status(price_payload.status)
        if price_payload.products is None:
            raise ProtocolError("dicehub returned a successful response without machine prices.")
        return machine_types_from_payloads(payload.machine_types, price_payload.products)

    async def list(
        self,
        *,
        namespace_id: str,
        include_descendants: bool = False,
        app_id: str | None = None,
        run_types: Sequence[RunType] | None = None,
        states: Sequence[RunState] | None = None,
        order_by: RunOrderField = RunOrderField.CREATED_AT,
        order: SortOrder = SortOrder.DESC,
        offset: int = 0,
        limit: int = 20,
        cursor: str | None = None,
    ) -> RunPage:
        valid_order_by = validated_enum(order_by, RunOrderField, "run order field")
        valid_order = validated_enum(order, SortOrder, "run sort order")
        result = await self._graphql.execute(
            operation_name="ListRuns",
            query=LIST_RUNS_QUERY,
            variables={
                "namespaceId": validated_id(namespace_id, "namespace ID"),
                "includeDescendants": validated_bool(
                    include_descendants,
                    "include-descendants flag",
                ),
                "appId": validated_optional_id(app_id, "app ID"),
                "runTypes": validated_enum_values(run_types, RunType, "run types"),
                "states": validated_enum_values(states, RunState, "run states"),
                "orderBy": valid_order_by.value,
                "order": valid_order.value,
                "offset": validated_offset(offset),
                "limit": validated_page_size(limit),
                "cursor": validated_cursor(cursor),
            },
        )
        response = _validated_response(ListRunsData, result.data)
        payload = response.runs.list_runs
        raise_for_status(payload.status)
        if payload.runs is None or payload.info is None:
            raise ProtocolError("dicehub returned a successful response without a run page.")
        return RunPage(
            runs=tuple(_run_from_payload(run) for run in payload.runs),
            offset=int(payload.info.offset),
            count=int(payload.info.count),
            cursor=payload.info.cursor,
        )

    async def get(self, *, run_id: str) -> RunDetail:
        result = await self._graphql.execute(
            operation_name="GetRun",
            query=GET_RUN_QUERY,
            variables={"runId": validated_uuid(run_id, "run ID")},
        )
        response = _validated_response(GetRunData, result.data)
        payload = response.runs.get_run
        raise_for_status(payload.status)
        if payload.run is None:
            raise ProtocolError("dicehub returned a successful response without a run.")
        return _run_detail_from_payload(payload.run)

    async def status(self, *, run_id: str) -> RunStatus:
        return await self._status(validated_uuid(run_id, "run ID"))

    async def wait(
        self,
        *,
        run_id: str,
        timeout_seconds: float,
        poll_seconds: float = 2.0,
    ) -> RunStatus:
        """Wait for one run to reach a terminal state."""

        valid_run_id = validated_uuid(run_id, "run ID")
        valid_timeout, valid_poll = validated_wait_settings(timeout_seconds, poll_seconds)
        async for status in self._watch(
            run_id=valid_run_id,
            timeout_seconds=valid_timeout,
            poll_seconds=valid_poll,
        ):
            if status.state in _TERMINAL_FAILURE_STATES:
                raise RunFailedError(status)
            if status.state in _TERMINAL_STATES:
                return status
        raise ProtocolError("Run status watching ended without a terminal state.")

    def watch(
        self,
        *,
        run_id: str,
        timeout_seconds: float,
        poll_seconds: float = 2.0,
    ) -> AsyncGenerator[RunStatus, None]:
        """Yield meaningful changes until one run reaches a terminal state."""

        valid_run_id = validated_uuid(run_id, "run ID")
        valid_timeout, valid_poll = validated_wait_settings(timeout_seconds, poll_seconds)
        return self._watch(
            run_id=valid_run_id,
            timeout_seconds=valid_timeout,
            poll_seconds=valid_poll,
        )

    async def _status(self, run_id: str, *, timeout_cap: float | None = None) -> RunStatus:
        if timeout_cap is None:
            result = await self._graphql.execute(
                operation_name="GetRunStatus",
                query=GET_RUN_STATUS_QUERY,
                variables={"runId": run_id},
            )
        else:
            result = await self._graphql.execute(
                operation_name="GetRunStatus",
                query=GET_RUN_STATUS_QUERY,
                variables={"runId": run_id},
                timeout_cap=timeout_cap,
            )
        response = _validated_response(GetRunStatusData, result.data)
        payload = response.runs.get_run
        raise_for_status(payload.status)
        if payload.run is None:
            raise ProtocolError("dicehub returned a successful response without run status.")
        status = _run_status_from_payload(payload.run)
        if status.run_id != run_id:
            raise ProtocolError("dicehub returned status for a different run.")
        return status

    async def _watch(
        self,
        *,
        run_id: str,
        timeout_seconds: float,
        poll_seconds: float,
    ) -> AsyncGenerator[RunStatus, None]:
        deadline = monotonic() + timeout_seconds
        last_status: RunStatus | None = None
        last_meaningful_status: tuple[object, ...] | None = None

        while True:
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise _run_timeout(run_id, timeout_seconds, last_status)
            timeout_error: RunTimeoutError | None = None
            try:
                status = await self._status(run_id, timeout_cap=remaining)
            except TransportError:
                if monotonic() >= deadline:
                    timeout_error = _run_timeout(run_id, timeout_seconds, last_status)
                else:
                    raise
            if timeout_error is not None:
                raise timeout_error

            last_status = status
            if monotonic() >= deadline:
                raise _run_timeout(run_id, timeout_seconds, last_status)
            meaningful_status = _meaningful_status(status)
            if meaningful_status != last_meaningful_status:
                yield status
                last_meaningful_status = meaningful_status
            if status.state in _TERMINAL_STATES:
                return

            remaining = deadline - monotonic()
            if remaining <= 0:
                raise _run_timeout(run_id, timeout_seconds, last_status)
            await asyncio.sleep(min(poll_seconds, remaining))

    async def download_results(
        self,
        *,
        run_id: str,
        destination: BinaryIO,
        max_bytes: int = MAX_RESULT_ARCHIVE_BYTES,
    ) -> int:
        """Download one run's result archive into a caller-owned binary stream."""

        if not callable(getattr(destination, "write", None)):
            raise ConfigurationError("Run result archive destination must be writable.")
        valid_run_id = validated_uuid(run_id, "run ID")
        return await self._graphql.download_binary(
            path=f"api/v1/run/archive/result/{valid_run_id}",
            destination=destination,
            max_bytes=validated_result_archive_limit(max_bytes),
            content_label="run result archive",
            expected_media_type="application/zip",
        )

    async def get_result_s3_credentials(
        self,
        *,
        app_id: str,
        run_id: str,
        regenerate: bool = False,
    ) -> RunResultS3Credentials:
        """Get the S3 credentials shown by the dicehub Results panel."""

        valid_app_id = validated_id(app_id, "app ID")
        valid_run_id = validated_uuid(run_id, "run ID")
        valid_regenerate = validated_bool(regenerate, "regenerate flag")
        folder_result = await self._graphql.execute(
            operation_name="GetRunResultFolder",
            query=GET_RUN_RESULT_FOLDER_QUERY,
            variables={
                "appId": valid_app_id,
                "key": f"data/run/{valid_run_id}/result",
            },
        )
        folder_response = _validated_response(GetRunResultFolderData, folder_result.data)
        folder_payload = folder_response.resources.get_result_folder
        raise_for_status(folder_payload.status)
        if folder_payload.resource is None:
            raise ProtocolError("dicehub returned no run result folder.")

        response = await self._execute_mutation(
            response_type=GetRunResultS3CredentialsData,
            operation_name="GetRunResultS3Credentials",
            query=GET_RUN_RESULT_S3_CREDENTIALS_MUTATION,
            variables={
                "resourceId": folder_payload.resource.resource_id,
                "generateNewKey": valid_regenerate,
            },
        )
        credentials = response.resources.get_credentials
        raise_for_status(credentials.status)
        if (
            credentials.bucket is None
            or credentials.access_key_id is None
            or credentials.secret_access_key is None
        ):
            raise _unknown_mutation_outcome()
        return RunResultS3Credentials(
            bucket=credentials.bucket,
            access_key_id=SecretStr(credentials.access_key_id),
            secret_access_key=SecretStr(credentials.secret_access_key),
        )

    async def start(
        self,
        *,
        config_id: str,
        machine_type_id: str,
        node_count: int = 1,
        cpu_count: int | None = None,
        notify: bool = False,
    ) -> RunStatus:
        response = await self._execute_mutation(
            response_type=StartRunData,
            operation_name="StartRun",
            query=START_RUN_MUTATION,
            variables={
                "configId": validated_id(config_id, "config ID"),
                "machineTypeId": validated_machine_type_id(machine_type_id),
                "nodeCount": validated_positive_count(node_count, "node count"),
                "cpuCount": validated_optional_positive_count(cpu_count, "CPU count"),
                "notify": validated_bool(notify, "notify flag"),
            },
        )
        payload = response.configs.start_run
        raise_for_status(payload.status)
        if payload.run is None:
            raise _unknown_mutation_outcome()
        return _run_status_from_payload(payload.run)

    async def stop(self, *, run_id: str) -> None:
        response = await self._execute_mutation(
            response_type=StopRunData,
            operation_name="StopRun",
            query=STOP_RUN_MUTATION,
            variables={"runId": validated_uuid(run_id, "run ID")},
        )
        raise_for_status(response.runs.stop_run.status)

    async def _execute_mutation(
        self,
        *,
        response_type: type[WireModelT],
        operation_name: str,
        query: str,
        variables: dict[str, object],
    ) -> WireModelT:
        mapped_error: MutationOutcomeUnknownError | None = None
        try:
            result = await self._graphql.execute(
                operation_name=operation_name,
                query=query,
                variables=variables,
            )
            return _validated_response(response_type, result.data)
        except _AMBIGUOUS_MUTATION_ERRORS as error:
            mapped_error = _unknown_mutation_outcome(request_id=error.request_id)
        assert mapped_error is not None
        raise mapped_error
