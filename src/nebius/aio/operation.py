"""Helpers for working with long-running operations.

This module provides an :class:`Operation` wrapper that normalizes different
versions of the service operation protobuf and exposes convenient helpers for
polling, synchronous waiting, and inspecting operation metadata.

The wrapper accepts operation protobufs from either the current v1 API or an
older v1alpha1 variant and routes calls to the corresponding operation
service client.
"""

from asyncio import sleep
from collections.abc import Iterable
from datetime import datetime, timedelta
from time import time
from typing import Generic, TypeVar

from grpc import CallCredentials, Compression, StatusCode

from nebius.aio.abc import ClientChannelInterface
from nebius.aio.request import DEFAULT_TIMEOUT
from nebius.base.error import SDKError
from nebius.base.protos.unset import Unset, UnsetType
from nebius.base.protos.well_known import local_timezone

from .constant_channel import Constant
from .request_status import RequestStatus

OperationPb = TypeVar("OperationPb")
"""
A convenience wrapper around operation protobufs.
Either :class:`nebius.api.nebius.common.v1.Operation` or
:class:`nebius.api.nebius.common.v1alpha1.Operation`, or their protobuf classes.
"""
T = TypeVar("T")


class Operation(Generic[OperationPb]):
    """A convenience wrapper around operation protobufs.

    The :class:`Operation` wrapper normalizes
    :class:`nebius.api.nebius.common.v1.Operation`
    and :class:`nebius.api.nebius.common.v1alpha1.Operation` representations and
    provides helpers to:

    - inspect operation metadata (id, resource_id, timestamps),
    - poll/update the operation state via the corresponding operation
      service, and
    - wait for completion either asynchronously or synchronously.

    The wrapper stores an operation service client bound to a
    :class:`nebius.aio.constant_channel.Constant` that points at the provided
    ``source_method`` and reuses the provided ``channel`` for network/auth
    behaviors.

    :param source_method: the originating ``service.method`` name used to build a
        constant channel for operation management calls
    :param channel: channel used for network and auth operations
    :type channel: :class:`ClientChannelInterface`
    :param operation: an operation protobuf instance (v1 or v1alpha1)
    :type operation: either :class:`nebius.api.nebius.common.v1.Operation` or
        :class:`nebius.api.nebius.common.v1alpha1.Operation`, or their protobuf
        classes.
    """

    def __init__(
        self,
        source_method: str,
        channel: ClientChannelInterface,
        operation: OperationPb,
    ) -> None:
        """Create an operation wrapper from the operation protobuf."""
        from nebius.api.nebius.common.v1 import (
            GetOperationRequest,
            Operation,
            OperationServiceClient,
        )
        from nebius.api.nebius.common.v1alpha1 import (
            GetOperationRequest as OldGet,
        )
        from nebius.api.nebius.common.v1alpha1 import (
            Operation as Old,
        )
        from nebius.api.nebius.common.v1alpha1 import (
            OperationServiceClient as OldClient,
        )

        self._channel = channel
        _operation: OperationPb | Operation | Old = operation
        if isinstance(_operation, Operation.__PB2_CLASS__):
            _operation = Operation(_operation)
        if isinstance(_operation, Old.__PB2_CLASS__):
            _operation = Old(_operation)

        if isinstance(_operation, Operation):
            self._service: OperationServiceClient | OldClient = OperationServiceClient(
                Constant(source_method, channel)
            )
            self._get_request_obj: type[GetOperationRequest | OldGet] = (
                GetOperationRequest
            )
        elif isinstance(_operation, Old):
            self._service = OldClient(Constant(source_method, channel))
            self._get_request_obj = OldGet
        else:
            raise SDKError(f"Operation type {type(_operation)} not supported.")

        self._operation: Operation | Old = _operation

    def __repr__(self) -> str:
        """Return a compact string representation useful for debugging."""
        return (
            f"Operation({self.id}, resource_id: {self.resource_id}, "
            f"status: {self.status()})"
        )

    def status(self) -> RequestStatus | None:
        """Return the operation's current status object or ``None``.

        :rtype: :class:`RequestStatus` or nothing
        """
        return self._operation.status

    def done(self) -> bool:
        """Return True when the operation has reached a terminal state."""
        return self.status() is not None

    async def update(
        self,
        metadata: Iterable[tuple[str, str]] | None = None,
        timeout: float | None | UnsetType = Unset,
        credentials: CallCredentials | None = None,
        compression: Compression | None = None,
        per_retry_timeout: float | None | UnsetType = Unset,
        retries: int | None = None,
    ) -> None:
        """Fetch the latest operation data from the operation service.

        This coroutine performs a single get operation using the internal
        operation service client and replaces the wrapped operation object
        with the returned value.

        :param metadata: optional gRPC metadata for the get call
        :param timeout: optional overall timeout for the get call
        :type timeout: optional `float` or `None`
        :param credentials: optional call credentials for the RPC
        :param compression: optional compression policy for the call
        :param per_retry_timeout: optional per-retry timeout forwarded to the
            request helper
        :type per_retry_timeout: optional `float` or `None`
        :param retries: optional retry count for the get call
        """
        if self.done():
            return

        req = self._service.get(
            self._get_request_obj(id=self.id),  # type: ignore
            metadata=metadata,
            timeout=timeout,
            credentials=credentials,
            compression=compression,
            per_retry_timeout=per_retry_timeout,
            retries=retries,
        )
        new_op = await req
        self._set_new_operation(new_op._operation)  # type: ignore

    def sync_wait(
        self,
        interval: float | timedelta = 1,
        metadata: Iterable[tuple[str, str]] | None = None,
        timeout: float | None = None,
        credentials: CallCredentials | None = None,
        compression: Compression | None = None,
        poll_iteration_timeout: float | None | UnsetType = Unset,
        poll_per_retry_timeout: float | None | UnsetType = Unset,
        poll_retries: int | None = None,
    ) -> None:
        """Synchronously wait for the operation to complete.

        This helper wraps :meth:`wait` and executes it in the channel's
        synchronous runner so callers that are not coroutine-based can wait
        for operation completion.

        :param interval: polling interval between updates (seconds or timedelta)
        :type interval: `float` or `timedelta`
        :param metadata: optional metadata forwarded to each update call
        :param timeout: overall timeout for the synchronous wait
        :type timeout: optional `float` or `None`
        :param credentials: optional call credentials forwarded to updates
        :param compression: optional compression forwarded to updates
        :param poll_iteration_timeout: timeout used for each polling iteration
        :type poll_iteration_timeout: optional `float` or `None`
        :param poll_per_retry_timeout: per-retry timeout for polling requests
        :type poll_per_retry_timeout: optional `float` or `None`
        :param poll_retries: retry count used for polling requests
        :type poll_retries: optional `int` or `None`
        """
        run_timeout = None if timeout is None else timeout + 0.2
        return self._channel.run_sync(
            self.wait(
                interval=interval,
                metadata=metadata,
                timeout=timeout,
                credentials=credentials,
                compression=compression,
                poll_iteration_timeout=poll_iteration_timeout,
                poll_per_retry_timeout=poll_per_retry_timeout,
                poll_retries=poll_retries,
            ),
            run_timeout,
        )

    def sync_update(
        self,
        metadata: Iterable[tuple[str, str]] | None = None,
        timeout: float | None | UnsetType = Unset,
        credentials: CallCredentials | None = None,
        compression: Compression | None = None,
        per_retry_timeout: float | None | UnsetType = Unset,
        retries: int | None = None,
    ) -> None:
        """Synchronously perform a single update of the operation state.

        This wraps the coroutine :meth:`update` and runs it via the channel's
        synchronous runner. A small safety margin is added to the provided
        timeout to allow for scheduling overhead.

        :param metadata: optional gRPC metadata for the get call
        :param timeout: optional overall timeout for the get call
        :type timeout: optional `float` or `None`
        :param credentials: optional call credentials for the RPC
        :param compression: optional compression policy for the call
        :param per_retry_timeout: optional per-retry timeout forwarded to the
            request helper
        :type per_retry_timeout: optional `float` or `None`
        :param retries: optional retry count for the get call
        """
        run_timeout: float | None = None
        if isinstance(timeout, (int, float)):
            run_timeout = timeout + 0.2
        elif isinstance(timeout, UnsetType):
            run_timeout = DEFAULT_TIMEOUT + 0.2
        return self._channel.run_sync(
            self.update(
                metadata=metadata,
                timeout=timeout,
                credentials=credentials,
                compression=compression,
                per_retry_timeout=per_retry_timeout,
                retries=retries,
            ),
            run_timeout,
        )

    async def wait(
        self,
        interval: float | timedelta = 1,
        metadata: Iterable[tuple[str, str]] | None = None,
        timeout: float | None = None,
        credentials: CallCredentials | None = None,
        compression: Compression | None = None,
        poll_iteration_timeout: float | UnsetType | None = Unset,
        poll_per_retry_timeout: float | UnsetType | None = Unset,
        poll_retries: int | None = None,
    ) -> None:
        """Asynchronously wait until the operation reaches a terminal state.

        The method repeatedly invokes :meth:`update` at the specified
        ``interval`` until the operation is done or the overall ``timeout`` is
        reached. Certain transient errors (deadline exceeded) are treated as
        ignorable and will be retried.

        :param interval: polling interval (seconds or timedelta)
        :type interval: `float` or `timedelta`
        :param metadata: optional metadata forwarded to each update call
        :param timeout: overall timeout for waiting
        :type timeout: optional `float` or `None`
        :param credentials: optional call credentials forwarded to updates
        :param compression: optional compression forwarded to updates
        :param poll_iteration_timeout: timeout used for each polling iteration
        :type poll_iteration_timeout: optional `float` or `None`
        :param poll_per_retry_timeout: per-retry timeout for polling requests
        :type poll_per_retry_timeout: optional `float` or `None`
        :param poll_retries: retry count used for polling requests
        :raises TimeoutError: when the overall timeout is exceeded
        """
        start = time()
        if poll_iteration_timeout is None:
            if timeout is not None:
                poll_iteration_timeout = min(5, timeout)
        if isinstance(interval, timedelta):
            interval = interval.total_seconds()
        from nebius.aio.service_error import RequestError as ServiceRequestError

        def _is_ignorable(err: Exception) -> bool:
            # TimeoutError raised locally or RequestError with DEADLINE_EXCEEDED
            if isinstance(err, TimeoutError):
                return True
            if isinstance(err, ServiceRequestError):
                try:
                    return err.status.code == StatusCode.DEADLINE_EXCEEDED
                except Exception:  # pragma: no cover - defensive
                    return False
            return False

        async def _safe_update() -> None:
            try:
                await self.update(
                    metadata=metadata,
                    timeout=poll_iteration_timeout,
                    credentials=credentials,
                    compression=compression,
                    per_retry_timeout=poll_per_retry_timeout,
                    retries=poll_retries,
                )
            except Exception as e:  # noqa: S110
                if not _is_ignorable(e):
                    raise

        if not self.done():
            await _safe_update()
        while not self.done():
            current_time = time()
            if timeout is not None and current_time > timeout + start:
                raise TimeoutError("Operation wait timeout")
            await sleep(interval)
            await _safe_update()

    def _set_new_operation(self, operation: OperationPb) -> None:
        """Replace the wrapped operation object with a new instance.

        The replacement is only allowed when the new operation has the same
        protobuf class as the currently wrapped object; otherwise an
        :class:`SDKError` is raised.
        """
        if isinstance(operation, self._operation.__class__):
            self._operation = operation  # type: ignore
        else:
            raise SDKError(f"Operation type {type(operation)} not supported.")

    @property
    def id(self) -> str:
        """Return the operation identifier (string)."""
        return self._operation.id

    @property
    def description(self) -> str:
        """Return the operation description as provided by the service."""
        return self._operation.description

    @property
    def created_at(self) -> datetime:
        """Return the operation creation timestamp.

        If the underlying protobuf does not expose a creation time this helper
        returns the current time in the local timezone.
        :rtype: datetime
        """
        ca = self._operation.created_at
        if ca is None:  # type: ignore[unused-ignore]
            return datetime.now(local_timezone)
        return ca

    @property
    def created_by(self) -> str:
        """Return the identity that created the operation (string)."""
        return self._operation.created_by

    @property
    def finished_at(self) -> datetime | None:
        """Return the completion timestamp for the operation or ``None`` if
        the operation hasn't finished yet.
        """
        return self._operation.finished_at

    @property
    def resource_id(self) -> str:
        """Return the resource id associated with the operation."""
        return self._operation.resource_id

    def successful(self) -> bool:
        """Return True when the operation completed successfully."""
        s = self.status()
        return s is not None and s.code == StatusCode.OK

    def raw(self) -> OperationPb:
        """Return the underlying operation protobuf object.

        Use this to access version-specific fields that are not exposed by the
        normalized wrapper.
        """
        return self._operation  # type: ignore
