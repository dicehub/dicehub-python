from __future__ import annotations

import hashlib
import os
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import BinaryIO, cast
from urllib.parse import quote

from dicehub._core.graphql import GraphQLExecutor
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

_AMBIGUOUS_MUTATION_ERRORS = (TransportError, HTTPError, ProtocolError)
_CHUNK_BYTES = 64 * 1024
_STORAGE_MEDIA_TYPES = frozenset({"", "application/octet-stream", "application/zip", "text/plain"})


class StorageService:
    def __init__(self, graphql: GraphQLExecutor) -> None:
        self._graphql = graphql

    def upload(
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
        chunks = _UploadChunks(source, limit)
        mapped_error: MutationOutcomeUnknownError | None = None
        input_error: ConfigurationError | None = None
        try:
            self._graphql.upload_binary(
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

    def upload_file(
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
        try:
            if source.stat().st_size > limit:
                raise ConfigurationError("Storage upload exceeds the configured limit.")
            with source.open("rb") as stream:
                return self.upload(
                    namespace_id=namespace_id,
                    path=path,
                    source=stream,
                    max_bytes=limit,
                )
        except OSError:
            pass
        raise ConfigurationError("Could not read the storage upload source.")

    def download(
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
        count = self._graphql.download_binary(
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

    def download_file(
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
        if not destination.parent.is_dir():
            raise ConfigurationError("Storage destination directory does not exist.")
        if destination.exists() and not overwrite:
            raise ConfigurationError("Storage destination already exists; use overwrite=True.")

        temporary_path: Path | None = None
        try:
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{destination.name}.",
                dir=destination.parent,
            )
            temporary_path = Path(temporary_name)
            with os.fdopen(descriptor, "wb") as stream:
                receipt = self.download(
                    namespace_id=namespace_id,
                    path=path,
                    destination=stream,
                    max_bytes=max_bytes,
                )
            if overwrite:
                os.replace(temporary_path, destination)
            else:
                os.link(temporary_path, destination)
                temporary_path.unlink()
            temporary_path = None
            return receipt
        except OSError:
            pass
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
        raise ConfigurationError("Could not write the storage destination.")


class _UploadChunks:
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

    def __iter__(self) -> Iterator[bytes]:
        while True:
            try:
                chunk = self._source.read(_CHUNK_BYTES)
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


class _HashingWriter:
    def __init__(self, destination: BinaryIO) -> None:
        if not callable(getattr(destination, "write", None)):
            raise ConfigurationError("Storage destination must be writable.")
        self._destination = destination
        self._digest = hashlib.sha256()
        self.count = 0

    @property
    def hexdigest(self) -> str:
        return self._digest.hexdigest()

    def write(self, chunk: bytes) -> int | None:
        written = self._destination.write(chunk)
        accepted = len(chunk) if written is None else written
        if accepted == len(chunk):
            self._digest.update(chunk)
            self.count += len(chunk)
        return written


def _storage_endpoint(namespace_id: str, path: str) -> str:
    encoded_path = quote(path, safe="/-._~")
    return f"api/v1/storage/{namespace_id}/{encoded_path}"


def _local_path(value: str | os.PathLike[str], message: str) -> Path:
    result: Path | None = None
    try:
        result = Path(value)
    except TypeError:
        pass
    if result is None:
        raise ConfigurationError(message)
    return result
