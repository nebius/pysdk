"""High-level gRPC channel manager for the Nebius Python SDK."""

import sys
from asyncio import (
    FIRST_COMPLETED,
    AbstractEventLoop,
    CancelledError,
    Event,
    Task,
    create_task,
    gather,
    get_event_loop,
    get_running_loop,
    iscoroutine,
    run_coroutine_threadsafe,
    shield,
    sleep,
    wait,
    wrap_future,
)
from collections.abc import Awaitable, Callable, Coroutine, Generator, Mapping, Sequence
from concurrent.futures import Future as ConcurrentFuture
from concurrent.futures import TimeoutError as ConcurrentTimeoutError
from contextlib import suppress
from inspect import isawaitable
from logging import getLogger
from pathlib import Path
from threading import Lock
from time import monotonic
from typing import Any, TextIO, TypeVar, cast
from weakref import finalize

from google.protobuf.message import Message
from grpc import (
    CallCredentials,
    ChannelConnectivity,
    ChannelCredentials,
    Compression,
    StatusCode,
    ssl_channel_credentials,
)
from grpc.aio import Metadata as GrpcMetadata
from grpc.aio._base_call import UnaryUnaryCall
from grpc.aio._base_channel import (
    StreamStreamMultiCallable,
    StreamUnaryMultiCallable,
    UnaryStreamMultiCallable,
    UnaryUnaryMultiCallable,
)
from grpc.aio._channel import (
    insecure_channel,  # type: ignore[unused-ignore]
    secure_channel,  # type: ignore[unused-ignore]
)
from grpc.aio._interceptor import ClientInterceptor
from grpc.aio._typing import (
    ChannelArgumentType,
    DeserializingFunction,
    SerializingFunction,
)

from nebius.aio._metadata_type import MetadataType
from nebius.aio.abc import GracefulInterface
from nebius.aio.authorization.authorization import Authenticator
from nebius.aio.authorization.authorization import Provider as AuthorizationProvider
from nebius.aio.authorization.token import TokenProvider
from nebius.aio.cli_config import Config as ConfigReader
from nebius.aio.idempotency import IdempotencyKeyInterceptor
from nebius.aio.keepalive import (
    KeepaliveOptions,
    keepalive_channel_options,
    keepalive_config_from_options,
)
from nebius.aio.metrics import (
    METRIC_RESULT_ERROR,
    METRIC_RESULT_SUCCESS,
    AuthMetricsLike,
    MetricsLike,
    bind_auth_metrics,
    metric_duration_seconds,
    metric_start,
    record_config_metric,
)
from nebius.aio.operation_service import OperationServiceTransportStub
from nebius.aio.route import Route
from nebius.aio.service_descriptor import ServiceStub, from_stub_class
from nebius.aio.token import exchangeable, renewable
from nebius.aio.token.static import Bearer as StaticTokenBearer
from nebius.aio.token.static import EnvBearer
from nebius.aio.token.token import Bearer as TokenBearer
from nebius.aio.token.token import Token
from nebius.base.constants import DOMAIN
from nebius.base.error import SDKError
from nebius.base.metadata import Metadata
from nebius.base.methods import service_from_method_name
from nebius.base.options import COMPRESSION, INSECURE, pop_option
from nebius.base.protos.registry import Registry
from nebius.base.resolver import (
    Chain,
    Conventional,
    Resolver,
    TemplateExpander,
    UnknownServiceError,
)
from nebius.base.service_account.service_account import (
    Reader as ServiceAccountReader,
)
from nebius.base.service_account.service_account import (
    TokenRequester as TokenRequestReader,
)
from nebius.base.tls_certificates import get_system_certificates
from nebius.base.version import version

from ._runtime import AsyncRuntime, CrossLoopAwaitable
from ._task_context import bridge_awaitable
from .base import AddressChannel, ChannelBase

logger = getLogger(__name__)

Req = TypeVar("Req", bound=Message)
Res = TypeVar("Res", bound=Message)

T = TypeVar("T")


class LoopError(SDKError):
    """Exception raised when a synchronous helper is used incorrectly with
    an asyncio event loop.

    A synchronous operation raises this error if its asyncio event loop is
    already running in the current thread. :meth:`Channel.run_sync` is one
    example of such an operation.

    The exception subclasses :class:`SDKError` so callers
    catching SDK-related errors will also catch this condition.

    ``LoopError`` does not add any new behaviour beyond the base error; it
    serves only to provide a more specific error type for loop misuse.
    """


class ChannelClosedError(SDKError):
    """Raised when an operation is attempted on a closed :class:`Channel`.

    This indicates that :meth:`Channel.close` (or :meth:`Channel.sync_close`)
    was previously called and the channel no longer accepts requests or
    returns channel objects.
    """


class _CrossLoopUnaryUnaryCall(UnaryUnaryCall[Req, Res]):
    """Provide cross-loop access to one unary gRPC call.

    All direct awaiters share the submitted call. Cancellation by one direct
    awaiter cancels the shared call and affects every waiter. Use
    :func:`asyncio.shield` when one waiter's cancellation must not cancel the
    call.
    """

    def __init__(
        self,
        channel: "Channel",
        method: str,
        request: Req,
        request_serializer: SerializingFunction | None,
        response_deserializer: DeserializingFunction | None,
        timeout: float | None,
        metadata: MetadataType | None,
        credentials: CallCredentials | None,
        wait_for_ready: bool | None,
        compression: Compression | None,
        address: str | None = None,
    ) -> None:
        """Initialize a cross-loop unary call.

        :param channel: SDK channel that owns the call.
        :param method: Fully qualified gRPC method name.
        :param request: Request value to send.
        :param request_serializer: Optional request serializer.
        :param response_deserializer: Optional response deserializer.
        :param timeout: Optional call timeout in seconds.
        :param metadata: Optional call metadata.
        :param credentials: Optional call credentials.
        :param wait_for_ready: Optional gRPC wait-for-ready setting.
        :param compression: Optional gRPC compression setting.
        :param address: Resolved transport address. Use ``None`` to resolve the
            address from ``method``.
        """

        self._channel = channel
        self._method = method
        self._request = request
        self._request_serializer = request_serializer
        self._response_deserializer = response_deserializer
        self._timeout = timeout
        self._metadata = metadata
        self._credentials = credentials
        self._wait_for_ready = wait_for_ready
        self._compression = compression
        self._address = address
        self._started_at = monotonic()
        self._call: UnaryUnaryCall[Req, Res] | None = None
        self._call_ready = Event()
        self._terminal_lock = Lock()
        self._terminal: dict[str, Any] = {}
        self._address_channel: AddressChannel | None = None
        self._released = False
        self._submitted = channel.run_async(self._invoke())

    async def _invoke(self) -> Res:
        """Create and run the native call on the SDK event loop."""

        discard = False
        try:
            if self._address is None:
                self._address_channel = self._channel.get_channel_by_method(
                    self._method
                )
            else:
                self._address_channel = self._channel.get_channel_by_addr(self._address)
            transport = self._address_channel.channel
            call = cast(
                UnaryUnaryCall[Req, Res],
                transport.unary_unary(
                    self._method,
                    self._request_serializer,
                    self._response_deserializer,
                )(
                    self._request,
                    timeout=self.time_remaining(),
                    metadata=self._metadata,  # type: ignore[arg-type]
                    credentials=self._credentials,
                    wait_for_ready=self._wait_for_ready,
                    compression=self._compression,
                ),
            )
            self._call = call
            self._call_ready.set()
            result = await call
            await self._capture_terminal(call)
            return result
        except BaseException:
            discard = True
            failed_call = self._call
            if failed_call is not None:
                with suppress(BaseException):
                    await self._capture_terminal(failed_call)
            raise
        finally:
            self._call_ready.set()
            if not self._released:
                self._channel.release_channel(
                    self._address_channel,
                    discard=discard,
                )
                self._released = True

    async def _capture_terminal(self, call: UnaryUnaryCall[Req, Res]) -> None:
        """Cache terminal metadata and status values.

        :param call: Completed or failed native call.
        """

        names = (
            "initial_metadata",
            "trailing_metadata",
            "code",
            "details",
        )
        values = await gather(
            *(getattr(call, name)() for name in names),
            return_exceptions=True,
        )
        with self._terminal_lock:
            for name, value in zip(names, values):
                if not isinstance(value, BaseException):
                    self._terminal[name] = value

    async def _call_result(self, method: str) -> Any:
        """Return one value from the native call.

        :param method: Name of the native call method to run.
        :return: Result of the named method.
        """

        with self._terminal_lock:
            if method in self._terminal:
                return self._terminal[method]
        await self._call_ready.wait()
        call = self._call
        if call is None:
            await self._submitted
            raise RuntimeError("gRPC call was not created")
        return await getattr(call, method)()

    async def _public_call_result(self, method: str) -> Any:
        """Return one call value to an external event loop.

        :param method: Name of the native call method to run.
        :return: Result of the named method.
        """

        with self._terminal_lock:
            if method in self._terminal:
                return self._terminal[method]
        return await self._channel.run_async(self._call_result(method))

    def __await__(self) -> Generator[Any, None, Res]:
        """Return an iterator that waits for the RPC result."""

        return self._submitted.__await__()

    def cancel(self) -> bool:
        """Request cancellation of the RPC.

        :return: ``True`` if the submission accepted cancellation.
        """

        cancelled = self._submitted.cancel()
        if cancelled and self._call is None:
            with self._terminal_lock:
                self._terminal.update(
                    {
                        "initial_metadata": GrpcMetadata(),
                        "trailing_metadata": GrpcMetadata(),
                        "code": StatusCode.CANCELLED,
                        "details": "Locally cancelled by application!",
                    }
                )
            try:
                self._submitted.event_loop.call_soon_threadsafe(self._call_ready.set)
            except RuntimeError:
                pass
        return cancelled

    def cancelled(self) -> bool:
        """Return whether the RPC was cancelled."""

        return self._submitted.cancelled()

    def done(self) -> bool:
        """Return whether the RPC is complete."""

        return self._submitted.done()

    def time_remaining(self) -> float | None:
        """Return the remaining RPC timeout in seconds."""

        if self._timeout is None:
            return None
        return max(0.0, self._timeout - (monotonic() - self._started_at))

    def add_done_callback(self, callback: Callable[[Any], None]) -> None:
        """Add a function to call when the RPC is complete.

        The callback follows concurrent-future thread rules. It normally runs
        on the SDK completion thread. If the RPC is already complete, it runs
        immediately on the registering thread. It does not run automatically
        on the caller's event loop.

        :param callback: Function that receives this call.
        """

        self._submitted.add_done_callback(lambda _: callback(self))

    async def initial_metadata(self) -> Any:
        """Return the initial RPC metadata."""

        return await self._public_call_result("initial_metadata")

    async def trailing_metadata(self) -> Any:
        """Return the trailing RPC metadata."""

        return await self._public_call_result("trailing_metadata")

    async def code(self) -> Any:
        """Return the final gRPC status code."""

        return await self._public_call_result("code")

    async def details(self) -> Any:
        """Return the final gRPC status details."""

        return await self._public_call_result("details")

    async def wait_for_connection(self) -> None:
        """Wait until the native call has a connection."""

        await self._channel.run_async(self._call_result("wait_for_connection"))


