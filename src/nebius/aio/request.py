from typing import Any, Callable, Generator, Generic, Iterable, Tuple, Type, TypeVar

from google.protobuf.message import Message as PMessage
from grpc import CallCredentials, Compression
from grpc.aio import AioRpcError
from grpc.aio import Channel as GRPCChannel
from grpc.aio._call import UnaryUnaryCall
from grpc_status import rpc_status

from nebius.aio.abc import ClientChannelInterface as Channel
from nebius.base.error import SDKError
from nebius.base.metadata import Metadata

from .request_status import RequestStatus

Req = TypeVar("Req")
Res = TypeVar("Res")
Err = TypeVar("Err")


class RequestError(SDKError):
    pass


class RequestIsSentError(RequestError):
    def __init__(self) -> None:
        super().__init__("Request is already sent")


class RequestIsCancelledError(RequestError):
    def __init__(self) -> None:
        super().__init__("Request is cancelled")


class UnparsedRequestStatusError(RequestError):
    def __init__(self, status: RequestStatus) -> None:
        self.status = status
        if status.message is None:
            msg_x = "."
        else:
            msg_x = ": " + status.message
        super().__init__(f"GRPC error with code {status.code.name}{msg_x}")


class Request(Generic[Req, Res]):
    def __init__(
        self,
        channel: Channel,
        service: str,
        method: str,
        request: Req,
        result_pb2_class: Type[PMessage],
        metadata: Metadata | Iterable[Tuple[str, str]] | None = None,
        timeout: float | None = None,
        credentials: CallCredentials | None = None,
        wait_for_ready: bool | None = None,
        compression: Compression | None = None,
        result_wrapper: Callable[[GRPCChannel, Any], Res] | None = None,
        grpc_channel_override: GRPCChannel | None = None,
        error_wrapper: Callable[[RequestStatus], RequestError] | None = None,
    ) -> None:
        self._channel = channel
        self._input = request
        self._service = service
        self._method = method
        self._result_pb2_class = result_pb2_class
        self._input_metadata = Metadata(metadata)
        self._result_wrapper = result_wrapper
        self._grpc_channel = grpc_channel_override
        self._timeout = timeout
        self._credentials = credentials
        self._wait_for_ready = wait_for_ready
        self._compression = compression
        self._call: UnaryUnaryCall | None = None
        self._cancelled: bool = False
        self._error_wrapper = (
            error_wrapper if error_wrapper is not None else UnparsedRequestStatusError
        )
        self._status: RequestStatus | None = None

    def done(self) -> bool:
        if self._call is None:
            return False
        return self._call.done()

    def cancelled(self) -> bool:
        if self._call is not None:
            return self._call.cancelled()
        return self._cancelled

    def cancel(self) -> bool:
        if self._call is not None:
            return self._call.cancel()
        else:
            self._cancelled = True
            return self._cancelled

    def input_metadata(self) -> Metadata:
        return self._input_metadata

    @property
    def timeout(self) -> float | None:
        return self._timeout

    @timeout.setter
    def timeout(self, timeout: float | None) -> None:
        if self._call is not None:
            raise RequestIsSentError()
        self._timeout = timeout

    @property
    def credentials(self) -> CallCredentials | None:
        return self._credentials

    @credentials.setter
    def credentials(self, credentials: CallCredentials | None) -> None:
        if self._call is not None:
            raise RequestIsSentError()
        self._credentials = credentials

    @property
    def wait_for_ready(self) -> bool | None:
        return self._wait_for_ready

    @wait_for_ready.setter
    def wait_for_ready(self, wait_for_ready: bool | None) -> None:
        if self._call is not None:
            raise RequestIsSentError()
        self._wait_for_ready = wait_for_ready

    @property
    def compression(self) -> Compression | None:
        return self._compression

    @compression.setter
    def compression(self, compression: Compression | None) -> None:
        if self._call is not None:
            raise RequestIsSentError()
        self._compression = compression

    @property
    def is_sent(self) -> bool:
        return self._sent

    def wait(self) -> Res:
        from asyncio import run

        async def main() -> Res:
            return await self

        return run(main())

    def send(self) -> None:
        from nebius.base.protos.pb_classes import Message

        req = self._input
        if isinstance(req, Message):
            req = req.__pb2_message__  # type: ignore[assignment]
        if isinstance(req, PMessage):
            serializer = req.__class__.SerializeToString
        else:
            raise RequestError(f"Unsupported request type {type(req)}")
        if self._call is not None:
            raise RequestIsSentError()
        if self._cancelled:
            raise RequestIsCancelledError()
        self._sent = True
        if self._grpc_channel is None:
            self._grpc_channel = self._channel.get_channel_by_method(
                self._service + "." + self._method
            )
        s_name = self._service
        if s_name[0] == ".":
            s_name = s_name[1:]
        self._call = self._grpc_channel.unary_unary(  # type: ignore
            "/" + s_name + "/" + self._method,
            serializer,
            self._result_pb2_class.FromString,
        )(
            req,
            timeout=self._timeout,
            metadata=self._input_metadata,
            credentials=self._credentials,
            wait_for_ready=self._wait_for_ready,
            compression=self._compression,
        )

    async def initial_metadata(self) -> Metadata:
        if self._call is None:
            self.send()
        if self._call is None:
            raise SDKError("Request sent but no call found.")
        md = await self._call.initial_metadata()
        return Metadata(md)

    async def trailing_metadata(self) -> Metadata:
        if self._call is None:
            self.send()
        if self._call is None:
            raise SDKError("Request sent but no call found.")
        md = await self._call.trailing_metadata()
        return Metadata(md)

    async def status(self) -> RequestStatus:
        if self._status is not None:
            return self._status
        if self._call is None:
            self.send()
        if self._call is None:
            raise SDKError("Request sent but no call found.")
        code = await self._call.code()
        msg = await self._call.details()
        mdi = await self._call.initial_metadata()
        mdt = await self._call.trailing_metadata()
        e = AioRpcError(code, mdi, mdt, msg, None)  # type: ignore
        status = rpc_status.from_call(e)  # type: ignore
        if status is None:
            self._status = RequestStatus(
                code=e.code(),
                message=e.details(),
                details=[],
            )
        else:
            self._status = RequestStatus(
                code=status.code,
                message=status.message,
                details=status.details,
            )
        return self._status

    def __await__(self) -> Generator[Any, None, Res]:
        if self._call is None:
            self.send()
        if self._call is None:
            raise SDKError("Request sent but no call found.")
        try:
            ret = yield from self._call.__await__()  # type: ignore[unused-ignore]
            if self._result_wrapper is not None:
                return self._result_wrapper(self._grpc_channel, ret)  # type: ignore
            return ret  # type: ignore
        except AioRpcError as e:
            status = rpc_status.from_call(e)  # type: ignore
            if status is None:
                self._status = RequestStatus(
                    code=e.code(),
                    message=e.details(),
                    details=[],
                )
                raise self._error_wrapper(self._status)

            self._status = RequestStatus.from_rpc_status(status)  # type: ignore[unused-ignore]
            raise self._error_wrapper(self._status)
