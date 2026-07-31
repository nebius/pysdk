"""Request helper used by generated clients.

The :class:`Request` class contains one RPC invocation. It controls retries,
authorization, metadata extraction, and synchronous calls. A generated client
creates the object. Await the object to perform the RPC. Its methods supply
status metadata, synchronous calls, and configurable retries and timeouts.

Key concepts:

  - Authorization loop: If a provider exists, the request authorizes before
    the RPC. If permitted, it authorizes again after ``UNAUTHENTICATED``.
  - Retry loop: transient errors are retried according to configured retry
    counts and per-retry timeouts.

The request logic is central to SDK call semantics. Make only small changes
that do not affect behavior.
"""

import os
from asyncio import CancelledError, ensure_future, get_running_loop, shield, wait_for
from collections.abc import Awaitable, Callable, Generator, Iterable
from logging import getLogger
from sys import exc_info
from threading import RLock
from time import time
from typing import TYPE_CHECKING, Any, Generic, TypeVar, cast

from google.protobuf.message import Message as ProviderMessage
from grpc import CallCredentials, Compression, StatusCode
from grpc.aio import AioRpcError
from grpc.aio import Metadata as GrpcMetadata
from grpc.aio._call import UnaryUnaryCall  # type: ignore[unused-ignore]

from nebius.aio.abc import ClientChannelInterface as Channel
from nebius.aio.abc import release_address_channel
from nebius.aio.authorization.options import OPTION_TYPE, Types
from nebius.aio.base import AddressChannel
from nebius.aio.idempotency import ensure_key_in_metadata
from nebius.base.error import SDKError
from nebius.base.metadata import Metadata
from nebius.base.protos.direct import Message as DirectMessage
from nebius.base.protos.pb_classes import Message as LegacyMessage
from nebius.base.protos.unset import Unset, UnsetType

from .request_status import RequestStatus, UnfinishedRequestStatus
from .route import Route

if TYPE_CHECKING:
    from nebius.base.protos.registry import Registry

Req = TypeVar("Req")
"""Request type variable. Either a protobuf/message or a serializable payload."""
Res = TypeVar("Res")
"""Response type variable. Either a protobuf/message or a custom wrapper."""
Err = TypeVar("Err")
"""Error type variable. Either a protobuf/message or a custom wrapper."""
T = TypeVar("T")

log = getLogger(__name__)