class NebiusUnaryUnaryMultiCallable(UnaryUnaryMultiCallable[Req, Res]):  # type: ignore[unused-ignore,misc]
    """A small callable wrapper that binds RPC calls to a Channel-managed
    address channel.

    Instances act as gRPC :class:`UnaryUnaryMultiCallable` objects. They get
    the transport channel from the SDK :class:`Channel` pool. When the RPC is
    complete, they return or discard the transport channel.
    """

    def __init__(
        self,
        channel: "Channel",
        method: str,
        request_serializer: SerializingFunction | None = None,
        response_deserializer: DeserializingFunction | None = None,
    ) -> None:
        """Create a callable wrapper that returns requests bound to an
        :class:`AddressChannel` from the SDK :class:`Channel`.

        :param channel: The SDK :class:`Channel` instance used to obtain a
            transport channel for the RPC.
        :param method: Full RPC method string (``'/package.service/Method'``).
        :param request_serializer: Optional serializer used by gRPC.
        :param response_deserializer: Optional deserializer used by gRPC.
        """
        super().__init__()
        self._channel = channel
        self._method = method
        self._request_serializer = request_serializer
        self._response_deserializer = response_deserializer

    def __call__(
        self,
        request: Req,
        *,
        timeout: float | None = None,
        metadata: MetadataType | None = None,
        credentials: CallCredentials | None = None,
        wait_for_ready: bool | None = None,
        compression: Compression | None = None,
    ) -> UnaryUnaryCall[Req, Res]:
        """Invoke the underlying unary-unary RPC on an address channel.

        This method resolves the concrete address for ``self._method`` and
        requests an :class:`AddressChannel` from the parent :class:`Channel`.
        A completion callback on the returned
        :class:`grpc.aio.UnaryUnaryCall` returns or discards the address
        channel after the RPC.

        :param request: The protobuf request message to send.
        :param timeout: Optional per-call timeout in seconds.
        :param metadata: Optional gRPC metadata to send with the request.
        :param credentials: Optional per-call call-credentials.
        :param wait_for_ready: Optional gRPC wait_for_ready flag.
        :param compression: Optional gRPC compression setting.
        :return: A :class:`grpc.aio.UnaryUnaryCall` representing the in-flight
            RPC. The caller may await or add callbacks to the returned object.
        """

        return _CrossLoopUnaryUnaryCall(
            self._channel,
            self._method,
            request,
            self._request_serializer,
            self._response_deserializer,
            timeout,
            metadata,
            credentials,
            wait_for_ready,
            compression,
        )


class _FixedAddressChannel:
    """Keep operation calls on one resolved address."""

    def __init__(self, channel: "Channel", address: str) -> None:
        """Initialize a fixed-address channel.

        :param channel: SDK channel that owns the transport pool.
        :param address: Resolved transport address.
        """

        self._channel = channel
        self._address = address

    def unary_unary(
        self,
        method: str,
        request_serializer: SerializingFunction | None = None,
        response_deserializer: DeserializingFunction | None = None,
    ) -> UnaryUnaryMultiCallable[Any, Any]:
        """Return a unary callable for the fixed address.

        :param method: Fully qualified gRPC method name.
        :param request_serializer: Optional request serializer.
        :param response_deserializer: Optional response deserializer.
        :return: Callable that creates a cross-loop unary call.
        """

        channel = self._channel
        address = self._address

        class FixedAddressCallable(UnaryUnaryMultiCallable[Any, Any]):
            """Create cross-loop calls for one method and address."""

            def __call__(
                self,
                request: Any,
                *,
                timeout: float | None = None,
                metadata: MetadataType | None = None,
                credentials: CallCredentials | None = None,
                wait_for_ready: bool | None = None,
                compression: Compression | None = None,
            ) -> UnaryUnaryCall[Any, Any]:
                """Create a unary call.

                :param request: Request value to send.
                :param timeout: Optional call timeout in seconds.
                :param metadata: Optional call metadata.
                :param credentials: Optional call credentials.
                :param wait_for_ready: Optional gRPC wait-for-ready setting.
                :param compression: Optional gRPC compression setting.
                :return: Cross-loop unary call.
                """

                return _CrossLoopUnaryUnaryCall(
                    channel,
                    method,
                    request,
                    request_serializer,
                    response_deserializer,
                    timeout,
                    metadata,
                    credentials,
                    wait_for_ready,
                    compression,
                    address,
                )

        return FixedAddressCallable()


class NoCredentials:
    """Marker type used to explicitly disable authorization.

    Give this value as the :class:`Channel` ``credentials`` parameter to
    disable authorization tokens for outgoing requests.
    """


Credentials = (
    AuthorizationProvider
    | TokenBearer
    | TokenRequestReader
    | NoCredentials
    | Token
    | str
    | None
)


class _RuntimeAuthenticator(Authenticator):
    """Run one authorization authenticator on the SDK event loop."""

    def __init__(self, channel: "Channel", authenticator: Authenticator) -> None:
        """Initialize a runtime-bound authenticator.

        :param channel: SDK channel that owns the event loop.
        :param authenticator: Authorization authenticator to wrap.
        """

        self._channel = channel
        self._authenticator = authenticator

    async def authenticate(
        self,
        metadata: Metadata,
        timeout: float | None = None,
        options: dict[str, str] | None = None,
    ) -> None:
        """Add authorization data to request metadata.

        :param metadata: Metadata to update.
        :param timeout: Optional authentication timeout in seconds.
        :param options: Optional authentication settings.
        """

        await self._channel.run_async(
            self._authenticator.authenticate(metadata, timeout, options)
        )

    def can_retry(
        self,
        err: Exception,
        options: dict[str, str] | None = None,
    ) -> bool:
        """Return whether authentication can be retried.

        :param err: Error that caused the retry decision.
        :param options: Optional authentication settings.
        :return: ``True`` if the authenticator permits a retry.
        """

        return self._channel._run_sdk_callable(
            self._authenticator.can_retry,
            err,
            options,
        )


class _RuntimeAuthorizationProvider(AuthorizationProvider):
    """Run an authorization provider on the SDK event loop."""

    def __init__(self, channel: "Channel", provider: AuthorizationProvider) -> None:
        """Initialize a runtime-bound authorization provider.

        :param channel: SDK channel that owns the event loop.
        :param provider: Authorization provider to wrap.
        """

        self._channel = channel
        self._provider = provider

    def authenticator(self) -> Authenticator:
        """Return an authenticator that uses the SDK event loop."""

        authenticator = self._channel._run_sdk_callable(self._provider.authenticator)
        return _RuntimeAuthenticator(self._channel, authenticator)


def _wrap_awaitable(awaitable: Awaitable[T]) -> Coroutine[Any, Any, T]:
    """Ensure the provided awaitable is a coroutine object.

    gRPC helper functions in this module accept both coroutine objects and
    other awaitable types (for example :class:`asyncio.Future`). This function
    normalizes them into a coroutine so that they can be wrapped in an
    :class:`asyncio.Task` safely.

    :param awaitable: Any awaitable or coroutine-like object.
    :return: A coroutine object ready to be scheduled.
    :raises TypeError: If the argument is not awaitable.
    """

    if iscoroutine(awaitable):
        return awaitable
    if not isawaitable(awaitable):
        raise TypeError(
            "An asyncio.Future, a coroutine or an awaitable is "
            + f"required, {type(awaitable)} given"
        )

    async def wrap() -> T:
        """Adapter coroutine that awaits the supplied awaitable and returns
        its result.

        This small wrapper is used to convert generic awaitable objects into
        a true coroutine so they can be scheduled as an :class:`asyncio.Task`.
        """
        return await awaitable

    return wrap()


