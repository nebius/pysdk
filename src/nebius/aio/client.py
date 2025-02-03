from collections.abc import Callable, Iterable
from typing import Any, TypeVar

from google.protobuf.message import Message as PMessage
from grpc import CallCredentials, Compression
from grpc.aio import Channel as GRPCChannel

from nebius.aio.abc import ClientChannelInterface as Channel
from nebius.aio.abc import SyncronizerInterface
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
        result_pb2_class: type[PMessage],
        metadata: Metadata | Iterable[tuple[str, str]] | None = None,
        timeout: float | None = None,
        credentials: CallCredentials | None = None,
        compression: Compression | None = None,
        result_wrapper: (
            Callable[[GRPCChannel, SyncronizerInterface, Any], Res] | None
        ) = None,
        retries: int | None = 3,
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
            compression=compression,
            result_wrapper=result_wrapper,
            retries=retries,
        )
