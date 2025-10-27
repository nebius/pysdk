"""Request helper used by generated clients.

This module implements :class:`Request` which encapsulates a single RPC
invocation, including retries, authorization handling, metadata extraction
and convenience synchronous wrappers. The Request object is created by a
generated client and then awaited to perform the RPC. It is intentionally
rich: it exposes request status metadata (initial/trailing metadata,
request/trace ids), synchronous helpers (``wait``, ``initial_metadata_sync``)
and configurable retry/timeout behaviour.

Key concepts:

  - Authorization loop: when an authorization provider exists, the request
    will perform an auth step before attempting the RPC and will re-authenticate
    on UNAUTHENTICATED responses when allowed.
  - Retry loop: transient errors are retried according to configured retry
    counts and per-retry timeouts.

Only small, non-behavioral changes should be made to this module because the
Request logic is central to the SDK call semantics.
"""

from asyncio import CancelledError, Future, ensure_future, wait_for
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
from nebius.aio.authorization.options import OPTION_TYPE, Types
from nebius.aio.base import AddressChannel
from nebius.aio.idempotency import ensure_key_in_metadata
from nebius.base.error import SDKError
from nebius.base.metadata import Metadata
from nebius.base.protos.unset import Unset, UnsetType

from .request_status import RequestStatus, UnfinishedRequestStatus

Req = TypeVar("Req")
"""Request type variable. Either a protobuf/message or a serializable payload."""
Res = TypeVar("Res")
"""Response type variable. Either a protobuf/message or a custom wrapper."""
Err = TypeVar("Err")
"""Error type variable. Either a protobuf/message or a custom wrapper."""
T = TypeVar("T")

log = getLogger(__name__)


class RequestError(SDKError):
    """Base exception for errors raised while processing a request."""


class RequestIsSentError(RequestError):
    """Exception raised when a request is already sent."""

    def __init__(self) -> None:
        super().__init__("Request is already sent")


class RequestIsCancelledError(RequestError):
    """Exception raised when a request is cancelled."""

    def __init__(self) -> None:
        super().__init__("Request is cancelled")


class RequestSentNoCallError(RequestError):
    """Exception raised when a request is sent without a call."""

    def __init__(self) -> None:
        super().__init__("Request marked as sent without call.")


DEFAULT_TIMEOUT = 60.0  # second
"""Default timeout for requests not including authorization."""
DEFAULT_PER_RETRY_TIMEOUT = DEFAULT_TIMEOUT / 3
"""Default per-retry timeout for requests."""
DEFAULT_AUTH_TIMEOUT = 15 * 60.0  # 15 minutes
"""Default timeout including the authorization and the request itself."""


