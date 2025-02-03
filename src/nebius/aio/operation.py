from asyncio import sleep
from collections.abc import Awaitable, Iterable
from datetime import datetime, timedelta
from time import time
from typing import Generic, TypeVar

from grpc import CallCredentials, Compression, StatusCode
from grpc.aio import Channel as GRPCChannel

from nebius.aio.abc import ClientChannelInterface, SyncronizerInterface
from nebius.base.error import SDKError
from nebius.base.protos.well_known import local_timezone

from .request_status import RequestStatus

OperationPb = TypeVar("OperationPb")

T = TypeVar("T")


class Static(ClientChannelInterface):
    def __init__(
        self,
        channel: GRPCChannel,
        syncronizer: SyncronizerInterface,
    ) -> None:
        self._channel = channel
        self._syncronizer = syncronizer

    def get_channel_by_method(self, method_name: str) -> GRPCChannel:
        return self._channel

    def run_sync(self, awaitable: Awaitable[T], timeout: float | None = None) -> T:
        return self._syncronizer.run_sync(awaitable, timeout)


class Operation(Generic[OperationPb]):
    def __init__(
        self,
        channel: GRPCChannel,
        syncronizer: SyncronizerInterface,
        operation: OperationPb,
    ) -> None:
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

        self._syncronizer = syncronizer
        _operation: OperationPb | Operation | Old = operation
        if isinstance(_operation, Operation.__PB2_CLASS__):
            _operation = Operation(_operation)
        if isinstance(_operation, Old.__PB2_CLASS__):
            _operation = Old(_operation)

        if isinstance(_operation, Operation):
            self._service: OperationServiceClient | OldClient = OperationServiceClient(
                Static(channel, syncronizer)
            )
            self._get_request_obj: type[GetOperationRequest | OldGet] = (
                GetOperationRequest
            )
        elif isinstance(_operation, Old):
            self._service = OldClient(Static(channel, syncronizer))
            self._get_request_obj = OldGet
        else:
            raise SDKError(f"Operation type {type(_operation)} not supported.")

        self._operation: Operation | Old = _operation
        self._channel = channel

    def __repr__(self) -> str:
        return (
            f"Operation({self.id}, resource_id: {self.resource_id}, "
            f"status: {self.status()})"
        )

    def status(self) -> RequestStatus | None:
        return self._operation.status

    def done(self) -> bool:
        return self.status() is not None

    async def update(
        self,
        metadata: Iterable[tuple[str, str]] | None = None,
        timeout: float | None = None,
        credentials: CallCredentials | None = None,
        compression: Compression | None = None,
    ) -> None:
        if self.done():
            return

        req = self._service.get(
            self._get_request_obj(id=self.id),  # type: ignore
            metadata=metadata,
            timeout=timeout,
            credentials=credentials,
            compression=compression,
        )
        new_op = await req
        self._set_new_operation(new_op._operation)  # type: ignore

    def sync_wait(self, timeout: float | None = None) -> None:
        return self._syncronizer.run_sync(self.wait(), timeout)

    def sync_update(self, timeout: float | None = None) -> None:
        return self._syncronizer.run_sync(self.update(), timeout)

    async def wait(
        self,
        interval: float | timedelta = 1,
        metadata: Iterable[tuple[str, str]] | None = None,
        timeout: float | None = None,
        credentials: CallCredentials | None = None,
        compression: Compression | None = None,
    ) -> None:
        start = time()
        if isinstance(interval, timedelta):
            interval = interval.total_seconds()
        if not self.done():
            await self.update(
                metadata=metadata,
                timeout=timeout,
                credentials=credentials,
                compression=compression,
            )
        while not self.done():
            if timeout is not None and time() < start + timeout:
                raise TimeoutError("Operation wait timeout")
            await sleep(interval)
            await self.update(
                metadata=metadata,
                timeout=timeout,
                credentials=credentials,
                compression=compression,
            )

    def _set_new_operation(self, operation: OperationPb) -> None:
        if isinstance(operation, self._operation.__class__):
            self._operation = operation  # type: ignore
        else:
            raise SDKError(f"Operation type {type(operation)} not supported.")

    @property
    def id(self) -> str:
        return self._operation.id

    @property
    def description(self) -> str:
        return self._operation.description

    @property
    def created_at(self) -> datetime:
        ca = self._operation.created_at
        if ca is None:
            return datetime.now(local_timezone)
        return ca

    @property
    def created_by(self) -> str:
        return self._operation.created_by

    @property
    def finished_at(self) -> datetime | None:
        return self._operation.finished_at

    @property
    def resource_id(self) -> str:
        return self._operation.resource_id

    def successful(self) -> bool:
        s = self.status()
        return s is not None and s.code == StatusCode.OK

    def raw(self) -> OperationPb:
        return self._operation  # type: ignore