def _get_working_loop() -> AbstractEventLoop:
    """Return the loop that a newly created gRPC AsyncIO channel will use."""
    try:
        return get_running_loop()
    except RuntimeError:
        return get_event_loop()


async def _run_awaitable_with_timeout(
    f: Awaitable[T],
    timeout: float | None = None,
) -> T:
    """Run an awaitable with an optional wall-clock timeout.

    The function creates an :class:`asyncio.Task` from the provided awaitable
    and, if a timeout is supplied, a short timer task. It waits for the first
    task to finish. If the timer completes first the awaited task is
    cancelled and a :class:`TimeoutError` is raised. Exceptions raised by the
    awaited task are propagated.

    :param f: The awaitable to run.
    :param timeout: Optional timeout in seconds. If ``None`` the awaitable is
        allowed to run indefinitely.
    :return: The awaited result.
    :raises TimeoutError: If the awaitable did not finish before the timeout.
    """

    task = Task(_wrap_awaitable(f), name=f"Task for {f=}")
    tasks: list[Task[Any]] = list[Task[Any]]([task])
    if timeout is not None:
        timer = Task(sleep(timeout), name=f"Timer for {f=}")
        tasks.append(timer)
    done, pending = await wait(
        tasks,
        return_when=FIRST_COMPLETED,
    )
    for p in pending:
        logger.debug(f"Canceling pending task {p}")
        p.cancel()
    await gather(*pending, return_exceptions=True)
    try:
        if task.exception() is not None:
            if task not in done:
                raise TimeoutError("Awaitable timed out") from task.exception()
            raise task.exception()  # type: ignore
    except CancelledError as e:
        if task not in done:
            raise TimeoutError("Awaitable timed out") from e
        raise e
    return task.result()


def set_user_agent_option(
    user_agent: str, options: ChannelArgumentType | None
) -> ChannelArgumentType:
    """
    Set or override the ``grpc.primary_user_agent`` channel option.
    This helper appends the provided user-agent string to the ``options``
    sequence, which is passed to gRPC when creating channels. If the
    ``grpc.primary_user_agent`` option is already present in ``options``,
    it will be replaced with the new value.

    :param user_agent: The user-agent string to set.
    :type user_agent: str
    :param options: Existing channel options, if any.
    :type options: optional list of ``(str, Any)`` tuples
    :return: The updated channel options including the user-agent.
    :rtype: list of ``(str, Any)`` tuples
    """
    options = list(options or [])
    options.append(("grpc.primary_user_agent", user_agent))
    return options