class Request(Generic[Req, Res]):
    """Encapsulates an RPC invocation with retries and auth handling.

    The :class:`Request` object is the workhorse behind generated client
    methods. It manages the lifecycle of a single RPC including:

    - preparing and populating protobuf request objects,
    - attaching metadata and idempotency keys,
    - performing an authorization step when needed, and
    - executing retry logic with per-attempt timeouts.

    Callers typically either ``await`` the request or call :meth:`wait` to run
    it synchronously.

    Parameters, that are general for all types of requests and are passed through
    generated methods and various wrappers, are also encapsulated in the
    :class:`nebius.aio.request_kwargs.RequestKwargs` class. Use this class to
    automatically infer and validate request parameters.

    :param channel: Channel used to resolve address channels and perform
        synchronous execution when callers use the synchronous helpers.
    :type channel: :class:`nebius.aio.abc.ClientChannelInterface`

    :param service: Fully-qualified service name used to construct the RPC
        path (e.g. ``"nebius.service.v1.MyService"``).
    :type service: `str`

    :param method: RPC method name (bare, without the service prefix),
        for example ``"Get"`` or ``"List"``.
    :type method: `str`

    :param request: The request payload. Typically a protobuf wrapper or a
        domain object that can be serialised by the generated client.

    :param result_pb2_class: Protobuf class used to deserialize the RPC
        response bytes into a message instance.
    :type result_pb2_class: type of specific message subclass of
        ``google.protobuf.Message``

    :param metadata: Optional initial gRPC metadata to attach to the call.
    :type metadata: either :class:`nebius.base.metadata.Metadata`
        or list of ``(str, str)`` tuples.

    :param timeout: Overall timeout (seconds) applied to the request execution
        portion. Or `None` for infinite timeout.
        Default is :data:`DEFAULT_TIMEOUT`.
    :type timeout: optional `float` or `None`

    :param auth_timeout: Timeout budget (seconds) reserved for authorization
        flows plus the request execution. When provided the total authorization
        + request time will not exceed this value.
        Default is :data:`DEFAULT_AUTH_TIMEOUT`.
        Provide `None` for infinite timeout.
    :type auth_timeout: optional `float` or `None`

    :param auth_options: Optional dictionary forwarded to the authenticator
        when performing authorization. See the authenticator documentation for
        provider-specific keys.
    :type auth_options: optional ``dict[str, str]``

    :param credentials: Optional gRPC :class:`CallCredentials` to use for the
        RPC invocation.
    :type credentials: optional :class:`grpc.CallCredentials`

    :param compression: Optional gRPC compression setting for the RPC.
    :type compression: optional :class:`grpc.Compression`

    :param result_wrapper: Optional callable used to post-process the raw
        protobuf response into a higher-level domain object. It is called as
        ``result_wrapper(service_method: str, channel: Channel, pb_obj)``.

    :param grpc_channel_override: Optionally provide an :class:`AddressChannel`
        instance to use instead of resolving one from the main channel. This
        is useful for tests or when the caller already has a concrete
        address-bound channel.
    :type grpc_channel_override: nebius.aio.base.AddressChannel | None

    :param error_wrapper: Optional callable that maps a :class:`RequestStatus`
        into a :class:`RequestError` subclass used by the SDK. When omitted a
        default service-specific wrapper is used.

    :param retries: Number of retry attempts for transient failures. Default is 3.
    :type retries: optional `int` or `None`

    :param per_retry_timeout: Timeout (seconds) applied to each retry attempt
        individually. You can pass `None` for infinite timeout. Default is
        :data:`DEFAULT_PER_RETRY_TIMEOUT`.
    :type per_retry_timeout: optional `float` or `None`

    Example::

        from nebius.sdk import SDK
        from nebius.aio.cli_config import Config
        from nebius.api.nebius.storage.v1 import (
            BucketServiceClient,
            CreateBucketRequest,
        )

        sdk = SDK(config_reader=Config())
        service = BucketServiceClient(sdk)

        # Create a request (typically done by generated client methods)
        request = service.create(CreateBucketRequest(name="my-bucket"))

        # Await the request asynchronously
        response = await request
        print(f"Created bucket: {response}")

        # Or wait synchronously
        response = request.wait()
        print(f"Created bucket: {response}")

        # Get request status
        status = await request.status()
        print(f"Request status: {status.code}")

        # Get request ID
        req_id = await request.request_id()
        print(f"Request ID: {req_id}")

        # Get trace ID
        trace_id = await request.trace_id()
        print(f"Trace ID: {trace_id}")

        # Get initial metadata
        initial_md = await request.initial_metadata()
        print(f"Initial metadata: {dict(initial_md)}")

        # Get trailing metadata
        trailing_md = await request.trailing_metadata()
        print(f"Trailing metadata: {dict(trailing_md)}")

        # Synchronous helpers
        req_id_sync = request.request_id_sync()
        trace_id_sync = request.trace_id_sync()
        initial_md_sync = request.initial_metadata_sync()
        trailing_md_sync = request.trailing_metadata_sync()
    """

    def __init__(
        self,
        channel: Channel,
        service: str,
        method: str,
        request: Req,
        result_pb2_class: type[PMessage],
        metadata: Metadata | Iterable[tuple[str, str]] | None = None,
        timeout: float | None | UnsetType = Unset,
        auth_timeout: float | None | UnsetType = Unset,
        auth_options: dict[str, str] | None = None,
        credentials: CallCredentials | None = None,
        compression: Compression | None = None,
        result_wrapper: Callable[[str, Channel, Any], Res] | None = None,
        grpc_channel_override: AddressChannel | None = None,
        error_wrapper: Callable[[RequestStatus], RequestError] | None = None,
        retries: int | None = 3,
        per_retry_timeout: float | None | UnsetType = Unset,
        # When adding new parameters, don't forget to add them to RequestKwargs as well,
        # if applicable.
    ) -> None:
        """
        Initialize the request with the provided parameters.
        """
        self._channel = channel
        self._input = request
        self._service = service
        self._method = method
        self._auth_options = auth_options if auth_options is not None else {}
        self._result_pb2_class = result_pb2_class
        self._input_metadata = Metadata(metadata)
        self._result_wrapper = result_wrapper
        self._grpc_channel = grpc_channel_override
        self._timeout: float | None = (
            timeout if not isinstance(timeout, UnsetType) else DEFAULT_TIMEOUT
        )
        self._per_retry_timeout: float | None = (
            per_retry_timeout
            if not isinstance(per_retry_timeout, UnsetType)
            else DEFAULT_PER_RETRY_TIMEOUT
        )
        self._auth_timeout: float | None = (
            auth_timeout
            if not isinstance(auth_timeout, UnsetType)
            else DEFAULT_AUTH_TIMEOUT
        )
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
        """Return a short representation including service, method and status."""
        return (
            f"{self.__class__.__name__}({self._service}.{self._method}, "
            f"{self.current_status()})"
        )

    def done(self) -> bool:
        """Return True if the underlying gRPC call has completed."""
        if self._call is None:
            return False
        return self._call.done()

    def cancelled(self) -> bool:
        """Return True if the call was cancelled (locally or remotely)."""
        if self._call is not None:
            return self._call.cancelled()
        return self._cancelled

    def cancel(self) -> bool:
        """Cancel the request; returns True when the request is marked
        cancelled.

        If the underlying gRPC call has already been created, cancellation is
        propagated to that call; otherwise a local cancelled flag is set so
        the call will not be sent when the request is executed.
        """
        if self._call is not None:
            return self._call.cancel()
        else:
            self._cancelled = True
            return self._cancelled

    def input_metadata(self) -> Metadata:
        """Return the metadata that will be sent with the request (mutable).

        This object may be modified by authenticators before the request is
        sent.
        """
        return self._input_metadata

    @property
    def timeout(self) -> float | None:
        """Return the configured overall timeout for the request in seconds.

        ``None`` means no timeout.
        """
        return self._timeout

    @timeout.setter
    def timeout(self, timeout: float | None) -> None:
        if self._call is not None:
            raise RequestIsSentError()
        self._timeout = timeout

    @property
    def credentials(self) -> CallCredentials | None:
        """Return optional gRPC CallCredentials attached to the request."""
        return self._credentials

    @credentials.setter
    def credentials(self, credentials: CallCredentials | None) -> None:
        if self._call is not None:
            raise RequestIsSentError()
        self._credentials = credentials

    @property
    def wait_for_ready(self) -> bool | None:
        """Return the wait_for_ready flag used when starting the RPC call."""
        return self._wait_for_ready

    @wait_for_ready.setter
    def wait_for_ready(self, wait_for_ready: bool | None) -> None:
        if self._call is not None:
            raise RequestIsSentError()
        self._wait_for_ready = wait_for_ready

    @property
    def compression(self) -> Compression | None:
        """Return the configured compression option for the RPC call."""
        return self._compression

    @compression.setter
    def compression(self, compression: Compression | None) -> None:
        if self._call is not None:
            raise RequestIsSentError()
        self._compression = compression

    def _send(self, timeout: float | None) -> None:
        """Prepare and start the underlying gRPC unary-unary call.

        Responsibilities:

        - Validate/serialize the request payload.
        - Populate parent identifiers into the request when absent and the
          channel exposes a parent id.
        - Resolve an :class:`AddressChannel` via :meth:`Channel.get_channel_by_method`
          when no override was provided.
        - Create the gRPC call object and store it on ``self._call``.

        :param timeout: per-attempt timeout to use for the RPC invocation.
        :type timeout: optional `float`
        :raises RequestError: when the request payload cannot be serialized or
            the request has been cancelled.
        """
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
        """Run an awaitable synchronously using the channel's sync runner.

        The channel's synchronous runner is invoked with the request's
        authorization timeout budget (``_auth_timeout``). In case the sync
        runner raises a :class:`TimeoutError` this method converts it into a
        :class:`RequestError` populated with a DEADLINE_EXCEEDED status so
        callers can inspect the failure uniformly.

        :param func: awaitable to execute
        :returns: result of the awaitable
        :raises RequestError: when execution times out or the request fails
        """
        try:
            # Overall timeout should include authorization + request execution
            timeout = self._auth_timeout
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
        """Synchronous convenience wrapper for awaiting the request.

        Equivalent to ``run_sync_with_timeout(self)``.
        """
        return self.run_sync_with_timeout(self)

    def initial_metadata_sync(self) -> Metadata:
        """Synchronously return the initial metadata received from the RPC.

        If initial metadata is not already cached this helper awaits the
        request (via the sync runner) and returns the initial metadata.
        :returns: initial metadata
        :rtype: :class:`nebius.base.metadata.Metadata`
        """
        if self._initial_metadata is not None:
            return self._initial_metadata
        return self.run_sync_with_timeout(self.initial_metadata())

    def trailing_metadata_sync(self) -> Metadata:
        """Synchronously return the trailing metadata received from the RPC.

        If trailing metadata is not already cached this helper awaits the
        request (via the sync runner) and returns the trailing metadata.
        :returns: trailing metadata
        :rtype: :class:`nebius.base.metadata.Metadata`
        """
        if self._trailing_metadata is not None:
            return self._trailing_metadata
        return self.run_sync_with_timeout(self.trailing_metadata())

    def current_status(self) -> RequestStatus | UnfinishedRequestStatus:
        """Return the current request status or an unfinished sentinel.

        When the RPC has not yet started this returns
        :class:`UnfinishedRequestStatus.INITIALIZED`. When the call is in
        progress it returns :class:`UnfinishedRequestStatus.SENT`. When the
        call completed it returns a concrete :class:`RequestStatus`.

        :rtype: either :class:`nebius.aio.request_status.RequestStatus` or
            :class:`nebius.aio.request_status.UnfinishedRequestStatus`
        """
        if self._status is not None:
            return self._status
        if self._call is None:
            return UnfinishedRequestStatus.INITIALIZED
        return UnfinishedRequestStatus.SENT

    async def _get_request_id(self) -> tuple[str, str]:
        """Ensure metadata is received and return the request and trace ids.

        Returns a tuple ``(request_id, trace_id)`` extracted from the initial
        metadata. This coroutine will await the request if metadata hasn't yet
        been received.
        """
        if self._request_id is not None and self._trace_id is not None:
            return (self._request_id, self._trace_id)
        await self.initial_metadata()
        return (self._request_id, self._trace_id)  # type: ignore[return-value] # should be set after receiving md

    async def request_id(self) -> str:
        """Return the request id extracted from initial metadata.
        This coroutine will await the request if metadata hasn't yet
        been received.

        This is a convenience wrapper over :meth:`_get_request_id`.
        """
        ret = await self._get_request_id()
        return ret[0]

    async def trace_id(self) -> str:
        """Return the trace id extracted from initial metadata.
        This coroutine will await the request if metadata hasn't yet
        been received.

        This is a convenience wrapper over :meth:`_get_request_id`.
        """
        ret = await self._get_request_id()
        return ret[1]

    def request_id_sync(self) -> str:
        """Synchronous helper to return the request id.

        If the id is already cached it is returned synchronously. Otherwise the
        request is awaited via the sync runner and the id is returned.
        """
        if self._request_id is not None:
            return self._request_id
        return self.run_sync_with_timeout(self.request_id())

    def trace_id_sync(self) -> str:
        """Synchronous helper to return the trace id.

        If the id is already cached it is returned synchronously. Otherwise the
        request is awaited via the sync runner and the id is returned.
        """
        if self._trace_id is not None:
            return self._trace_id
        return self.run_sync_with_timeout(self.trace_id())

    async def initial_metadata(self) -> Metadata:
        """Return the initial metadata from the RPC, awaiting the request if
        necessary.

        If the request failed but initial metadata was still produced it will
        be returned. Otherwise a :class:`RequestError` is raised.
        """
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
        """Return the trailing metadata from the RPC, awaiting the request if
        necessary.

        If the request failed but trailing metadata was still produced it will
        be returned. Otherwise a :class:`RequestError` is raised.
        """
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
        """Extract request and trace ids from cached initial metadata.

        Raises :class:`RequestError` when initial metadata is not present.
        """
        if self._initial_metadata is None:
            raise RequestError("no initial metadata")
        self._request_id = self._initial_metadata.get_one("x-request-id", "")
        self._trace_id = self._initial_metadata.get_one("x-trace-id", "")

    async def status(self) -> RequestStatus:
        """Return the final request status, awaiting completion if needed.

        When the request fails but a status object is still available it is
        returned. Otherwise a :class:`RequestError` is raised.
        """
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
        """Convert a gRPC AioRpcError into the SDK's RequestError and status.

        This extracts initial/trailing metadata, parses request identifiers and
        attempts to convert the gRPC status into the SDK's structured
        RequestStatus. The resulting status is stored on ``self._status`` and
        a :class:`nebius.aio.service_error.RequestError` is raised.
        """
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
        """Attempt to raise a RequestError from an AioRpcError, swallowing
        any resulting RequestError.

        This helper is used to set status and other metadata that came with
        the AioRpcError without actually raising the RequestError.
        """
        from .service_error import RequestError

        try:
            self._raise_request_error(err)
        except RequestError:
            pass

    async def _retry_loop(self, outer_deadline: float | None = None) -> Res:
        """Core retry loop for the RPC invocation.

        This coroutine executes the RPC, applies per-attempt and overall
        timeouts, and implements retry/backoff rules for retriable errors.
        It returns the RPC result or raises the error that terminated the
        operation.

        :param outer_deadline: optional absolute timestamp (time.time()) that
            caps the total time budget for this retry loop.
        :returns: the deserialized RPC result (or wrapped result via
            ``result_wrapper`` when configured).
        :raises RequestError, AioRpcError, CancelledError: depending on the
            failure mode.
        """
        from .service_error import RequestError, is_retriable_error

        self._start_time = time()
        # Compute this loop's absolute deadline, capped by an outer deadline if provided
        own_deadline = (
            None if self._timeout is None else self._start_time + self._timeout
        )
        if outer_deadline is None:
            deadline = own_deadline
        elif own_deadline is None:
            deadline = outer_deadline
        else:
            deadline = min(own_deadline, outer_deadline)
        attempt = 0
        while not self._cancelled:
            attempt += 1
            timeout = None if deadline is None else deadline - time()

            if self._per_retry_timeout is not None and (
                timeout is None or timeout > self._per_retry_timeout
            ):
                # Clip per-retry timeout by remaining overall deadline if present
                per_attempt = self._per_retry_timeout
                if deadline is not None:
                    remaining = deadline - time()
                    if remaining <= 0:
                        per_attempt = 0
                    else:
                        per_attempt = min(per_attempt, remaining)
                timeout = per_attempt

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

    async def _request_with_authorization_loop(self) -> Res:
        """Wrap request retry loop with an authorization loop.

        The authorization loop will attempt to authenticate and then execute the
        request retry loop. If the result is UNAUTHENTICATED and the authenticator
        allows retry, it will re-authenticate and try again while respecting the
        overall auth timeout.
        """
        # If no provider or authorization explicitly disabled, just run the request
        provider = self._channel.get_authorization_provider()

        auth_type = self._auth_options.get(OPTION_TYPE, None)
        if provider is None or auth_type == Types.DISABLE:
            return await self._retry_loop()

        start = time()
        deadline = None if self._auth_timeout is None else start + self._auth_timeout
        attempt = 0
        auth = provider.authenticator()

        while True:
            attempt += 1
            timeout = None if deadline is None else (deadline - time())
            if timeout is not None and timeout <= 0:
                raise TimeoutError("authorization timed out")
            # Perform authentication: use a gRPC Metadata, then copy back auth header
            # to the internal Metadata used when sending the request
            auth_md = Metadata(self._input_metadata)
            try:
                await wait_for(
                    auth.authenticate(auth_md, timeout, self._auth_options), timeout
                )
            except Exception as e:  # noqa: BLE001
                # If authentication itself failed (e.g., token refresh timeout),
                # retry if authenticator allows and we are within deadline.
                if deadline is not None and deadline <= time():
                    raise
                if auth.can_retry(e, self._auth_options):
                    continue
                raise
            self._input_metadata = auth_md

            # Run the request retry loop; map UNAUTHENTICATED to re-auth attempts
            try:
                return await self._retry_loop(outer_deadline=deadline)
            except Exception as e:  # noqa: BLE001
                # Only retry auth on UNAUTHENTICATED codes
                from .service_error import RequestError as ServiceRequestError

                if not isinstance(e, ServiceRequestError):
                    raise
                try:
                    code = e.status.code
                except Exception:
                    # If code is not available, don't treat it as auth failure
                    raise
                if not (
                    code == StatusCode.UNAUTHENTICATED
                    or getattr(code, "name", None) == "UNAUTHENTICATED"
                ):
                    raise
                if deadline is not None and deadline <= time():
                    raise
                if not auth.can_retry(e, self._auth_options):
                    raise
                # loop continues to re-authenticate and retry

    async def _await_result(self) -> Res:
        """Ensure the request coroutine is scheduled and return its result.

        This helper memoizes the created Future so the underlying request is
        executed only once even if multiple awaiters call it.
        """
        if self._future is None:
            self._future = ensure_future(self._request_with_authorization_loop())
        return await self._future

    def __await__(self) -> Generator[Any, None, Res]:
        """Support awaiting the Request instance.

        The first await schedules the internal request; awaiting a finished
        request raises a RuntimeError to prevent double-execution semantics.
        """
        if self._awaited:
            raise RuntimeError("cannot await the finished coroutine")
        self._awaited = True

        res = yield from self._await_result().__await__()
        return res
