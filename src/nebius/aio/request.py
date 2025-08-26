from asyncio import CancelledError, Future, ensure_future
from collections.abc import Awaitable, Callable, Generator, Iterable
from logging import getLogger
from sys import exc_info
from time import time
from typing import Any, Generic, TypeVar

from google.protobuf.message import Message as PMessage
from grpc import CallCredentials, Compression, StatusCode
from grpc.aio import AioRpcError
from grpc.aio import Metadata as GrpcMetadata
from grpc.aio._call import UnaryUnaryCall  # type: ignore[unused-ignore]
from grpc_status import rpc_status

from nebius.aio.abc import ClientChannelInterface as Channel
from nebius.aio.base import AddressChannel
from nebius.aio.idempotency import ensure_key_in_metadata
from nebius.base.error import SDKError
from nebius.base.metadata import Metadata

from .request_status import RequestStatus, UnfinishedRequestStatus

Req = TypeVar("Req")
Res = TypeVar("Res")
Err = TypeVar("Err")
T = TypeVar("T")

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
        compression: Compression | None = None,
        result_wrapper: Callable[[str, Channel, Any], Res] | None = None,
        grpc_channel_override: AddressChannel | None = None,
        error_wrapper: Callable[[RequestStatus], RequestError] | None = None,
        retries: int | None = 3,
        per_retry_timeout: float | None = None,
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
        self._per_retry_timeout = per_retry_timeout
        self._credentials = credentials
        self._compression = compression
        self._call: UnaryUnaryCall | None = None
        self._retries = retries
        self._cancelled: bool = False
        from .service_error import RequestError as RSError
        from .service_error import RequestStatusExtended

        ensure_key_in_metadata(self._input_metadata)

        self._error_wrapper = error_wrapper if error_wrapper is not None else RSError
        self._status: RequestStatusExtended | None = None
        self._initial_metadata: Metadata | None = None
        self._trailing_metadata: Metadata | None = None
        self._trace_id: str | None = None
        self._request_id: str | None = None

        self._awaited = False
        self._future: Future[Res] | None = None

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

    def _send(self, timeout: float | None) -> None:
        from nebius.base.protos.pb_classes import Message

        self._initial_metadata = None
        self._trailing_metadata = None
        self._status = None
        req = self._input
        if isinstance(req, Message):
            req = req.__pb2_message__  # type: ignore[assignment]
        if isinstance(req, PMessage):
            serializer = req.__class__.SerializeToString
        else:
            raise RequestError(f"Unsupported request type {type(req)}")
        if self._cancelled:
            raise RequestIsCancelledError()
        channel_parent_id = self._channel.parent_id()
        if channel_parent_id is not None:
            if self._method == "List" or self._method == "GetByName":
                if hasattr(req, "parent_id") and req.parent_id == "":  # type: ignore[unused-ignore]
                    req.parent_id = channel_parent_id  # type: ignore[unused-ignore]
            elif self._method != "Update":
                if hasattr(req, "metadata") and hasattr(req.metadata, "parent_id"):  # type: ignore[unused-ignore]
                    if req.metadata.parent_id == "":  # type: ignore[unused-ignore]
                        req.metadata.parent_id = channel_parent_id  # type: ignore[unused-ignore]
        self._sent = True
        if self._grpc_channel is None:
            self._grpc_channel = self._channel.get_channel_by_method(
                self._service + "." + self._method
            )
        s_name = self._service
        if s_name[0] == ".":
            s_name = s_name[1:]
        self._call = self._grpc_channel.channel.unary_unary(  # type: ignore
            "/" + s_name + "/" + self._method,
            serializer,
            self._result_pb2_class.FromString,
        )(
            req,
            timeout=timeout,
            metadata=GrpcMetadata(*self._input_metadata),
            credentials=self._credentials,
            wait_for_ready=True,
            compression=self._compression,
        )

    def run_sync_with_timeout(self, func: Awaitable[T]) -> T:
        try:
            timeout = self._timeout
            if timeout is not None:
                timeout += 0.2  # 200 ms for an internal graceful shutdown
            return self._channel.run_sync(func, timeout=timeout)
        except TimeoutError as e:
            from .service_error import RequestError, RequestStatusExtended

            self._status = RequestStatusExtended(
                code=StatusCode.DEADLINE_EXCEEDED,
                message="Deadline Exceeded",
                details=[],
                service_errors=[],
                request_id=self._request_id if self._request_id is not None else "",
                trace_id=self._trace_id if self._trace_id is not None else "",
            )
            raise RequestError(self._status) from e

    def wait(self) -> Res:
        return self.run_sync_with_timeout(self)

    def initial_metadata_sync(self) -> Metadata:
        if self._initial_metadata is not None:
            return self._initial_metadata
        return self.run_sync_with_timeout(self.initial_metadata())

    def trailing_metadata_sync(self) -> Metadata:
        if self._trailing_metadata is not None:
            return self._trailing_metadata
        return self.run_sync_with_timeout(self.trailing_metadata())

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
        return self.run_sync_with_timeout(self.request_id())

    def trace_id_sync(self) -> str:
        if self._trace_id is not None:
            return self._trace_id
        return self.run_sync_with_timeout(self.trace_id())

    async def initial_metadata(self) -> Metadata:
        try:
            await self._await_result()
        except Exception as e:  # noqa: S110
            if self._initial_metadata is not None:
                return self._initial_metadata
            raise e
        if self._initial_metadata is not None:
            return self._initial_metadata
        raise RequestError("no initial metadata after call finished")

    async def trailing_metadata(self) -> Metadata:
        try:
            await self._await_result()
        except Exception as e:  # noqa: S110
            if self._trailing_metadata is not None:
                return self._trailing_metadata
            raise e
        if self._trailing_metadata is not None:
            return self._trailing_metadata
        raise RequestError("no trailing metadata after call finished")

    def _parse_request_id(self) -> None:
        if self._initial_metadata is None:
            raise RequestError("no initial metadata")
        self._request_id = self._initial_metadata.get_one("x-request-id", "")
        self._trace_id = self._initial_metadata.get_one("x-trace-id", "")

    async def status(self) -> RequestStatus:
        try:
            await self._await_result()
        except Exception as e:  # noqa: S110
            if self._status is not None:
                return self._status
            raise e
        if self._status is not None:
            return self._status
        raise RequestError("no status after call finished")

    def _raise_request_error(self, err: AioRpcError) -> None:
        self._initial_metadata = Metadata(err.initial_metadata())
        self._trailing_metadata = Metadata(err.trailing_metadata())  # type: ignore
        self._parse_request_id()
        status = rpc_status.from_call(err)  # type: ignore
        from .service_error import RequestError, RequestStatusExtended

        debug_info = err.debug_error_string()
        if debug_info:
            log.debug(f"RPC Debug info: {debug_info}")

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

    def _convert_request_error(self, err: AioRpcError) -> None:
        from .service_error import RequestError

        try:
            self._raise_request_error(err)
        except RequestError:
            pass

    async def _retry_loop(self) -> Res:
        from .service_error import RequestError, is_retriable_error

        self._start_time = time()
        deadline = None if self._timeout is None else self._start_time + self._timeout
        attempt = 0
        while not self._cancelled:
            attempt += 1
            timeout = None if deadline is None else deadline - time()

            if self._per_retry_timeout is not None and (
                timeout is None or timeout > self._per_retry_timeout
            ):
                timeout = self._per_retry_timeout

            # somehow, this time python doesn't want to catch the raised error again
            # thus, it will be two nested try/except blocks
            try:
                try:
                    self._send(timeout)
                    if self._call is None:
                        raise RequestSentNoCallError()
                    ret = await self._call  # type: ignore[unused-ignore]
                    code = await self._call.code()
                    msg = await self._call.details()
                    mdi = await self._call.initial_metadata()
                    mdt = await self._call.trailing_metadata()
                    e = AioRpcError(code, mdi, mdt, msg, None)  # type: ignore
                    self._convert_request_error(e)
                    if self._result_wrapper is not None:
                        return self._result_wrapper(
                            self._service + "." + self._method,
                            self._channel,
                            ret,
                        )
                    self._channel.return_channel(self._grpc_channel)
                    self._grpc_channel = None
                    return ret  # type: ignore
                except CancelledError as e:
                    self._channel.discard_channel(self._grpc_channel)
                    self._grpc_channel = None
                    raise e
                except AioRpcError as e:
                    self._raise_request_error(e)
            except Exception as e:
                if (
                    (deadline is None or deadline > time())
                    and is_retriable_error(e, deadline_retriable=True)
                    and (self._retries is None or self._retries > attempt)
                ):
                    log.error(
                        f"request attempt {attempt} for {self} failed with {e} "
                        + "but will be retried",
                        exc_info=exc_info(),
                    )
                    continue
                if deadline is not None and deadline <= time():
                    if isinstance(e, RequestError) and e.status.request_id == "":
                        self._channel.discard_channel(self._grpc_channel)
                        self._grpc_channel = None
                self._channel.return_channel(self._grpc_channel)
                raise e
        raise RequestIsCancelledError()

    async def _await_result(self) -> Res:
        if self._future is None:
            self._future = ensure_future(self._retry_loop())
        return await self._future

    def __await__(self) -> Generator[Any, None, Res]:
        if self._awaited:
            raise RuntimeError("cannot await the finished coroutine")
        self._awaited = True

        res = yield from self._await_result().__await__()
        return res