class Channel(ChannelBase):  # type: ignore[unused-ignore,misc]
    """Manage high-level gRPC channels for the SDK.

    Responsibilities and behavior
    ==============================

    - Resolve service names and create gRPC channels for the resolved addresses.
    - Keep a small pool for each address to reuse connections. See
      ``max_free_channels_per_address``.
    - Attach authorization credentials and manage token providers.
    - Get tokens with :meth:`get_token` or :meth:`get_token_sync`.
    - Return unary-unary RPC channels to the pool after use. See
      :class:`NebiusUnaryUnaryMultiCallable`.
    - Support asynchronous and synchronous use.
    - Use ``async with Channel(...)``, ``close()``, or ``sync_close()`` to
      release resources.

    Important notes
    ---------------

    - By default the channel starts a dedicated daemon event-loop thread and
      a private daemon executor. All SDK asynchronous work uses that loop.
    - Awaitable SDK handles bridge their internal result into any caller loop.
    - A supplied ``event_loop`` must already be running. The caller owns it,
      and closing the channel does not stop or reconfigure it.
    - Initialization connects token bearers, authorization providers, the
      idempotency interceptor, and a resolver.
    - Public methods include ``get_token``, ``get_token_sync``, ``run_sync``,
      ``bg_task``, ``get_channel_by_method``, and ``create_address_channel``.

    Usage example
    =============

    Async usage (recommended)::

        async with Channel(...) as channel:
            # Use the channel or give it to generated service clients.
            pass

    Synchronous usage::

        channel = Channel(...)
        try:
            channel.run_sync(some_coroutine())
        finally:
            channel.sync_close()

    :ivar user_agent: The user-agent string used by channels created by
        this Channel instance.

    :param resolver:
        Optional custom :class:`Resolver` used to resolve service names to concrete
        addresses. If omitted a :class:`Conventional` resolver is used. If
        provided, it will be chained with the built-in resolver so both
        can be consulted.
    :type resolver: optional :class:`Resolver`

    :param substitutions:
        Optional mapping of template substitutions applied to resolved
        addresses. The construct inserts ``{"{domain}": domain}`` and
        then updates it with this mapping. Typical use is to override
        domain placeholders in generated service addresses.
    :type substitutions: optional dict[from, to]

    :param user_agent_prefix:
        Optional string prepended to the default SDK user-agent. The
        final user-agent string follows the pattern
        ``"<user_agent_prefix> nebius-python-sdk/<version> (python/X.Y.Z)"``.
        Recommended format:
        ``"my-app/1.0 (dependency-to-track/version; other-dependency)"``.
    :type user_agent_prefix: optional str

    :param domain:
        Optional domain for service addresses. If absent, the constructor
        calls ``config_reader.endpoint()``. If that has no value, it uses
        the package ``DOMAIN`` constant.
    :type domain: optional str

    :param options:
        Global channel options passed to gRPC when creating address
        channels. This should follow the ``ChannelArgumentType``
        shape (sequence of key/value tuples).
    :type options: optional list of tuple[str, Any]

    :param interceptors:
        Global list of gRPC :class:`ClientInterceptor`
        instances that will be applied to all address channels. An
        idempotency-key interceptor is added by default; pass a list to
        extend or override additional behavior.
    :type interceptors: optional list of :class:`ClientInterceptor`

    :param address_options:
        Optional mapping from a resolved address to per-address channel
        options. Each value must follow the ``ChannelArgumentType``
        shape (sequence of key/value tuples). If omitted
        an empty mapping is used.
    :type address_options: optional mapping address -> list of ``tuple[str, Any]``

    :param address_interceptors:
        Optional mapping from a resolved address to a sequence of
        per-address interceptors. Per-address interceptors are invoked
        in addition to the global interceptors.
    :type address_interceptors: optional mapping address ->
        Sequence[ClientInterceptor]

    :param credentials:
        Credentials can be provided in several forms:

        - ``None`` (default): attempts to read credentials from
            ``credentials_file_name``, then from provided service account
            fields, then from ``config_reader.get_credentials(...)``, and
            finally falls back to an environment-backed bearer
            (:class:`nebius.aio.token.static.EnvBearer`).
        - ``str`` or :class:`Token`: treated as a
            static token and wrapped with a static bearer.
        - :class:`TokenBearer` to use an existing token bearer as-is.
        - :class:`TokenRequester` to exchange tokens on demand.
        - :class:`AuthorizationProvider`: an explicit authorization provider
            (used rarely by advanced users).
        - :class:`NoCredentials`: disables authorization entirely.

        Unsupported types raise :class:`SDKError`.
    :type credentials: token in form of string or :class:`Token`, or classes
        :class:`TokenBearer`, :class:`TokenRequester`,
        :class:`AuthorizationProvider`, :class:`NoCredentials`

    :param service_account_id:
        Service account ID used when a private key file is supplied
        directly (alternate to using ``credentials_file_name``). See the
        README for examples. If ``credentials`` is provided explicitly
        this parameter is ignored.
    :type service_account_id: optional str

    :param service_account_public_key_id:
        Public key ID corresponding to the private key file used for
        service-account authentication, as described in the README. If
        ``credentials`` is provided explicitly this parameter is ignored.
    :type service_account_public_key_id: optional str

    :param service_account_private_key_file_name:
        Path to a PEM private key file. When provided with the key ID and service
        account ID fields above, the constructor wraps it in a service-account
        reader.
    :type service_account_private_key_file_name: optional str or :class:`Path`

    :param credentials_file_name:
        Path to a credentials JSON file containing service-account
        information. If supplied this takes precedence over other implicit
        credential discovery (unless ``credentials`` is explicitly
        provided).
    :type credentials_file_name: optional str or :class:`Path`

    :param config_reader:
        Optional :class:`nebius.aio.cli_config.Config` instance used to
        populate defaults like domain, default parent ID, and to obtain
        credentials via the CLI-style configuration.
    :type config_reader: optional :class:`ConfigReader`

    :param keepalive:
        Optional SDK gRPC keepalive configuration. By default the channel uses
        defaults compatible with the Nebius SDK for Go. It reads
        ``NEBIUS_GRPC_KEEPALIVE_*`` environment variables. Set ``False`` to
        disable SDK keepalive, or give
        :class:`nebius.aio.keepalive.KeepaliveOptions` / a mapping with
        ``time_ms``, ``timeout_ms`` and ``permit_without_stream`` overrides.
        Explicit keepalive options ignore the environment variables. Channel
        ``options`` and ``address_options`` apply later and can replace
        individual keepalive arguments.
    :type keepalive: optional :class:`KeepaliveOptions`, mapping or bool

    :param metrics:
        Optional callback object or mapping that receives both config-reader
        and authorization metrics. Callback names can use Python snake_case,
        such as ``token_acquire`` and ``credentials_resolve``. camelCase names
        support compatibility with the TypeScript SDK.
    :type metrics: optional object or mapping

    :param auth_metrics:
        Optional callback object or mapping that receives auth-only metrics.
        This is ignored when ``metrics`` is also provided because full metrics
        are used for auth callbacks too.
    :type auth_metrics: optional object or mapping

    :param tls_credentials:
        Optional gRPC channel TLS credentials (:class:`ChannelCredentials`).
        If omitted the constructor will load system root certificates via
        :func:`nebius.base.tls_certificates.get_system_certificates` and
        create an SSL channel credentials object.
    :type tls_credentials: optional :class:`ChannelCredentials`

    :param event_loop:
        Optional already-running asyncio event loop used for all SDK work.
        The caller retains ownership: :meth:`close` does not stop the loop or
        replace its default executor. If omitted, the Channel eagerly starts
        and owns a dedicated daemon loop thread.
    :type event_loop: optional :class:`AbstractEventLoop`

    :param executor_max_workers:
        Number of daemon workers in the private default executor attached to
        an SDK-owned loop. Defaults to 2. This setting is ignored when
        ``event_loop`` is supplied because the caller owns that loop and its
        executor configuration.
    :type executor_max_workers: int

    :param max_free_channels_per_address:
        Number of free underlying gRPC channels to keep in the pool per
        resolved address. Defaults to 2. Lower values reduce resource
        usage but increase connection churn; larger values raise resource
        consumption.
    :type max_free_channels_per_address: optional int

    :param parent_id:
        Optional parent ID which will be automatically applied to many
        requests when left empty by the caller. If not provided and a
        ``config_reader`` is supplied the constructor will attempt to use
        ``config_reader.parent_id``. An explicit empty string is treated
        as an error.
    :type parent_id: optional str

    :param federation_invitation_writer:
        Optional file-like writer passed to the config reader to display
        the URL for federation authentication during interactive credential
        acquisition.
    :type federation_invitation_writer: optional :class:`TextIO`

    :param federation_invitation_no_browser_open:
        When using the config reader, set to ``True`` to avoid opening a web
        browser during interactive federation flows. Defaults to ``False``.
    :type federation_invitation_no_browser_open: optional bool
    """

    def __init__(
        self,
        *,
        resolver: Resolver | None = None,
        substitutions: dict[str, str] | None = None,
        user_agent_prefix: str | None = None,
        domain: str | None = None,
        options: ChannelArgumentType | None = None,
        interceptors: Sequence[ClientInterceptor] | None = None,
        address_options: dict[str, ChannelArgumentType] | None = None,
        address_interceptors: dict[str, Sequence[ClientInterceptor]] | None = None,
        credentials: Credentials = None,
        service_account_id: str | None = None,
        service_account_public_key_id: str | None = None,
        service_account_private_key_file_name: str | Path | None = None,
        credentials_file_name: str | Path | None = None,
        config_reader: ConfigReader | None = None,
        keepalive: KeepaliveOptions | Mapping[str, object] | bool | None = None,
        metrics: MetricsLike = None,
        auth_metrics: AuthMetricsLike = None,
        tls_credentials: ChannelCredentials | None = None,
        event_loop: AbstractEventLoop | None = None,
        executor_max_workers: int = 2,
        max_free_channels_per_address: int = 2,
        parent_id: str | None = None,
        federation_invitation_writer: TextIO | None = None,
        federation_invitation_no_browser_open: bool = False,
    ) -> None:
        """Construct a new :class:`Channel`.

        The constructor connects gRPC channel management, credential
        providers, resolvers, TLS configuration, and interceptors.

        The channel resolves logical service names to transport addresses. It
        creates and pools gRPC channels. It also supplies synchronous and
        asynchronous methods.

        :raises SDKError:
            Raised for unsupported credential types or if ``parent_id`` is an
            explicitly empty string.

        Notes
        -----
        - The constructor performs several discovery steps for credentials in
          the following precedence order when ``credentials`` is ``None``:
          1. ``credentials_file_name`` reader
          2. service-account PEM reader (when id/key args are provided)
          3. ``config_reader.get_credentials(...)``
          4. environment-backed bearer (:class:`EnvBearer`)

        - The constructor wraps token readers in exchangeable and renewable
          bearers. These bearers refresh tokens in the background.
        - The channel adds each bearer to its shutdown set. :meth:`close`
          stops their background tasks.

        Examples
        --------
        Typical, minimal construction that reads token from environment:

        >>> channel = Channel()

        Using explicit static token:

        >>> channel = Channel(credentials="MY_TOKEN")

        Creating channel from CLI config and a custom resolver:

        >>> from nebius.aio.cli_config import Config
        >>> channel = Channel(config_reader=Config(), resolver=my_resolver)

        """

        self._metrics = metrics
        self._auth_metrics = metrics if metrics is not None else auth_metrics
        self._runtime = AsyncRuntime(event_loop, executor_max_workers)
        self._event_loop = self._runtime.event_loop
        self._runtime_finalizer = finalize(self, self._runtime.shutdown_async)
        self._close_submit_lock = Lock()
        self._close_handle: CrossLoopAwaitable[None] | None = None
        self._closed = False
        if metrics is not None and auth_metrics is not None:
            logger.warning(
                "Both metrics and auth_metrics provided; using metrics for "
                "auth callbacks."
            )
        self._keepalive_config = keepalive_config_from_options(keepalive)
        if config_reader is not None:
            self._runtime.call_with_context(
                self._configure_metrics_on_config_reader,
                config_reader,
            )

        if domain is None:
            if config_reader is not None:
                domain = self._runtime.call_with_context(config_reader.endpoint)

            if domain is None or domain == "":
                domain = DOMAIN

        substitutions_full = dict[str, str]()
        substitutions_full["{domain}"] = domain
        if substitutions is not None:
            substitutions_full.update(substitutions)
        self._route_substitutions = substitutions_full

        self._max_free_channels_per_address = max_free_channels_per_address

        self._gracefuls = set[GracefulInterface]()
        self._tasks = set[Any]()
        self._tasks_lock = Lock()

        self._resolver: Resolver = Conventional()
        self._route_custom_resolver: Resolver | None = None
        if resolver is not None:
            self._route_custom_resolver = TemplateExpander(
                substitutions_full,
                resolver,
            )
            self._resolver = Chain(resolver, self._resolver)
        self._resolver = TemplateExpander(substitutions_full, self._resolver)
        if tls_credentials is None:
            root_ca = get_system_certificates()
            with open(root_ca, "rb") as f:
                trusted_certs = f.read()
            tls_credentials = ssl_channel_credentials(root_certificates=trusted_certs)
        self._tls_credentials = tls_credentials

        self._free_channels = dict[str, list[AddressChannel]]()
        self._leased_channels = dict[int, AddressChannel]()
        self._channel_pool_lock = Lock()
        self._close_completion: ConcurrentFuture[None] | None = None
        self._close_task: Task[None] | None = None
        self._methods = dict[str, str]()
        self._routes = dict[tuple[int, str, str, str], str]()
        self.user_agent = "nebius-python-sdk/" + version
        self.user_agent += f" (python/{sys.version_info.major}.{sys.version_info.minor}"
        self.user_agent += f".{sys.version_info.micro})"

        if user_agent_prefix is not None:
            self.user_agent = f"{user_agent_prefix} {self.user_agent}"

        if interceptors is None:
            interceptors = []
        self._global_options = options or []
        self._global_interceptors: list[ClientInterceptor] = [
            IdempotencyKeyInterceptor()
        ]
        self._global_interceptors.extend(interceptors)

        if address_options is None:
            address_options = dict[str, ChannelArgumentType]()
        if address_interceptors is None:
            address_interceptors = dict[str, Sequence[ClientInterceptor]]()
        self._address_options = address_options
        self._address_interceptors = address_interceptors

        self._global_interceptors_inner: list[ClientInterceptor] = []

        self._parent_id = parent_id
        if self._parent_id is None and config_reader is not None:
            from .cli_config import NoParentIdError

            with suppress(NoParentIdError):
                self._parent_id = self._runtime.call_with_context(
                    lambda: config_reader.parent_id
                )
        if self._parent_id == "":
            raise SDKError("Parent id is empty")

        self._token_bearer: TokenBearer | None = None
        self._authorization_provider: AuthorizationProvider | None = None
        if credentials is None:
            if credentials_file_name is not None:
                from nebius.base.service_account.credentials_file import (
                    Reader as CredentialsFileReader,
                )

                credentials = CredentialsFileReader(credentials_file_name)
            elif (
                service_account_id is not None
                and service_account_private_key_file_name is not None
                and service_account_public_key_id is not None
            ):
                from nebius.base.service_account.pk_file import Reader as PKFileReader

                credentials = PKFileReader(
                    service_account_private_key_file_name,
                    service_account_public_key_id,
                    service_account_id,
                )
            elif config_reader is not None:
                metrics_aware = self._is_config_metrics_aware_config_reader(
                    config_reader
                )
                start = metric_start()
                try:
                    credentials = self._runtime.call_with_context(
                        config_reader.get_credentials,
                        self,
                        writer=federation_invitation_writer,
                        no_browser_open=federation_invitation_no_browser_open,
                    )
                except Exception:
                    if not metrics_aware:
                        self._runtime.call_with_context(
                            record_config_metric,
                            self._metrics,
                            "credentials_resolve",
                            "config-reader",
                            METRIC_RESULT_ERROR,
                            metric_duration_seconds(start),
                        )
                    raise
                if not metrics_aware:
                    self._runtime.call_with_context(
                        record_config_metric,
                        self._metrics,
                        "credentials_resolve",
                        "config-reader",
                        METRIC_RESULT_SUCCESS,
                        metric_duration_seconds(start),
                    )
            else:
                credentials = EnvBearer()
        if isinstance(credentials, (str, Token)):
            credentials = StaticTokenBearer(credentials)
        if isinstance(credentials, ServiceAccountReader):
            from nebius.aio.token.service_account import ServiceAccountBearer

            credentials = ServiceAccountBearer(
                credentials,
                self,
                metrics=self._auth_metrics,
            )
        if isinstance(credentials, TokenRequestReader):
            exchange = exchangeable.Bearer(
                credentials, self, metrics=self._auth_metrics
            )
            cache = renewable.Bearer(exchange, metrics=self._auth_metrics)
            credentials = cache
        if isinstance(credentials, TokenBearer):
            credentials = cast(
                TokenBearer,
                bind_auth_metrics(credentials, self._auth_metrics),
            )
            self._gracefuls.add(credentials)
            self._token_bearer = credentials
            credentials = TokenProvider(credentials)
        if isinstance(credentials, AuthorizationProvider):
            self._authorization_provider = credentials
        elif not isinstance(credentials, NoCredentials):  # type: ignore[unused-ignore]
            raise SDKError(f"credentials type is not supported: {type(credentials)}")

    def _configure_metrics_on_config_reader(self, config_reader: ConfigReader) -> None:
        reader = cast(Any, config_reader)
        if self._metrics is not None and callable(getattr(reader, "set_metrics", None)):
            reader.set_metrics(self._metrics)
            return
        if self._auth_metrics is not None and callable(
            getattr(reader, "set_auth_metrics", None)
        ):
            reader.set_auth_metrics(self._auth_metrics)

    def _is_config_metrics_aware_config_reader(
        self, config_reader: ConfigReader
    ) -> bool:
        return self._metrics is not None and callable(
            getattr(config_reader, "set_metrics", None)
        )

    def get_authorization_provider(self) -> AuthorizationProvider | None:
        """Return the configured :class:`AuthorizationProvider`.

        :return: The authorization provider instance if any authorization
            mechanism was configured; otherwise ``None``.
        :rtype: :class:`AuthorizationProvider` or None
        """
        provider = self._authorization_provider
        return provider

    def _get_runtime_authorization_provider(
        self,
    ) -> AuthorizationProvider | None:
        """Return a private provider that uses the SDK event loop."""

        provider = self._authorization_provider
        if provider is None:
            return None
        return _RuntimeAuthorizationProvider(self, provider)

    async def get_token(
        self,
        timeout: float | None,
        options: dict[str, str] | None = None,
    ) -> Token:
        """Asynchronously fetch an authorization :class:`Token`.

        This helper delegates to the configured token bearer and performs any
        necessary refresh or exchange logic implemented by the bearer, if any was
        configured. If no bearer was configured, the method raises
        :class:`SDKError`.

        :param timeout: Maximum time in seconds to wait for a token. If
            ``None`` the operation may block indefinitely according to the
            bearer semantics.
        :type timeout: optional float
        :param options: Optional mapping of string options passed to the
            underlying token receiver.
        :type options: optional ``dict[str, str]``
        :return: A :class:`Token` instance containing the access token.
        :rtype: :class:`Token`
        :raises SDKError: If no token bearer was configured on the channel.
        """

        return await self.run_async(self._get_token_internal(timeout, options))

    async def _get_token_internal(
        self,
        timeout: float | None,
        options: dict[str, str] | None = None,
    ) -> Token:
        """Get a token on the SDK event loop.

        :param timeout: Maximum wait time in seconds.
        :param options: Optional token receiver settings.
        :return: Authorization token.
        :raises SDKError: If the channel has no token bearer.
        """

        if self._token_bearer is None:
            raise SDKError("Token bearer is not set")
        receiver = self._token_bearer.receiver()
        return await receiver.fetch(
            timeout=timeout,
            options=options,
        )

    def get_token_sync(
        self,
        timeout: float | None,
        options: dict[str, str] | None = None,
    ) -> Token:
        """Get an authorization :class:`Token` synchronously.

        This method runs :meth:`get_token` on the channel event loop. It
        blocks the calling thread until a token is available or time expires.

        A small grace period is added to the supplied timeout to allow the
        internal token bearer shutdown logic to complete during immediate
        handoff.

        :param timeout: Maximum time in seconds to wait for a token; may be
            ``None`` to wait indefinitely.
        :type timeout: optional float
        :param options: Optional mapping of string options passed to the
            underlying token receiver.
        :type options: optional ``dict[str, str]``
        :return: A :class:`Token` instance.
        :rtype: :class:`Token`
        :raises TimeoutError: If the token could not be obtained within the
            supplied timeout.
        """

        timeout_sync = timeout
        if timeout_sync is not None:
            timeout_sync += 0.2  # 200 ms for graceful shutdown
        return self.run_sync(
            self.get_token(timeout, options),
            timeout_sync,
        )

    def parent_id(self) -> str | None:
        """Return the channel-wide default parent ID used for certain requests.

        Some SDK methods automatically populate a ``parent_id`` field when
        missing using this channel-level default. The value may be ``None`` if not
        configured.

        :return: The configured parent ID or ``None``.
        :rtype: str | None
        """

        return self._parent_id

    def run_async(self, awaitable: Awaitable[T]) -> CrossLoopAwaitable[T]:
        """Submit SDK work to the channel's event loop.

        The returned awaitable is backed by a thread-safe concurrent future,
        so callers can await it from the SDK loop or from an external event
        loop.

        :param awaitable: Work to run on the SDK event loop.
        :return: Cross-loop awaitable for the result.
        :raises ChannelClosedError: If channel close has started.
        """

        with self._channel_pool_lock:
            if self._closed:
                close = getattr(awaitable, "close", None)
                if callable(close):
                    close()
                raise ChannelClosedError("Channel is closed")
            return self._runtime.submit(awaitable)

    def _run_sdk_callable(
        self,
        callable_: Callable[..., T],
        *args: Any,
    ) -> T:
        """Call a function on the SDK event loop.

        :param callable\\_: Function to call.
        :param args: Positional arguments for ``callable_``.
        :return: Result of ``callable_``.
        """

        if self._runtime.in_event_loop():
            return callable_(*args)

        async def call() -> T:
            """Call the function in an SDK task."""

            return callable_(*args)

        return self._runtime.run_sync(call())

    def bg_task(self, coro: Awaitable[T]) -> CrossLoopAwaitable[None]:
        """Run an awaitable in the background.

        The channel tracks the returned awaitable and cancels it during
        :meth:`close`. The method logs exceptions other than cancellation.

        :param coro: Work to run in the background.
        :return: Cross-loop awaitable that completes after the background work.
        """

        async def wrapper() -> None:
            """Run background work and log its exception."""

            try:
                await bridge_awaitable(coro)
            except CancelledError:
                pass
            except Exception as e:
                logger.error("Unhandled exception in Channel.bg_task", exc_info=e)

        ret = self.run_async(wrapper())
        with self._tasks_lock:
            self._tasks.add(ret)
        ret.add_done_callback(self._discard_background_task)
        return ret

    def _discard_background_task(self, task: CrossLoopAwaitable[Any]) -> None:
        """Remove completed background work from channel tracking.

        :param task: Completed background submission.
        """

        with self._tasks_lock:
            self._tasks.discard(task)

    def run_sync(self, awaitable: Awaitable[T], timeout: float | None = None) -> T:
        """Run an awaitable to completion on the channel's event loop.

        This method blocks the calling thread. It rejects calls from the SDK
        event loop. When the SDK owns its loop, it also rejects calls from any
        other running event loop. When the caller supplies the SDK loop, the
        method permits a call from a different running loop and blocks that
        loop until the result is ready.

        :param awaitable: The awaitable to run to completion.
        :param timeout: Optional maximum wait time in seconds.
        :return: The awaitable's result.
        :raises LoopError: If the caller runs on the SDK loop, or if the SDK
            owns its loop and the caller runs in any asynchronous context.
        :raises TimeoutError: If the time limit expires.
        """

        try:
            current_loop = get_running_loop()
        except RuntimeError:
            current_loop = None
        if current_loop is not None:
            if current_loop is self._event_loop:
                close = getattr(awaitable, "close", None)
                if callable(close):
                    close()
                raise LoopError(
                    "Provided loop is equal to current thread's "
                    "loop. Either use async/await or provide "
                    "another loop at the SDK initialization."
                )
            if self._runtime.owned:
                close = getattr(awaitable, "close", None)
                if callable(close):
                    close()
                raise LoopError(
                    "Synchronous call inside async context. Either use "
                    "async/await or provide a safe and separate loop "
                    "to run at the SDK initialization."
                )

        return self._runtime.run_sync(awaitable, timeout)

    def sync_close(self, timeout: float | None = None) -> None:
        """Synchronously close the channel and wait for graceful shutdown.

        This method calls :meth:`close` and blocks until shutdown is complete
        or time expires.

        :param timeout: Optional timeout in seconds for the shutdown.
        :type timeout: optional float
        :raises TimeoutError: If the shutdown did not complete within the
            supplied timeout.
        """

        if self._runtime.in_event_loop():
            raise LoopError(
                "Cannot synchronously close the SDK from its event loop; "
                "await close() instead."
            )
        try:
            current_loop = get_running_loop()
        except RuntimeError:
            current_loop = None
        if current_loop is not None and self._runtime.owned:
            raise LoopError(
                "Cannot synchronously close the SDK from an async context; "
                "await close() instead."
            )

        deadline = None if timeout is None else monotonic() + timeout

        def remaining() -> float | None:
            """Return the time that remains for shutdown."""

            if deadline is None:
                return None
            return max(0.0, deadline - monotonic())

        closing = self._get_close_handle(None)
        try:
            closing.result(remaining())
        except ConcurrentTimeoutError:
            closing.add_done_callback(lambda _: self._runtime.shutdown_async())
            raise TimeoutError("SDK shutdown timed out") from None
        except BaseException:
            shutdown = self._runtime.shutdown_async()
            shutdown.result(remaining())
            raise

        shutdown = self._runtime.shutdown_async()
        try:
            shutdown.result(remaining())
        except ConcurrentTimeoutError:
            raise TimeoutError("SDK shutdown timed out") from None

    async def close(self, grace: float | None = None) -> None:
        """Gracefully close the channel and all associated background work.

        The channel stops supplying address channels. It closes pooled gRPC
        channels and registered ``GracefulInterface`` objects, such as token
        bearers. It cancels tasks from :meth:`bg_task` and logs shutdown
        exceptions.

        :param grace: Optional per-transport grace period passed to underlying
            channel close methods.
        :type grace: optional float
        """

        current_submission = self._runtime.protect_current_submission()
        completion = self._close_completion
        if completion is not None and completion.done():
            await shield(wrap_future(completion))
            if current_submission is None:
                await shield(self._runtime.shutdown_async())
            else:
                self._shutdown_after_internal_caller(current_submission)
                self._runtime.mark_current_submission_close_returning()
            return
        closing = self._get_close_handle(grace)
        try:
            await shield(closing)
        finally:
            if current_submission is None and closing.done():
                await shield(self._runtime.shutdown_async())
            elif current_submission is not None:
                self._shutdown_after_internal_caller(
                    current_submission,
                    closing,
                )
                self._runtime.mark_current_submission_close_returning()
            else:
                closing.add_done_callback(lambda _: self._runtime.shutdown_async())

    def _shutdown_after_internal_caller(
        self,
        current_submission: CrossLoopAwaitable[Any] | None,
        closing: CrossLoopAwaitable[Any] | None = None,
    ) -> None:
        """Start shutdown after an internal close caller can return.

        :param current_submission: Internal submission that called close.
        :param closing: Optional channel cleanup submission.
        """

        if current_submission is None:
            self._runtime.shutdown_async()
            return

        if closing is None or closing.done():
            self._runtime.shutdown_async()
        else:
            closing.add_done_callback(lambda _: self._runtime.shutdown_async())

    def _get_close_handle(
        self,
        grace: float | None,
    ) -> CrossLoopAwaitable[None]:
        """Return the single channel cleanup submission.

        :param grace: Optional transport close period in seconds.
        :return: Cross-loop awaitable for channel cleanup.
        """

        with self._close_submit_lock:
            closing = self._close_handle
            if closing is None:
                closing = self._runtime.submit(
                    self._close_internal(grace),
                    track=False,
                )
                self._close_handle = closing
            return closing

    async def _close_internal(self, grace: float | None = None) -> None:
        """Close SDK resources without stopping the runtime.

        :param grace: Optional transport close period in seconds.
        """

        with self._channel_pool_lock:
            completion = self._close_completion
            if completion is None:
                completion = ConcurrentFuture[None]()
                self._close_completion = completion
                self._closed = True
                channels = {
                    id(chan): chan
                    for chans in self._free_channels.values()
                    for chan in chans
                }
                channels.update(self._leased_channels)
                self._free_channels.clear()
                gracefuls = list(self._gracefuls)
                with self._tasks_lock:
                    tasks = list(self._tasks)
                run_cleanup = True
            else:
                run_cleanup = False
        if not run_cleanup:
            await shield(wrap_future(completion))
            return

        async def cleanup() -> None:
            """Cancel SDK work and close all channel resources."""

            try:
                self._runtime.begin_close()
                await self._runtime.cancel_submissions()
                awaits = list[Coroutine[Any, Any, Any]]()
                for chan in channels.values():
                    awaits.append(self._close_address_channel(chan, grace))
                for graceful in gracefuls:
                    awaits.append(graceful.close(grace))
                for task in tasks:
                    task.cancel()
                rets = await gather(*awaits, *tasks, return_exceptions=True)
                for ret in rets:
                    if isinstance(ret, BaseException) and not isinstance(
                        ret,
                        CancelledError,
                    ):
                        logger.error(
                            f"Error while graceful shutdown: {ret}",
                            exc_info=ret,
                        )
            except BaseException as error:
                completion.set_exception(error)
            else:
                completion.set_result(None)

        self._close_task = create_task(cleanup(), name="Channel.close cleanup")
        await shield(wrap_future(completion))

    def get_corresponding_operation_service(
        self,
        service_stub_class: type[ServiceStub],
    ) -> OperationServiceTransportStub:
        """Return an operations service stub for the same address as a
        generated service stub.

        Long-running operations are associated with their source service. This
        method resolves the address for the generated stub class. It returns
        an ``OperationServiceStub`` on the transport channel for that
        address.

        :param service_stub_class: Generated gRPC service stub class (the SDK service
            descriptor type).
        :return: An operations service stub bound to the same backend used by
            the provided service.
        :rtype: ``OperationServiceStub``
        """

        addr = self.get_addr_from_stub(service_stub_class)
        registry = self._registry_for_service(service_stub_class)
        return OperationServiceTransportStub(
            cast(Any, _FixedAddressChannel(self, addr)),
            registry,
        )

    def get_corresponding_operation_service_alpha(
        self,
        service_stub_class: type[ServiceStub],
    ) -> OperationServiceTransportStub:
        """Compatibility helper returning the alpha-version operations
        service stub for the same address as a generated service stub.

        See :meth:`get_corresponding_operation_service` for details. This
        method returns the older alpha operations stub for callers that need
        to interoperate with legacy server implementations.
        """

        addr = self.get_addr_from_stub(service_stub_class)
        registry = self._registry_for_service(service_stub_class)
        return OperationServiceTransportStub(
            cast(Any, _FixedAddressChannel(self, addr)),
            registry,
            alpha=True,
        )

    @staticmethod
    def _registry_for_service(
        service_stub_class: type[ServiceStub],
    ) -> Registry:
        registry: Registry | None = getattr(service_stub_class, "__registry__", None)
        if registry is not None:
            return registry
        try:
            from nebius.api._registry import REGISTRY
        except ImportError as error:
            raise SDKError("service stub has no direct-message registry") from error
        return REGISTRY

    def get_addr_from_stub(self, service_stub_class: type[ServiceStub]) -> str:
        """Resolve the concrete address for a generated service stub class.

        :param service_stub_class: The generated gRPC stub class for a
            service.
        :return: The resolved address string used by the SDK to reach that
            service (for example ``'host:port'`` or a resolver template
            expanded value).
        :rtype: str
        """

        service = from_stub_class(service_stub_class)
        return self.get_addr_from_service_name(service)

    def get_addr_from_service_name(self, service_name: str) -> str:
        """Resolve a logical service name into a transport address.

        The method strips a leading dot (``"."``) if present and delegates
        to the configured :class:`Resolver`.

        :param service_name: Logical service name as generated by stubs or
            conventions.
        :return: Resolved address string.
        :rtype: str
        """

        runtime = cast(AsyncRuntime | None, getattr(self, "_runtime", None))
        if runtime is not None and not runtime.in_event_loop():
            return runtime.run_sync(self._get_addr_from_service_name(service_name))
        return self._get_addr_from_service_name_internal(service_name)

    async def _get_addr_from_service_name(self, service_name: str) -> str:
        """Resolve a service name on the SDK event loop.

        :param service_name: Logical service name.
        :return: Resolved transport address.
        """

        return self._get_addr_from_service_name_internal(service_name)

    def _get_addr_from_service_name_internal(self, service_name: str) -> str:
        """Normalize and resolve a service name without loop dispatch.

        :param service_name: Logical service name.
        :return: Resolved transport address.
        """

        if len(service_name) > 1 and service_name[0] == ".":
            service_name = service_name[1:]
        return self._resolver.resolve(service_name)

    def get_addr_by_method(self, method_name: str) -> str:
        """Return the cached address for a fully-qualified RPC method name.

        For a new method, call :func:`service_from_method_name` to get its
        service. Then, resolve it with :meth:`get_addr_from_service_name` and
        cache the result.

        :param method_name: Full RPC method string (``'/package.service/Method'``).
        :return: Resolved address string.
        :rtype: str
        """

        runtime = cast(AsyncRuntime | None, getattr(self, "_runtime", None))
        if runtime is not None and not runtime.in_event_loop():
            return runtime.run_sync(self._get_addr_by_method(method_name))
        return self._get_addr_by_method_internal(method_name)

    async def _get_addr_by_method(self, method_name: str) -> str:
        """Resolve and cache a method address on the SDK event loop.

        :param method_name: Fully qualified RPC method name.
        :return: Resolved transport address.
        """

        return self._get_addr_by_method_internal(method_name)

    def _get_addr_by_method_internal(self, method_name: str) -> str:
        """Resolve and cache a method address without loop dispatch.

        :param method_name: Fully qualified RPC method name.
        :return: Resolved transport address.
        """

        if method_name not in self._methods:
            service_name = service_from_method_name(method_name)
            self._methods[method_name] = self._get_addr_from_service_name_internal(
                service_name
            )
        return self._methods[method_name]

    def get_addr_by_route(self, route: Route) -> str:
        """Resolve immutable generated route metadata without global descriptors."""
        runtime = cast(AsyncRuntime | None, getattr(self, "_runtime", None))
        if runtime is not None and not runtime.in_event_loop():
            return runtime.run_sync(self._get_addr_by_route(route))
        return self._get_addr_by_route_internal(route)

    async def _get_addr_by_route(self, route: Route) -> str:
        """Resolve and cache a generated route on the SDK event loop.

        :param route: Generated route metadata.
        :return: Resolved transport address.
        """

        return self._get_addr_by_route_internal(route)

    def _get_addr_by_route_internal(self, route: Route) -> str:
        """Resolve and cache generated route metadata without loop dispatch.

        :param route: Generated route metadata.
        :return: Resolved transport address.
        """

        key = (
            id(route.registry),
            route.service,
            route.method,
            route.api_service_name,
        )
        if key in self._routes:
            return self._routes[key]
        address: str | None = None
        if self._route_custom_resolver is not None:
            try:
                address = self._route_custom_resolver.resolve(route.service)
            except UnknownServiceError:
                pass
        if address is None and route.api_service_name:
            address = route.api_service_name + ".{domain}"
            for find, replace in self._route_substitutions.items():
                address = address.replace(find, replace)
        if address is None:
            address = self._get_addr_from_service_name_internal(route.service)
        self._routes[key] = address
        return address

    def get_channel_by_route(self, route: Route) -> AddressChannel:
        """Return a pooled channel selected from generated route metadata."""
        return self.get_channel_by_addr(self.get_addr_by_route(route))

    def _lease_address_channel(self, chan: AddressChannel) -> AddressChannel:
        """Track a checked-out transport or retire it if shutdown won the race."""
        with self._channel_pool_lock:
            if not self._closed:
                self._leased_channels[id(chan)] = chan
                return chan
        self._schedule_address_channel_close(chan, None)
        raise ChannelClosedError("Channel closed")

    def get_channel_by_addr(self, addr: str) -> AddressChannel:
        """Request an :class:`AddressChannel` for the given resolved address.

        The method returns a pooled channel if available; otherwise a new
        underlying gRPC channel is created. Pooled channels with state
        :attr:`grpc.ChannelConnectivity.SHUTDOWN` are closed asynchronously and
        skipped.

        :param addr: Resolved address string.
        :return: An :class:`AddressChannel` wrapper for a gRPC channel.
        :rtype: :class:`AddressChannel`
        :raises ChannelClosedError: If the SDK channel has already been closed.

        .. warning::
           ``AddressChannel.channel`` is a native ``grpc.aio.Channel`` owned
           by the SDK loop. Direct calls on it are loop-affine. Use generated
           clients or :meth:`unary_unary` for cross-loop call handling.
        """

        with self._channel_pool_lock:
            if self._closed:
                raise ChannelClosedError("Channel closed")
        if not self._runtime.in_event_loop():
            return self._runtime.run_sync(self._get_channel_by_addr(addr))
        return self._get_channel_by_addr_internal(addr)

    async def _get_channel_by_addr(self, addr: str) -> AddressChannel:
        """Lease an address channel on the SDK event loop.

        :param addr: Resolved transport address.
        :return: Leased address channel.
        """

        return self._get_channel_by_addr_internal(addr)

    def _get_channel_by_addr_internal(self, addr: str) -> AddressChannel:
        """Lease or create an address channel without loop dispatch.

        The method reuses only a channel that belongs to the SDK event loop.
        It schedules stopped pooled channels for closure.

        :param addr: Resolved transport address.
        :return: Leased address channel.
        :raises ChannelClosedError: If channel shutdown has started.
        """

        current_loop = self._event_loop
        while True:
            chan: AddressChannel | None = None
            with self._channel_pool_lock:
                if self._closed:
                    raise ChannelClosedError("Channel closed")
                chans = self._free_channels.setdefault(addr, [])
                for index in range(len(chans) - 1, -1, -1):
                    if getattr(chans[index], "event_loop", None) is current_loop:
                        chan = chans.pop(index)
                        break
            if chan is None:
                break
            if chan.channel.get_state() != ChannelConnectivity.SHUTDOWN:
                return self._lease_address_channel(chan)
            self._schedule_address_channel_close(chan, None)

        chan = self.create_address_channel(addr)
        if getattr(chan, "event_loop", None) is None:
            chan.event_loop = current_loop
        return self._lease_address_channel(chan)

    def return_channel(self, chan: AddressChannel | None) -> None:
        """Return an :class:`AddressChannel` to the internal pool.

        Later :meth:`get_channel_by_addr` calls reuse channels in the pool.
        The pool keeps at most ``max_free_channels_per_address`` channels.
        The method closes excess or stopped channels asynchronously.

        :param chan: The :class:`AddressChannel` to return, or ``None``.
        :raises ChannelClosedError: If the SDK channel has been closed.
        """

        self._release_channel_on_sdk_loop(
            chan,
            discard=False,
            raise_if_closed=True,
        )

    def release_channel(
        self,
        chan: AddressChannel | None,
        *,
        discard: bool = False,
    ) -> None:
        """Release an internal transport without masking a concurrent shutdown.

        Generated request and stream paths use this method so a
        :class:`ChannelClosedError` raised during cleanup cannot replace the RPC
        result or its original error. Direct callers of :meth:`return_channel`
        and :meth:`discard_channel` retain their previous closed-channel error.
        """
        self._release_channel_on_sdk_loop(
            chan,
            discard=discard,
            raise_if_closed=False,
        )

    def _release_channel_on_sdk_loop(
        self,
        chan: AddressChannel | None,
        *,
        discard: bool,
        raise_if_closed: bool,
    ) -> None:
        """Release a channel on the SDK loop or dispatch the release to it.

        :param chan: Address channel to release. Use ``None`` for no action.
        :param discard: Close the channel instead of returning it to the pool.
        :param raise_if_closed: Raise when SDK channel shutdown has started.
        :raises ChannelClosedError: If shutdown has started and
            ``raise_if_closed`` is ``True``.
        """

        if chan is None:
            return
        with self._channel_pool_lock:
            closed = self._closed
        if closed:
            with self._channel_pool_lock:
                leased = self._leased_channels.pop(id(chan), None)
            if leased is None:
                self._schedule_address_channel_close(chan, None)
            if raise_if_closed:
                raise ChannelClosedError("Channel closed")
            return
        if self._runtime.in_event_loop():
            self._release_address_channel(
                chan,
                discard=discard,
                raise_if_closed=raise_if_closed,
            )
            return
        self._runtime.run_sync(
            self._release_address_channel_async(
                chan,
                discard=discard,
                raise_if_closed=raise_if_closed,
            )
        )

    async def _release_address_channel_async(
        self,
        chan: AddressChannel | None,
        *,
        discard: bool,
        raise_if_closed: bool,
    ) -> None:
        """Release an address channel from an SDK-loop coroutine.

        :param chan: Address channel to release. Use ``None`` for no action.
        :param discard: Close the channel instead of returning it to the pool.
        :param raise_if_closed: Raise when SDK channel shutdown has started.
        :raises ChannelClosedError: If shutdown has started and
            ``raise_if_closed`` is ``True``.
        """

        self._release_address_channel(
            chan,
            discard=discard,
            raise_if_closed=raise_if_closed,
        )

    def _release_address_channel(
        self,
        chan: AddressChannel | None,
        *,
        discard: bool,
        raise_if_closed: bool,
    ) -> None:
        if chan is None:
            return
        with self._channel_pool_lock:
            leased = self._leased_channels.pop(id(chan), None)
            closed = self._closed
        if closed:
            if leased is None:
                self._schedule_address_channel_close(chan, None)
            if raise_if_closed:
                raise ChannelClosedError("Channel closed")
            return
        reusable = (
            not discard
            and getattr(chan, "event_loop", None) is not None
            and chan.channel.get_state() != ChannelConnectivity.SHUTDOWN
        )
        with self._channel_pool_lock:
            closed = self._closed
            if not closed and reusable:
                chans = self._free_channels.setdefault(chan.address, [])
                if any(pooled is chan for pooled in chans):
                    return
                if len(chans) < self._max_free_channels_per_address:
                    chans.append(chan)
                    return
        self._schedule_address_channel_close(chan, None)
        if closed and raise_if_closed:
            raise ChannelClosedError("Channel closed")

    async def _close_address_channel(
        self,
        chan: AddressChannel,
        grace: float | None,
    ) -> None:
        """Close a pooled transport on its owner loop when that loop is running."""
        owner_loop = getattr(chan, "event_loop", None)
        current_loop = get_running_loop()
        if (
            owner_loop is not None
            and owner_loop is not current_loop
            and owner_loop.is_running()
        ):
            close_coro = chan.channel.close(grace)
            try:
                close_future = run_coroutine_threadsafe(
                    close_coro,
                    owner_loop,
                )
            except RuntimeError:
                try:
                    await close_coro
                except RuntimeError as error:
                    logger.warning(
                        "Unable to close channel after its owner loop stopped",
                        exc_info=error,
                    )
            else:
                await wrap_future(close_future)
            return
        await chan.channel.close(grace)

    def _schedule_address_channel_close(
        self,
        chan: AddressChannel,
        grace: float | None,
    ) -> None:
        """Schedule an unpooled transport close without sharing loop-local tasks."""

        async def close_and_log() -> None:
            try:
                await self._close_address_channel(chan, grace)
            except CancelledError:
                pass
            except Exception as e:
                logger.error(
                    "Unhandled exception while closing address channel",
                    exc_info=e,
                )

        owner_loop = getattr(chan, "event_loop", None)
        try:
            current_loop = get_running_loop()
        except RuntimeError:
            current_loop = None
        if (
            owner_loop is not None
            and owner_loop is not current_loop
            and owner_loop.is_running()
        ):
            close_coro = close_and_log()
            try:
                run_coroutine_threadsafe(close_coro, owner_loop)
                return
            except RuntimeError:
                close_coro.close()
        if current_loop is None:
            logger.warning(
                "Unable to schedule channel close without a running event loop"
            )
            return
        create_task(
            close_and_log(),
            name=f"Channel transport close for {chan.address}",
        )

    def discard_channel(self, chan: AddressChannel | None) -> None:
        """Dispose of an :class:`AddressChannel` by scheduling its close.

        The close is performed asynchronously on the transport's owner loop
        without blocking the caller.

        :param chan: The :class:`AddressChannel` to discard, or ``None``.
        :raises ChannelClosedError: If the SDK channel has been closed.
        """

        self._release_channel_on_sdk_loop(
            chan,
            discard=True,
            raise_if_closed=True,
        )

    def get_channel_by_method(self, method_name: str) -> AddressChannel:
        """Get an :class:`AddressChannel` for an RPC method name.

        The method resolves the address via :meth:`get_addr_by_method` and
        then calls :meth:`get_channel_by_addr` to obtain the channel.

        :param method_name: Full RPC method string.
        :return: An :class:`AddressChannel` bound to the resolved address.
        """

        addr = self.get_addr_by_method(method_name)
        return self.get_channel_by_addr(addr)

    def get_address_options(self, addr: str) -> ChannelArgumentType:
        """Compute effective gRPC channel options for a specific address.

        Global options are combined with per-address options and the SDK
        user-agent is appended via ``grpc.primary_user_agent``.

        :param addr: Resolved address string.
        :return: A sequence of channel option tuples ready to be passed to
            gRPC when creating a channel.
        :rtype: list of ``tuple[str, Any]``
        """

        ret = list(keepalive_channel_options(self._keepalive_config))
        ret.extend(self._global_options)
        if addr in self._address_options:
            ret.extend(self._address_options[addr])
        return set_user_agent_option(self.user_agent, ret)

    def get_address_interceptors(self, addr: str) -> Sequence[ClientInterceptor]:
        """Return the ordered list of interceptors to apply to a channel.

        Global interceptors are applied first, then any per-address
        interceptors, and finally internal interceptors added by the
        channel implementation.

        :param addr: Resolved address string.
        :return: Combined global and per-address interceptors.
        :rtype: A sequence of :class:`ClientInterceptor`
        """

        ret = list(self._global_interceptors)
        if addr in self._address_interceptors:
            ret.extend(self._address_interceptors[addr])
        ret.extend(self._global_interceptors_inner)
        return ret

    def create_address_channel(self, addr: str) -> AddressChannel:
        """Create a new underlying gRPC channel for the given address.

        The method combines options and interceptors. It extracts special
        options such as ``INSECURE`` and ``COMPRESSION``. Then, it constructs
        a secure or insecure gRPC channel wrapper. The returned
        :class:`AddressChannel` contains the gRPC channel and resolved address.

        :param addr: Resolved address string.
        :type addr: str
        :return: An :class:`AddressChannel` containing the created channel.
        :rtype: :class:`AddressChannel`
        """

        if not self._runtime.in_event_loop():
            return self._runtime.run_sync(self._create_address_channel(addr))
        return self._create_address_channel_internal(addr)

    async def _create_address_channel(self, addr: str) -> AddressChannel:
        """Create an address channel on the SDK event loop.

        :param addr: Resolved transport address.
        :return: New address channel.
        """

        return self._create_address_channel_internal(addr)

    def _create_address_channel_internal(self, addr: str) -> AddressChannel:
        """Create a configured gRPC channel without loop dispatch.

        The new channel records the current SDK event loop as its owner.

        :param addr: Resolved transport address.
        :return: New address channel.
        """

        logger.debug(f"creating channel for {addr=}")
        event_loop = _get_working_loop()
        opts = self.get_address_options(addr)
        opts, insecure = pop_option(opts, INSECURE, bool)
        opts, compression = pop_option(opts, COMPRESSION, Compression)
        interceptors = self.get_address_interceptors(addr)
        if insecure:
            return AddressChannel(
                insecure_channel(addr, opts, compression, interceptors),  # type: ignore[unused-ignore,no-any-return]
                addr,
                event_loop,
            )
        return AddressChannel(
            secure_channel(  # type: ignore[unused-ignore,no-any-return]
                addr,
                self._tls_credentials,
                opts,
                compression,
                interceptors,
            ),
            addr,
            event_loop,
        )

    def unary_unary(  # type: ignore[unused-ignore,override]
        self,
        method_name: str,
        request_serializer: SerializingFunction | None = None,
        response_deserializer: DeserializingFunction | None = None,
    ) -> UnaryUnaryMultiCallable[Req, Res]:  # type: ignore[unused-ignore,override]
        """
        A method to support using SDK channel as gRPC Channel.

        :param method_name:
            Full RPC method string, i.e., ``'/package.service/method'``.
        :type method_name: str
        :param request_serializer:
            A function that serializes a request message to bytes.
        :type request_serializer: SerializingFunction | None
        :param response_deserializer:
            A function that deserializes a response message from bytes.
        :type response_deserializer: DeserializingFunction | None
        :return:
            A :class:`UnaryUnaryMultiCallable` object that can be used to make
            the call.
        :rtype: :class:`NebiusUnaryUnaryMultiCallable` wrapper.
        """
        return NebiusUnaryUnaryMultiCallable(
            self,
            method_name,
            request_serializer,
            response_deserializer,
        )

    async def __aenter__(self) -> "Channel":
        """
        Enter the async context manager.
        Returns self to allow usage like::

            async with channel as chan:
                await chan.some_method()

        Will close the channel on exit.
        """
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """
        Exit the async context manager.
        Calls close() to gracefully shut down resources.
        """
        await self.close(None)

    def get_state(self, try_to_connect: bool = False) -> ChannelConnectivity:
        """
        Nebius Python SDK channels are always ready unless closed.

        :param try_to_connect:
            Ignored parameter to satisfy the gRPC Channel interface.
        :type try_to_connect: bool
        :return:
            :attr:`grpc.ChannelConnectivity.READY` if the channel is open,
            :attr:`grpc.ChannelConnectivity.SHUTDOWN` if closed.
        :rtype: :class:`grpc.ChannelConnectivity`
        """
        if self._closed:
            return ChannelConnectivity.SHUTDOWN
        return ChannelConnectivity.READY

    async def wait_for_state_change(
        self,
        last_observed_state: ChannelConnectivity,
    ) -> None:
        """
        Nebius Python SDK channels are always ready unless closed.
        This method is provided to satisfy the gRPC Channel interface.

        :raises NotImplementedError:
        """
        raise NotImplementedError("this method has no meaning for this channel")

    async def channel_ready(self) -> None:
        """
        Channel is always ready, nothing to do here.
        """
        return

    def unary_stream(  # type: ignore[unused-ignore,override]
        self,
        method: str,
        request_serializer: SerializingFunction | None = None,
        response_deserializer: DeserializingFunction | None = None,
    ) -> UnaryStreamMultiCallable[Req, Res]:  # type: ignore[unused-ignore]
        """
        Nebius Python SDK does not support streaming RPCs.

        :raises NotImplementedError:
        """
        raise NotImplementedError("Method not implemented")

    def stream_unary(  # type: ignore[unused-ignore,override]
        self,
        method: str,
        request_serializer: SerializingFunction | None = None,
        response_deserializer: DeserializingFunction | None = None,
    ) -> StreamUnaryMultiCallable:
        """
        Nebius Python SDK does not support streaming RPCs.

        :raises NotImplementedError:
        """
        raise NotImplementedError("Method not implemented")

    def stream_stream(  # type: ignore[unused-ignore,override]
        self,
        method: str,
        request_serializer: SerializingFunction | None = None,
        response_deserializer: DeserializingFunction | None = None,
    ) -> StreamStreamMultiCallable:
        """
        Nebius Python SDK does not support streaming RPCs.

        :raises NotImplementedError:
        """
        raise NotImplementedError("Method not implemented")
