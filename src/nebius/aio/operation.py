from asyncio import sleep
from datetime import datetime, timedelta
from time import time
from typing import Generic, Iterable, Tuple, Type, TypeVar

from grpc import CallCredentials, Compression, StatusCode
from grpc.aio import Channel as GRPCChannel

from nebius.aio.abc import ClientChannelInterface
from nebius.base.error import SDKError
from nebius.base.protos.well_known import local_timezone

from .request_status import RequestStatus

OperationPb = TypeVar("OperationPb")


class Static(ClientChannelInterface):
    def __init__(self, channel: GRPCChannel) -> None:
        self._channel = channel

    def get_channel_by_method(self, method_name: str) -> GRPCChannel:
        return self._channel


class Operation(Generic[OperationPb]):
    def __init__(self, channel: GRPCChannel, operation: OperationPb):
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

        if isinstance(operation, Operation):
            self._service: OperationServiceClient | OldClient = OperationServiceClient(
                Static(channel)
            )
            self._get_request_obj: Type[GetOperationRequest | OldGet] = (
                GetOperationRequest
            )
        elif isinstance(operation, Old):
            self._service = OldClient(Static(channel))
            self._get_request_obj = OldGet
        else:
            raise SDKError(f"Operation type {type(operation)} not supported.")

        self._operation: Operation | Old = operation  # type: ignore
        self._channel = channel

    def status(self) -> RequestStatus | None:
        return self._operation.status

    def done(self) -> bool:
        return self.status() is not None

    async def update(
        self,
        metadata: Iterable[Tuple[str, str]] | None = None,
        timeout: float | None = None,
        credentials: CallCredentials | None = None,
        wait_for_ready: bool | None = None,
        compression: Compression | None = None,
    ) -> None:
        if self.done():
            return

        req = self._service.get(
            self._get_request_obj(id=self.id),  # type: ignore
            metadata=metadata,
            timeout=timeout,
            credentials=credentials,
            wait_for_ready=wait_for_ready,
            compression=compression,
        )
        new_op = await req
        self._set_new_operation(new_op._operation)  # type: ignore

    async def wait(
        self,
        interval: float | timedelta = 1,
        metadata: Iterable[Tuple[str, str]] | None = None,
        timeout: float | None = None,
        credentials: CallCredentials | None = None,
        wait_for_ready: bool | None = None,
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
                wait_for_ready=wait_for_ready,
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
                wait_for_ready=wait_for_ready,
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
