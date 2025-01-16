from collections.abc import Callable, Generator, Iterable
from logging import getLogger
from typing import Any, Generic, TypeVar

from google.protobuf.message import Message as PMessage
from grpc import CallCredentials, Compression
from grpc.aio import AioRpcError
from grpc.aio import Channel as GRPCChannel
from grpc.aio import Metadata as GrpcMetadata
from grpc.aio._call import UnaryUnaryCall  # type: ignore[unused-ignore]
from grpc_status import rpc_status

from nebius.aio.abc import ClientChannelInterface as Channel
from nebius.aio.abc import SyncronizerInterface
from nebius.base.error import SDKError
from nebius.base.metadata import Metadata

from .request_status import RequestStatus, UnfinishedRequestStatus

Req = TypeVar("Req")
Res = TypeVar("Res")
Err = TypeVar("Err")

log = getLogger(__name__)


class RequestError(SDKError):
    pass


class RequestIsSentError(RequestError):
    def __init__(self) -> None:
        super().__init__("Request is already sent")


class RequestIsCancelledError(RequestError):
    def __init__(self) -> None:
        super().__init__("Request is cancelled")


class RequestSentNoCallError(RequestError):
    def __init__(self) -> None:
        super().__init__("Request marked as sent without call.")


class Request(Generic[Req, Res]):
    def __init__(
        self,
        channel: Channel,
        service: str,
        method: str,
        request: Req,
        result_pb2_class: type[PMessage],
        metadata: Metadata | Iterable[tuple[str, str]] | None = None,
        timeout: float | None = None,
        credentials: CallCredentials | None = None,
        wait_for_ready: bool | None = None,
        compression: Compression | None = None,
        result_wrapper: (
            Callable[[GRPCChannel, SyncronizerInterface, Any], Res] | None
        ) = None,
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
        from .service_error import RequestError as RSError
        from .service_error import RequestStatusExtended

        self._error_wrapper = error_wrapper if error_wrapper is not None else RSError
        self._status: RequestStatusExtended | None = None
        self._initial_metadata: Metadata | None = None
        self._trailing_metadata: Metadata | None = None
        self._trace_id: str | None = None
        self._request_id: str | None = None

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}({self._service}.{self._method}, "
            f"{self.current_status()})"
        )

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
            metadata=GrpcMetadata(*self._input_metadata),
            credentials=self._credentials,
            wait_for_ready=self._wait_for_ready,
            compression=self._compression,
        )

    def wait(self) -> Res:
        return self._channel.run_sync(self, timeout=self._timeout)

    def initial_metadata_sync(self) -> Metadata:
        if self._initial_metadata is not None:
            return self._initial_metadata
        return self._channel.run_sync(self.initial_metadata(), timeout=self._timeout)

    def trailing_metadata_sync(self) -> Metadata:
        if self._trailing_metadata is not None:
            return self._trailing_metadata
        return self._channel.run_sync(self.trailing_metadata(), timeout=self._timeout)

    def current_status(self) -> RequestStatus | UnfinishedRequestStatus:
        if self._status is not None:
            return self._status
        if self._call is None:
            return UnfinishedRequestStatus.INITIALIZED
        return UnfinishedRequestStatus.SENT

    async def _get_request_id(self) -> tuple[str, str]:
        if self._request_id is not None and self._trace_id is not None:
            return (self._request_id, self._trace_id)
        await self.initial_metadata()
        return (self._request_id, self._trace_id)  # type: ignore[return-value] # should be set after receiving md

    async def request_id(self) -> str:
        ret = await self._get_request_id()
        return ret[0]

    async def trace_id(self) -> str:
        ret = await self._get_request_id()
        return ret[1]

    def request_id_sync(self) -> str:
        if self._request_id is not None:
            return self._request_id
        return self._channel.run_sync(self.request_id(), timeout=self._timeout)

    def trace_id_sync(self) -> str:
        if self._trace_id is not None:
            return self._trace_id
        return self._channel.run_sync(self.trace_id(), timeout=self._timeout)

    async def initial_metadata(self) -> Metadata:
        from .service_error import RequestError

        if self._initial_metadata is None:
            if self._call is None:
                self.send()
            if self._call is None:
                raise RequestSentNoCallError()
            try:
                md = await self._call.initial_metadata()
                self._initial_metadata = Metadata(md)
                self._parse_request_id()
            except AioRpcError as e:
                self._raise_request_error(e)
            except RequestError:
                pass
        return self._initial_metadata  # type: ignore[return-value] # _raise_request_error sets it

    async def trailing_metadata(self) -> Metadata:
        from .service_error import RequestError

        if self._trailing_metadata is None:
            if self._call is None:
                self.send()
            if self._call is None:
                raise RequestSentNoCallError()
            try:
                md = await self._call.trailing_metadata()
                self._trailing_metadata = Metadata(md)
            except AioRpcError as e:
                self._raise_request_error(e)
            except RequestError:
                pass
        return self._trailing_metadata  # type: ignore[return-value] # _raise_request_error sets it

    def _parse_request_id(self) -> None:
        if self._initial_metadata is None:
            raise RequestError("no initial metadata")
        self._request_id = self._initial_metadata.get_one("x-request-id", "")
        self._trace_id = self._initial_metadata.get_one("x-trace-id", "")

    async def status(self) -> RequestStatus:
        from .service_error import RequestError, RequestStatusExtended

        e: AioRpcError
        if self._status is not None:
            return self._status
        if self._call is None:
            self.send()
        if self._call is None:
            raise RequestSentNoCallError()
        try:
            code = await self._call.code()
            msg = await self._call.details()
            mdi = await self._call.initial_metadata()
            mdt = await self._call.trailing_metadata()
            e = AioRpcError(code, mdi, mdt, msg, None)  # type: ignore
        except AioRpcError as e:
            self._raise_request_error(e)
        except RequestError:
            return self._status  # type: ignore # set by _raise_request_error
        status = rpc_status.from_call(e)  # type: ignore

        if status is None:
            self._status = RequestStatusExtended(
                code=e.code(),  # type: ignore[misc] # when unbound, flow returns early
                message=e.details(),  # type: ignore[misc] # when unbound, flow returns early
                details=[],
                service_errors=[],
                request_id=self._request_id,  # type: ignore[arg-type] # should be strings by now
                trace_id=self._trace_id,  # type: ignore[arg-type] # should be strings by now
            )
        else:
            self._status = RequestStatusExtended.from_rpc_status(  # type: ignore[unused-ignore]
                status,
                trace_id=self._trace_id,  # type: ignore[arg-type] # should be known by now
                request_id=self._request_id,  # type: ignore[arg-type] # should be known by now
            )
        return self._status

    def _raise_request_error(self, err: AioRpcError) -> None:
        self._initial_metadata = Metadata(err.initial_metadata())
        self._trailing_metadata = Metadata(err.trailing_metadata())  # type: ignore
        self._parse_request_id()
        status = rpc_status.from_call(err)  # type: ignore
        from .service_error import RequestError, RequestStatusExtended

        if status is None:
            self._status = RequestStatusExtended(
                code=err.code(),
                message=err.details(),
                details=[],
                service_errors=[],
                request_id=self._request_id,  # type: ignore[arg-type] # should be strings by now
                trace_id=self._trace_id,  # type: ignore[arg-type] # should be strings by now
            )
            raise RequestError(self._status) from None

        self._status = RequestStatusExtended.from_rpc_status(  # type: ignore[unused-ignore]
            status,
            trace_id=self._trace_id,  # type: ignore[arg-type] # should be strings by now
            request_id=self._request_id,  # type: ignore[arg-type] # should be known by now
        )
        raise RequestError(self._status) from None

    def __await__(self) -> Generator[Any, None, Res]:  # type: ignore[return] # it returns or raises
        if self._call is None:
            self.send()
        if self._call is None:
            raise RequestSentNoCallError()
        try:
            ret = yield from self._call.__await__()  # type: ignore[unused-ignore]
            if self._result_wrapper is not None:
                return self._result_wrapper(self._grpc_channel, self._channel, ret)  # type: ignore
            return ret  # type: ignore
        except AioRpcError as e:
            self._raise_request_error(e)
