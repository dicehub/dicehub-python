from __future__ import annotations

import asyncio
import hashlib
import os
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path
from typing import BinaryIO, cast

from dicehub._core.async_graphql import AsyncGraphQLExecutor
from dicehub.errors import (
    ConfigurationError,
    HTTPError,
    MutationOutcomeUnknownError,
    ProtocolError,
    TransportError,
)
from dicehub.resources._validation import (
    MAX_STORAGE_BYTES,
    validated_data_path,
    validated_namespace_id,
    validated_storage_limit,
)
from dicehub.storage.models import DownloadReceipt, UploadReceipt
from dicehub.storage.service import (
    _STORAGE_MEDIA_TYPES,
    _HashingWriter,
    _local_path,
    _storage_endpoint,
)

_AMBIGUOUS_MUTATION_ERRORS = (TransportError, HTTPError, ProtocolError)
_CHUNK_BYTES = 64 * 1024


class AsyncStorageService:
    def __init__(self, graphql: AsyncGraphQLExecutor) -> None:
        self._graphql = graphql

    async def upload(
        self,
        *,
        namespace_id: str,
        path: str,
        source: BinaryIO,
        max_bytes: int = MAX_STORAGE_BYTES,
    ) -> UploadReceipt:
        namespace_id = validated_namespace_id(namespace_id)
        path = validated_data_path(path)
        limit = validated_storage_limit(max_bytes)
        chunks = _AsyncUploadChunks(source, limit)
        mapped_error: MutationOutcomeUnknownError | None = None
        input_error: ConfigurationError | None = None
        try:
            await self._graphql.upload_binary(
                path=_storage_endpoint(namespace_id, path),
                chunks=chunks,
                method="POST",
            )
        except _AMBIGUOUS_MUTATION_ERRORS as error:
            mapped_error = MutationOutcomeUnknownError(
                "The storage upload may have completed, but dicehub did not confirm its outcome.",
                request_id=error.request_id,
            )
        except ConfigurationError as error:
            if chunks.count:
                mapped_error = MutationOutcomeUnknownError(
                    "The storage upload may have completed, but dicehub did not confirm its "
                    "outcome."
                )
            else:
                input_error = ConfigurationError(str(error))
        if mapped_error is not None:
            raise mapped_error
        if input_error is not None:
            raise input_error
        return UploadReceipt(
            namespace_id=namespace_id,
            path=path,
            bytes_sent=chunks.count,
            sha256=chunks.hexdigest,
        )

    async def upload_file(
        self,
        *,
        namespace_id: str,
        path: str,
        source_path: str | os.PathLike[str],
        max_bytes: int = MAX_STORAGE_BYTES,
    ) -> UploadReceipt:
        namespace_id = validated_namespace_id(namespace_id)
        path = validated_data_path(path)
        limit = validated_storage_limit(max_bytes)
        source = _local_path(source_path, "Storage upload source path is invalid.")
        stream: BinaryIO | None = None
        try:
            stat = await asyncio.to_thread(source.stat)
            if stat.st_size > limit:
                raise ConfigurationError("Storage upload exceeds the configured limit.")
            stream = await asyncio.to_thread(source.open, "rb")
            receipt = await self.upload(
                namespace_id=namespace_id,
                path=path,
                source=stream,
                max_bytes=limit,
            )
            await asyncio.to_thread(stream.close)
            stream = None
            return receipt
        except OSError:
            raise ConfigurationError("Could not read the storage upload source.") from None
        finally:
            if stream is not None:
                try:
                    await asyncio.to_thread(stream.close)
                except OSError:
                    pass

    async def download(
        self,
        *,
        namespace_id: str,
        path: str,
        destination: BinaryIO,
        max_bytes: int = MAX_STORAGE_BYTES,
    ) -> DownloadReceipt:
        namespace_id = validated_namespace_id(namespace_id)
        path = validated_data_path(path)
        limit = validated_storage_limit(max_bytes)
        writer = _HashingWriter(destination)
        count = await self._graphql.download_binary(
            path=_storage_endpoint(namespace_id, path),
            destination=cast(BinaryIO, writer),
            max_bytes=limit,
            content_label="storage object",
            expected_media_type=_STORAGE_MEDIA_TYPES,
        )
        if count != writer.count:
            raise ProtocolError("dicehub returned an inconsistent storage byte count.")
        return DownloadReceipt(
            namespace_id=namespace_id,
            path=path,
            bytes_received=count,
            sha256=writer.hexdigest,
        )

    async def download_file(
        self,
        *,
        namespace_id: str,
        path: str,
        destination_path: str | os.PathLike[str],
        overwrite: bool = False,
        max_bytes: int = MAX_STORAGE_BYTES,
    ) -> DownloadReceipt:
        if not isinstance(overwrite, bool):
            raise ConfigurationError("Storage overwrite flag is invalid.")
        namespace_id = validated_namespace_id(namespace_id)
        path = validated_data_path(path)
        max_bytes = validated_storage_limit(max_bytes)
        destination = _local_path(destination_path, "Storage destination path is invalid.")
        parent_is_dir, destination_exists = await asyncio.gather(
            asyncio.to_thread(destination.parent.is_dir),
            asyncio.to_thread(destination.exists),
        )
        if not parent_is_dir:
            raise ConfigurationError("Storage destination directory does not exist.")
        if destination_exists and not overwrite:
            raise ConfigurationError("Storage destination already exists; use overwrite=True.")

        temporary_path: Path | None = None
        stream: BinaryIO | None = None
        try:
            descriptor, temporary_name = await asyncio.to_thread(
                tempfile.mkstemp,
                prefix=f".{destination.name}.",
                dir=destination.parent,
            )
            temporary_path = Path(temporary_name)
            stream = os.fdopen(descriptor, "wb")
            receipt = await self.download(
                namespace_id=namespace_id,
                path=path,
                destination=stream,
                max_bytes=max_bytes,
            )
            await asyncio.to_thread(stream.close)
            stream = None
            if overwrite:
                await asyncio.to_thread(os.replace, temporary_path, destination)
            else:
                await asyncio.to_thread(os.link, temporary_path, destination)
                await asyncio.to_thread(temporary_path.unlink)
            temporary_path = None
            return receipt
        except OSError:
            raise ConfigurationError("Could not write the storage destination.") from None
        finally:
            if stream is not None:
                try:
                    await asyncio.to_thread(stream.close)
                except OSError:
                    pass
            if temporary_path is not None:
                try:
                    await asyncio.to_thread(temporary_path.unlink, missing_ok=True)
                except OSError:
                    pass


class _AsyncUploadChunks:
    def __init__(self, source: BinaryIO, max_bytes: int) -> None:
        if not callable(getattr(source, "read", None)):
            raise ConfigurationError("Storage upload source must be readable.")
        self._source = source
        self._max_bytes = max_bytes
        self._digest = hashlib.sha256()
        self.count = 0

    @property
    def hexdigest(self) -> str:
        return self._digest.hexdigest()

    def __aiter__(self) -> AsyncIterator[bytes]:
        return self._iterate()

    async def _iterate(self) -> AsyncIterator[bytes]:
        while True:
            try:
                chunk = await asyncio.to_thread(self._source.read, _CHUNK_BYTES)
            except Exception:
                raise ConfigurationError("Could not read the storage upload source.") from None
            if not isinstance(chunk, bytes):
                raise ConfigurationError("Storage upload source must return bytes.")
            if not chunk:
                return
            next_count = self.count + len(chunk)
            if next_count > self._max_bytes:
                raise ConfigurationError("Storage upload exceeds the configured limit.")
            self.count = next_count
            self._digest.update(chunk)
            yield chunk
