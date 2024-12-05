from typing import Any, Callable, Iterable, Tuple, Type, TypeVar

from google.protobuf.message import Message as PMessage
from grpc import CallCredentials, Compression
from grpc.aio import Channel as GRPCChannel

from nebius.aio.abc import ClientChannelInterface as Channel
from nebius.aio.request import Request

# from nebius.api.nebius.common.v1 import Operation
from nebius.base.metadata import Metadata

Req = TypeVar("Req")
Res = TypeVar("Res")


class Client:
    # __operation_type__: Message = Operation
    __service_name__: str

    def __init__(self, channel: Channel) -> None:
        self._channel = channel

    def request(
        self,
        method: str,
        request: Req,
        result_pb2_class: Type[PMessage],
        metadata: Metadata | Iterable[Tuple[str, str]] | None = None,
        timeout: float | None = None,
        credentials: CallCredentials | None = None,
        wait_for_ready: bool | None = None,
        compression: Compression | None = None,
        result_wrapper: Callable[[GRPCChannel, Any], Res] | None = None,
    ) -> Request[Req, Res]:
        return Request[Req, Res](
            channel=self._channel,
            service=self.__service_name__,
            method=method,
            request=request,
            metadata=metadata,
            result_pb2_class=result_pb2_class,
            timeout=timeout,
            credentials=credentials,
            wait_for_ready=wait_for_ready,
            compression=compression,
            result_wrapper=result_wrapper,
        )


class OperationClient(Client):
    def __init__(self, parent: Client) -> None:
        super().__init__(parent._channel)
        self._parent = parent

    def request(
        self,
        method: str,
        request: Req,
        result_pb2_class: Type[PMessage],
        metadata: Metadata | Iterable[Tuple[str, str]] | None = None,
        timeout: float | None = None,
        credentials: CallCredentials | None = None,
        wait_for_ready: bool | None = None,
        compression: Compression | None = None,
        result_wrapper: Callable[[GRPCChannel, Any], Res] | None = None,
    ) -> Request[Req, Res]:
        return Request[Req, Res](
            channel=self._channel,
            service=self.__service_name__,
            method=method,
            request=request,
            result_pb2_class=result_pb2_class,
            metadata=metadata,
            timeout=timeout,
            credentials=credentials,
            wait_for_ready=wait_for_ready,
            compression=compression,
            result_wrapper=result_wrapper,
        )