def _snapshot_request_input(value: T) -> T:
    """Clone a supported message before it crosses to the SDK event loop.

    Direct generated messages and provider protobuf messages expose
    ``CopyFrom``. Legacy SDK wrappers expose their provider protobuf through
    ``__pb2_message__``. Unknown loop-neutral payload types retain their
    historical pass-through behavior.

    :param value: Request value to snapshot.
    :return: Independent message, or ``value`` for an unknown payload type.
    """

    if isinstance(value, LegacyMessage):
        provider_message = value.__pb2_message__
        provider_copy = type(provider_message)()
        provider_copy.CopyFrom(provider_message)
        value_type = cast(Any, type(value))
        return cast(T, value_type(provider_copy))

    if isinstance(value, (DirectMessage, ProviderMessage)):
        copied = cast(Any, type(value))()
        copied_copy_from = cast(Callable[[T], None], copied.CopyFrom)
        copied_copy_from(value)
        return cast(T, copied)
    return value


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
    """Contain an RPC invocation with retries and authorization.

    Generated client methods use :class:`Request`. It controls one RPC:

    - preparing and populating protobuf request objects,
    - attaching metadata and idempotency keys,
    - performing an authorization step when needed, and
    - executing retry logic with per-attempt timeouts.

    Callers typically either ``await`` the request or call :meth:`wait` to run
    it synchronously.

    :class:`nebius.aio.request_kwargs.RequestKwargs` contains parameters that
    apply to all request types. Generated methods and wrappers pass these
    parameters through. Use this class to infer and validate request
    parameters.

    :param channel: Channel used to resolve address channels and perform
        synchronous execution when callers use the synchronous helpers.
    :type channel: :class:`nebius.aio.abc.ClientChannelInterface`

    :param service: Fully-qualified service name used to construct the RPC
        path (e.g. ``"nebius.service.v1.MyService"``).
    :type service: `str`

    :param method: RPC method name (bare, without the service prefix),
        for example ``"Get"`` or ``"List"``.
    :type method: `str`

    :param request: The request payload. Supported mutable protobuf messages
        are copied when the wrapper is created. Unknown custom values retain
        their historical pass-through behavior and must be thread-safe.

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

        sdk = SDK(
            config_reader=Config(),
            user_agent_prefix="example-application/1.0",
        )
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
        result_pb2_class: type[Any],
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
        route: Route | None = None,
        # When adding new parameters, don't forget to add them to RequestKwargs as well,
        # if applicable.
    ) -> None:
        """
        Initialize the request with the provided parameters.
        """
        self._channel = channel
        self._process_id = os.getpid()
        # Generated update methods derive reset-mask metadata before creating
        # this wrapper. Copy supported mutable messages now so that metadata
        # and the payload always describe the same state. Unknown custom
        # payloads retain their historical pass-through behavior.
        self._input = _snapshot_request_input(request)
        self._service = service
        self._method = method
        self._route = route or Route(service=service, method=method)
        self._registry = cast(
            "Registry | None",
            self._route.registry or getattr(type(request), "__REGISTRY__", None),
        )
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
        self._call: UnaryUnaryCall | None = None  # type: ignore[type-arg,unused-ignore]
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
        self._future: Awaitable[Res] | None = None
        self._future_lock = RLock()
        self._native_terminal = False
        # A native attempt can finish before error translation decides whether
        # the logical request will retry. During that phase done() stays false
        # and cancel() may still cancel the request before another call opens.
        self._retry_decision_pending = False
        self._native_attempt_terminal = False
        self._cancel_after_terminal_attempt = False

    def _check_process(self) -> None:
        """Reject a request inherited by a child process before locking."""

        if os.getpid() != self._process_id:
            raise RuntimeError(
                "an SDK request cannot be used after fork; fork before "
                "creating any SDK objects"
            )

    def _release_grpc_channel(self, *, discard: bool = False) -> None:
        """Release and forget the request's current transport lease.

        Clearing the reference before invoking channel code prevents an outer
        authorization retry from reusing a wrapper that has already returned
        to the shared pool. It also ensures a custom release failure cannot
        leave this request claiming a lease whose pool state is unknown.

        :param discard: Whether the transport must be discarded instead of
            returned for reuse.
        """

        grpc_channel, self._grpc_channel = self._grpc_channel, None
        release_address_channel(
            self._channel,
            grpc_channel,
            discard=discard,
        )

    def __repr__(self) -> str:
        """Return a short representation including service, method and status."""
        return (
            f"{self.__class__.__name__}({self._service}.{self._method}, "
            f"{self.current_status()})"
        )

    def done(self) -> bool:
        """Return True if the underlying gRPC call has completed."""
        self._check_process()
        with self._future_lock:
            future = self._future
            done = getattr(future, "done", None)
            terminal = self._native_terminal and not self._retry_decision_pending
            return terminal or (bool(done()) if callable(done) else False)

    def cancelled(self) -> bool:
        """Return True if the call was cancelled (locally or remotely)."""
        self._check_process()
        with self._future_lock:
            future = self._future
            cancelled = getattr(future, "cancelled", None)
            if callable(cancelled) and cancelled():
                return True
            status = self._status
            return self._cancelled or (
                status is not None and status.code is StatusCode.CANCELLED
            )

    def cancel(self) -> bool:
        """Cancel the request; returns True when the request is marked
        cancelled.

        If the gRPC call exists, cancel that call. Otherwise, set a local flag
        to prevent the request from sending the call.
        """
        self._check_process()
        with self._future_lock:
            if self._cancelled or (
                self._native_terminal and not self._retry_decision_pending
            ):
                return False
            if self._native_attempt_terminal:
                # The owner loop has not classified the result as final or
                # retriable yet. Record cancellation without cancelling the
                # wrapper task, which could erase an authoritative success.
                self._cancelled = True
                self._cancel_after_terminal_attempt = True
                return True
            future = self._future
            if future is None:
                self._cancelled = True
                return True
            cancel = getattr(future, "cancel", None)
            cancelled = bool(cancel()) if callable(cancel) else False
            if cancelled:
                self._cancelled = True
            return cancelled

    def input_metadata(self) -> Metadata:
        """Return the metadata that will be sent with the request (mutable).

        Before first submission, callers may modify the returned object. The
        SDK snapshots it when the request is first awaited or synchronously
        waited. After submission this method returns a copy, so external
        mutation cannot race authorization or transport processing on the SDK
        loop.
        """
        self._check_process()
        with self._future_lock:
            if self._future is None:
                return self._input_metadata
            return Metadata(self._input_metadata)

    @property
    def timeout(self) -> float | None:
        """Return the configured overall timeout for the request in seconds.

        ``None`` means no timeout.
        """
        return self._timeout

    @timeout.setter
    def timeout(self, timeout: float | None) -> None:
        self._check_process()
        with self._future_lock:
            if self._future is not None:
                raise RequestIsSentError()
            self._timeout = timeout

    @property
    def credentials(self) -> CallCredentials | None:
        """Return optional gRPC CallCredentials attached to the request."""
        return self._credentials

    @credentials.setter
    def credentials(self, credentials: CallCredentials | None) -> None:
        self._check_process()
        with self._future_lock:
            if self._future is not None:
                raise RequestIsSentError()
            self._credentials = credentials

    @property
    def wait_for_ready(self) -> bool | None:
        """Return the wait_for_ready flag used when starting the RPC call."""
        return self._wait_for_ready

    @wait_for_ready.setter
    def wait_for_ready(self, wait_for_ready: bool | None) -> None:
        self._check_process()
        with self._future_lock:
            if self._future is not None:
                raise RequestIsSentError()
            self._wait_for_ready = wait_for_ready

    @property
    def compression(self) -> Compression | None:
        """Return the configured compression option for the RPC call."""
        return self._compression

    @compression.setter
    def compression(self, compression: Compression | None) -> None:
        self._check_process()
        with self._future_lock:
            if self._future is not None:
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
        self._initial_metadata = None
        self._trailing_metadata = None
        self._status = None
        req = self._input
        from nebius.base.protos.pb_classes import Message as LegacyMessage

        if isinstance(req, LegacyMessage):
            req = req.__pb2_message__  # type: ignore[assignment]
        serializer = getattr(req.__class__, "SerializeToString", None)
        if not callable(serializer):
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
            routed = getattr(self._channel, "get_channel_by_route", None)
            if callable(routed):
                self._grpc_channel = routed(self._route)
            else:
                self._grpc_channel = self._channel.get_channel_by_method(
                    self._service + "." + self._method
                )
        s_name = self._service
        if s_name[0] == ".":
            s_name = s_name[1:]
        owner_loop = getattr(self._grpc_channel, "event_loop", None)
        if owner_loop is not None and owner_loop is not get_running_loop():
            incompatible = self._grpc_channel
            self._grpc_channel = None
            release_address_channel(self._channel, incompatible, discard=True)
            raise RequestError(
                "grpc_channel_override belongs to a different event loop"
            )
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
        add_done_callback = getattr(self._call, "add_done_callback", None)
        if callable(add_done_callback):
            add_done_callback(self._mark_native_attempt_terminal)

    def _mark_native_attempt_terminal(self, _: object) -> None:
        """Publish native attempt completion before its awaiter resumes.

        The SDK loop still has to classify a terminal attempt as success,
        final error, or retriable error. Cancellation during that interval is
        recorded but does not cancel the wrapper task and erase a native
        success.
        """

        with self._future_lock:
            if not self._native_terminal:
                self._native_attempt_terminal = True

    def run_sync_with_timeout(self, func: Awaitable[T]) -> T:
        """Run an awaitable synchronously using the channel's sync runner.

        Call the channel's synchronous runner with ``_auth_timeout``. If the
        runner raises :class:`TimeoutError`, convert it to
        :class:`RequestError` with ``DEADLINE_EXCEEDED``. Callers can then
        inspect all timeout failures in the same way.

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
                registry=self._registry,
            )
            raise RequestError(self._status) from e

    def wait(self) -> Res:
        """Wait for the request synchronously.

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
        metadata. This coroutine awaits the request if the metadata is not
        available.
        """
        if self._request_id is not None and self._trace_id is not None:
            return (self._request_id, self._trace_id)
        await self.initial_metadata()
        return (self._request_id, self._trace_id)  # type: ignore[return-value] # should be set after receiving md

    async def request_id(self) -> str:
        """Return the request ID from the initial metadata.

        This coroutine awaits the request if the metadata is not available.

        This method wraps :meth:`_get_request_id`.
        """
        ret = await self._get_request_id()
        return ret[0]

    async def trace_id(self) -> str:
        """Return the trace ID from the initial metadata.

        This coroutine awaits the request if the metadata is not available.
        This method wraps :meth:`_get_request_id`.
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
        from .request_status import rpc_status_from_call

        status = rpc_status_from_call(err, registry=self._registry)
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
                registry=self._registry,
            )
            raise RequestError(self._status) from None

        self._status = RequestStatusExtended.from_rpc_status(  # type: ignore[unused-ignore]
            status,
            trace_id=self._trace_id,  # type: ignore[arg-type] # should be strings by now
            request_id=self._request_id,  # type: ignore[arg-type] # should be known by now
            registry=self._registry,
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
                    # A successful native response is authoritative even
                    # while status and metadata are still being copied. The
                    # shared lock linearizes this publication with cancel().
                    with self._future_lock:
                        self._native_terminal = True
                        self._native_attempt_terminal = False
                        if self._cancel_after_terminal_attempt:
                            self._cancel_after_terminal_attempt = False
                            self._cancelled = False
                    return await self._complete_authoritative_success(ret)
                except CancelledError as e:
                    self._release_grpc_channel(discard=True)
                    raise e
                except AioRpcError as e:
                    # A native RPC error is authoritative while its SDK error
                    # representation is being built. The retry branch below
                    # reopens cancellation before starting another attempt.
                    raw_code = e.code()
                    raw_code_retriable = raw_code in (
                        StatusCode.DEADLINE_EXCEEDED,
                        StatusCode.RESOURCE_EXHAUSTED,
                        StatusCode.UNAVAILABLE,
                    )
                    could_retry = (
                        (deadline is None or deadline > time())
                        and (
                            raw_code_retriable
                            or is_retriable_error(e, deadline_retriable=True)
                        )
                        and (self._retries is None or self._retries > attempt)
                    )
                    with self._future_lock:
                        self._native_terminal = True
                        self._native_attempt_terminal = False
                        self._retry_decision_pending = could_retry
                        if self._cancel_after_terminal_attempt and not could_retry:
                            self._cancel_after_terminal_attempt = False
                            self._cancelled = False
                    self._raise_request_error(e)
            except Exception as e:
                retry = (
                    (deadline is None or deadline > time())
                    and is_retriable_error(e, deadline_retriable=True)
                    and (self._retries is None or self._retries > attempt)
                )
                with self._future_lock:
                    terminal_attempt = (
                        self._native_terminal or self._native_attempt_terminal
                    )
                    if terminal_attempt:
                        self._native_terminal = True
                        self._native_attempt_terminal = False
                    cancelled_during_decision = (
                        retry
                        and terminal_attempt
                        and self._retry_decision_pending
                        and self._cancelled
                    )
                    self._retry_decision_pending = False
                    if terminal_attempt:
                        self._cancel_after_terminal_attempt = False
                    if terminal_attempt and not retry:
                        self._cancelled = False
                    if retry and terminal_attempt and not cancelled_during_decision:
                        self._native_terminal = False
                if cancelled_during_decision:
                    self._release_grpc_channel(discard=True)
                    raise RequestIsCancelledError() from e
                if retry:
                    # A custom terminal accessor can fail after the native
                    # response was received. Retrying reopens cancellation
                    # until the next native attempt becomes terminal.
                    log.error(
                        f"request attempt {attempt} for {self} failed with {e} "
                        + "but will be retried",
                        exc_info=exc_info(),
                    )
                    continue
                if deadline is not None and deadline <= time():
                    if isinstance(e, RequestError) and e.status.request_id == "":
                        self._release_grpc_channel(discard=True)
                        raise e
                self._release_grpc_channel()
                raise e
        raise RequestIsCancelledError()

    async def _complete_authoritative_success(self, result: Any) -> Res:
        """Copy terminal state without allowing SDK close to erase success.

        The native response is already authoritative when this method starts.
        Runtime shutdown may cancel the parent submission, so final metadata,
        error conversion, wrapping, and transport release run in a shielded
        child task that the parent drains before returning.

        :param result: Native response value.
        :return: Native or wrapped response value.
        """

        async def complete() -> Res:
            if self._call is None:
                raise RequestSentNoCallError()
            code = await self._call.code()
            msg = await self._call.details()
            mdi = await self._call.initial_metadata()
            mdt = await self._call.trailing_metadata()
            error = AioRpcError(code, mdi, mdt, msg, None)  # type: ignore
            self._convert_request_error(error)
            if self._result_wrapper is not None:
                response = self._result_wrapper(
                    self._service + "." + self._method,
                    self._channel,
                    result,
                )
            else:
                response = cast(Res, result)
            self._release_grpc_channel()
            return response

        completion = ensure_future(complete())
        try:
            return await shield(completion)
        except CancelledError:
            return await completion

    async def _request_with_authorization_loop(self) -> Res:
        """Wrap request retry loop with an authorization loop.

        The authorization loop will attempt to authenticate and then execute the
        request retry loop. If the result is UNAUTHENTICATED and the authenticator
        allows retry, it will re-authenticate and try again while respecting the
        overall auth timeout.
        """
        # If no provider or authorization explicitly disabled, just run the request
        runtime_provider = getattr(
            self._channel,
            "_get_runtime_authorization_provider",
            None,
        )
        provider = (
            runtime_provider()
            if callable(runtime_provider)
            else self._channel.get_authorization_provider()
        )

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
                # The failed native call is no longer the request's final
                # outcome: authorization and RPC execution are about to start
                # another attempt. Reopen cancellation before yielding back
                # to the authentication loop.
                with self._future_lock:
                    self._native_terminal = False
                # loop continues to re-authenticate and retry

    async def _await_result(self) -> Res:
        """Ensure the request coroutine is scheduled and return its result.

        This helper memoizes the created Future so the underlying request is
        executed only once even if multiple awaiters call it.
        """
        self._check_process()
        with self._future_lock:
            if self._future is None:
                self._input_metadata = Metadata(self._input_metadata)
                self._auth_options = dict(self._auth_options)
                coroutine = self._request_with_authorization_loop()
                submit = getattr(self._channel, "run_async", None)
                candidate = submit(coroutine) if callable(submit) else coroutine
                # SDK channels return a reusable cross-loop handle. A legacy
                # adapter can return the original one-shot coroutine; schedule
                # that fallback before memoizing it for status/metadata reads.
                submitted = (
                    candidate
                    if callable(getattr(candidate, "done", None))
                    else ensure_future(candidate)
                )
                self._future = submitted
            future = self._future
        try:
            shielded_wait = getattr(future, "_wait_shielded", None)
            if callable(shielded_wait):
                return cast(Res, await shielded_wait())
            return await shield(future)
        except CancelledError:
            # Shield prevents asyncio from cancelling the shared future
            # directly. Route propagation through the request state machine,
            # which rejects cancellation after native terminal completion.
            self.cancel()
            raise

    def __await__(self) -> Generator[Any, None, Res]:
        """Support awaiting the Request instance.

        The first await schedules the internal request; awaiting a finished
        request raises a RuntimeError to prevent double-execution semantics.
        """
        self._check_process()
        with self._future_lock:
            if self._awaited:
                raise RuntimeError("cannot await the finished coroutine")
            self._awaited = True

        res = yield from self._await_result().__await__()
        return res
