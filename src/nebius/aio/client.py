from collections.abc import Callable, Iterable
from logging import getLogger
from typing import Any, Generic, TypeVar

from google.protobuf.message import Message as PMessage
from grpc import CallCredentials, Compression

from nebius.aio.abc import ClientChannelInterface as Channel
from nebius.aio.constant_channel import Constant
from nebius.aio.request import Request

# from nebius.api.nebius.common.v1 import Operation
from nebius.base.metadata import Metadata

Req = TypeVar("Req")
Res = TypeVar("Res")


class Client:
    # __operation_type__: Message = Operation
    __service_name__: str
    __service_deprecation_details__: str | None = None

    def __init__(self, channel: Channel) -> None:
        self._channel = channel

        if self.__service_deprecation_details__ is not None:
            getLogger("deprecation").warning(
                f"Service {self.__service_name__} is deprecated. "
                f"{self.__service_deprecation_details__}",
                stack_info=True,
                stacklevel=2,
            )

    def request(
        self,
        method: str,
        request: Req,
        result_pb2_class: type[PMessage],
        metadata: Metadata | Iterable[tuple[str, str]] | None = None,
        timeout: float | None = None,
        credentials: CallCredentials | None = None,
        compression: Compression | None = None,
        result_wrapper: Callable[[str, Channel, Any], Res] | None = None,
        retries: int | None = 3,
        per_retry_timeout: float | None = None,
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
            per_retry_timeout=per_retry_timeout,
        )


OperationPb = TypeVar("OperationPb")
OperationService = TypeVar("OperationService", bound=Client)


class ClientWithOperations(Client, Generic[OperationPb, OperationService]):
    __operation_type__: type[OperationPb]
    __operation_service_class__: type[OperationService]
    __operation_source_method__: str

    def __init__(self, channel: Channel) -> None:
        super().__init__(channel)
        self.__operation_service__: OperationService | None = None

    def operation_service(self) -> OperationService:
        if self.__operation_service__ is None:
            self.__operation_service__ = self.__operation_service_class__(
                Constant(
                    self.__service_name__ + "." + self.__operation_source_method__,
                    self._channel,
                )
            )
        return self.__operation_service__
