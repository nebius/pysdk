"""High-level gRPC channel manager for the Nebius Python SDK.

Channel locks follow one order. Code can acquire ``_channel_pool_lock`` before
``_tasks_lock`` or a runtime lock, and ``_close_submit_lock`` before a runtime
lock. It must not acquire these locks in reverse order. No code awaits, joins a
thread, or waits for a future while it holds a channel lock. SDK task objects
are copied under their lock and then cancelled or awaited after the lock is
released.
"""

import os
import sys
from asyncio import (
    AbstractEventLoop,
    CancelledError,
    Event,
    Future,
    Task,
    create_task,
    current_task,
    ensure_future,
    gather,
    get_event_loop,
    get_running_loop,
    run_coroutine_threadsafe,
    shield,
    sleep,
    wait_for,
    wrap_future,
)
from asyncio import TimeoutError as AsyncTimeoutError
from collections.abc import Awaitable, Callable, Coroutine, Generator, Mapping, Sequence
from concurrent.futures import CancelledError as ConcurrentCancelledError
from concurrent.futures import Future as ConcurrentFuture
from concurrent.futures import InvalidStateError as ConcurrentInvalidStateError
from concurrent.futures import TimeoutError as ConcurrentTimeoutError
from contextlib import suppress
from functools import wraps
from inspect import isawaitable
from logging import getLogger
from pathlib import Path
from threading import Event as ThreadEvent
from threading import Lock, RLock, Thread
from time import monotonic
from typing import Any, Concatenate, ParamSpec, TextIO, TypeVar, cast
from weakref import WeakSet, finalize, ref

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
from nebius.aio.request import _snapshot_request_input, _validate_timeout
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

from ._runtime import (
    AsyncRuntime,
    CrossLoopAwaitable,
    LoopExceptionHandler,
    _validate_loop_exception_handler,
)
from ._task_context import (
    bridge_awaitable,
    close_rejected_sync_awaitable,
    dispose_unstarted_awaitable,
)
from .base import AddressChannel, ChannelBase

logger = getLogger(__name__)

Req = TypeVar("Req", bound=Message)
Res = TypeVar("Res", bound=Message)

T = TypeVar("T")
P = ParamSpec("P")
C = TypeVar("C")

_detached_foreign_close_handles = WeakSet[Any]()
_detached_foreign_close_tasks_lock = Lock()
_DETACHED_FOREIGN_CLOSE_RETENTION_SECONDS = 3600.0
_transport_close_watch_lock = Lock()
_transport_close_watch_event = ThreadEvent()
_transport_close_watch_entries: list[
    tuple[Callable[[], AbstractEventLoop | None], ConcurrentFuture[None]]
] = []
_transport_close_watch_thread: Thread | None = None


def _reset_detached_foreign_close_tasks_after_fork() -> None:
    """Drop parent-process task and lock state in a forked child.

    Event-loop tasks cannot be transferred across ``fork``. Replacing both
    objects also prevents a child from observing a lock held by a vanished
    parent thread.
    """

    global _detached_foreign_close_handles
    global _detached_foreign_close_tasks_lock
    global _transport_close_watch_entries
    global _transport_close_watch_event
    global _transport_close_watch_lock
    global _transport_close_watch_thread
    _detached_foreign_close_handles = WeakSet()
    _detached_foreign_close_tasks_lock = Lock()
    _transport_close_watch_entries = []
    _transport_close_watch_event = ThreadEvent()
    _transport_close_watch_lock = Lock()
    _transport_close_watch_thread = None


if hasattr(os, "register_at_fork"):
    os.register_at_fork(after_in_child=_reset_detached_foreign_close_tasks_after_fork)


def _retain_detached_foreign_close(
    handle: Any,
    owner_loop: AbstractEventLoop,
) -> None:
    """Retain foreign-loop cleanup without retaining its parent channel.

    A caller-owned event loop keeps only weak references to tasks. A
    cross-thread dispatch returns a concurrent Future. The SDK retains either
    handle until completion.
    A callback in the owner loop's public scheduling queue retains the handle.
    It renews a long timer while the close is pending. The module-level weak
    set is only for diagnostics and tests. As a result, the retention cycle
    has no process-global strong reference. If the application drops a stopped
    loop, its pending close state can be collected with it. This design does
    not add private attributes to the loop, so it also supports fixed-slot
    loop types.

    The registry contains only detached cleanup. It does not contain per-SDK
    scheduler or bridge state. Its lock lets independent SDK instances and
    owner-loop threads use it at the same time.

    :param handle: Foreign-loop transport-close task or Future to retain.
    :param owner_loop: Event loop that owns the close operation.
    """

    with _detached_foreign_close_tasks_lock:
        _detached_foreign_close_handles.add(handle)
    loop_ref = ref(owner_loop)
    retention: dict[str, Any] = {}

    def retain_on_owner_loop() -> None:
        """Renew owner-loop retention while detached close work is pending."""

        retained_loop = loop_ref()
        if handle.done() or retained_loop is None or retained_loop.is_closed():
            retention.clear()
            return
        retention["timer"] = retained_loop.call_later(
            _DETACHED_FOREIGN_CLOSE_RETENTION_SECONDS,
            retain_on_owner_loop,
        )

    def discard(completed: Any) -> None:
        """Release a completed detached transport close."""

        with _detached_foreign_close_tasks_lock:
            _detached_foreign_close_handles.discard(completed)
        timer = retention.pop("timer", None)
        retained_loop = loop_ref()
        if timer is None or retained_loop is None or retained_loop.is_closed():
            retention.clear()
            return
        try:
            retained_loop.call_soon_threadsafe(timer.cancel)
        except RuntimeError:
            retention.clear()

    handle.add_done_callback(discard)
    try:
        owner_loop.call_soon_threadsafe(retain_on_owner_loop)
    except RuntimeError:
        # The loop closed after it accepted the transport close. It cannot run
        # that close, so no loop-owned retention callback can make progress.
        pass


def _start_detached_foreign_close(
    close_coro: Coroutine[Any, Any, None],
    owner_loop: AbstractEventLoop,
    name: str,
    completion: ConcurrentFuture[None] | None = None,
) -> bool:
    """Start and retain detached close work on the current owner loop.

    A custom task factory can reject task creation. This helper closes the
    rejected coroutine and settles an optional SDK lifecycle reservation, so
    the rejection cannot strand shutdown.

    :param close_coro: Transport-close coroutine to start.
    :param owner_loop: Running loop that owns ``close_coro``.
    :param name: Diagnostic task name.
    :param completion: Optional SDK lifecycle reservation to settle on failure.
    :return: ``True`` if task creation succeeded.
    """

    try:
        task = create_task(close_coro, name=name)
    except BaseException as error:
        dispose_unstarted_awaitable(close_coro)
        logger.error(
            "The SDK could not start the transport close task.",
            exc_info=error,
        )
        if completion is not None:
            try:
                completion.set_result(None)
            except ConcurrentInvalidStateError:
                pass
        return False
    _retain_detached_foreign_close(task, owner_loop)
    return True


def _schedule_detached_close_factory(
    factory: Callable[[], Coroutine[Any, Any, None]],
    owner_loop: AbstractEventLoop,
    name: str,
    completion: ConcurrentFuture[None] | None = None,
) -> bool:
    """Create detached close work only after its owner loop executes.

    A loop can accept a thread-safe callback and stop before it executes that
    callback. The callback retains the factory instead of a coroutine, so loop
    closure cannot discard unawaited close work. The detached task settles an
    optional SDK reservation after it starts or rejects the close work.

    :param factory: Function that creates close work on the owner loop.
    :param owner_loop: Event loop that owns the close work.
    :param name: Diagnostic task name.
    :param completion: Optional SDK lifecycle reservation.
    :return: ``True`` if the loop accepted or started the close work.
    """

    def create_and_start() -> bool:
        """Create and start close work on its owner loop."""

        try:
            close_coro = factory()
        except BaseException as error:
            logger.error(
                "The SDK could not create the transport close work.",
                exc_info=error,
            )
            if completion is not None:
                try:
                    completion.set_result(None)
                except ConcurrentInvalidStateError:
                    pass
            return False
        return _start_detached_foreign_close(close_coro, owner_loop, name, completion)

    def start() -> None:
        """Run the close factory from a thread-safe loop callback."""

        create_and_start()

    try:
        current_loop = get_running_loop()
    except RuntimeError:
        current_loop = None
    if current_loop is owner_loop:
        return create_and_start()
    try:
        owner_loop.call_soon_threadsafe(start)
    except RuntimeError:
        if completion is not None:
            try:
                completion.set_result(None)
            except ConcurrentInvalidStateError:
                pass
        return False
    if completion is not None:
        _watch_transport_close(owner_loop, completion)
    return True


def _watch_transport_close(
    owner_loop: AbstractEventLoop,
    completion: ConcurrentFuture[None],
) -> None:
    """Use one daemon monitor for all close callbacks on stopped loops.

    :param owner_loop: Loop that accepted the close callback.
    :param completion: SDK lifecycle reservation to release if the loop stops.
    """

    global _transport_close_watch_thread
    start_thread = False
    with _transport_close_watch_lock:
        _transport_close_watch_entries.append((ref(owner_loop), completion))
        if _transport_close_watch_thread is None:
            start_thread = True
            _transport_close_watch_thread = Thread(
                name="nebius-sdk-transport-close-watch",
                target=_monitor_transport_closes,
                daemon=True,
            )
        thread = _transport_close_watch_thread
    _transport_close_watch_event.set()
    if not start_thread:
        return
    try:
        thread.start()
    except RuntimeError as error:
        logger.error(
            "The SDK could not monitor the transport close callbacks.",
            exc_info=error,
        )
        with _transport_close_watch_lock:
            pending = list(_transport_close_watch_entries)
            _transport_close_watch_entries.clear()
            _transport_close_watch_thread = None
        for _, pending_completion in pending:
            try:
                pending_completion.set_result(None)
            except ConcurrentInvalidStateError:
                pass


def _monitor_transport_closes() -> None:
    """Release close reservations when their owner loops stop."""

    global _transport_close_watch_thread
    while True:
        _transport_close_watch_event.wait(0.01)
        _transport_close_watch_event.clear()
        with _transport_close_watch_lock:
            _transport_close_watch_entries[:] = [
                entry for entry in _transport_close_watch_entries if not entry[1].done()
            ]
            if not _transport_close_watch_entries:
                _transport_close_watch_thread = None
                return
            entries = list(_transport_close_watch_entries)
        for loop_reference, completion in entries:
            loop = loop_reference()
            if loop is not None and loop.is_running():
                continue
            try:
                completion.set_result(None)
            except ConcurrentInvalidStateError:
                pass


def _finalize_runtime(runtime: AsyncRuntime, process_id: int) -> None:
    """Shut down a runtime only in the process that created it.

    Threads and locks do not survive ``fork`` coherently. A child finalizer
    must therefore avoid touching inherited runtime state.

    :param runtime: Runtime owned by the finalized channel.
    :param process_id: Process that created ``runtime``.
    """

    if os.getpid() == process_id:
        runtime.shutdown_async()


def _shutdown_runtime_on_init_failure(
    initializer: Callable[Concatenate[C, P], None],
) -> Callable[Concatenate[C, P], None]:
    """Stop a partially constructed channel's runtime before re-raising.

    A constructor traceback can retain the incomplete channel, so its weakref
    finalizer is not a timely resource boundary. This wrapper starts cleanup
    for every exception after runtime creation without obscuring the public
    signature or documentation. It waits for an owned runtime. It only
    schedules cleanup on a running caller-owned loop, because waiting for an
    unresponsive borrowed loop would prevent the constructor from propagating
    an interruption.

    :param initializer: Channel initializer to guard.
    :return: Initializer that stops an acquired runtime on failure.
    """

    @wraps(initializer)
    def guarded(instance: C, *args: P.args, **kwargs: P.kwargs) -> None:
        """Run the initializer and clean up a partial runtime on failure."""

        try:
            initializer(instance, *args, **kwargs)
        except BaseException:
            runtime = getattr(instance, "_runtime", None)
            finalizer = getattr(instance, "_runtime_finalizer", None)
            if finalizer is not None:
                finalizer.detach()
            if runtime is not None:
                try:
                    get_close_handle = getattr(instance, "_get_close_handle", None)
                    channel_lifecycle_ready = getattr(
                        instance,
                        "_channel_lifecycle_ready",
                        False,
                    )
                    if callable(get_close_handle) and channel_lifecycle_ready:
                        closing = get_close_handle(None)
                        shutdown = runtime.shutdown_async()
                        if runtime.owned and not runtime.in_event_loop():
                            try:
                                closing._result()
                            finally:
                                shutdown._result()
                    elif runtime.event_loop.is_running():
                        shutdown = runtime.shutdown_async()
                        if runtime.owned and not runtime.in_event_loop():
                            shutdown._result()
                    else:
                        runtime.shutdown()
                except BaseException as cleanup_error:
                    logger.error(
                        "The SDK could not clean up the partially initialized "
                        "channel.",
                        exc_info=cleanup_error,
                    )
                    try:
                        shutdown = runtime.shutdown_async()
                        if runtime.owned and not runtime.in_event_loop():
                            shutdown._result()
                    except BaseException as shutdown_error:
                        logger.error(
                            "The SDK could not shut down the runtime after channel "
                            "cleanup failed.",
                            exc_info=shutdown_error,
                        )
            raise

    return cast(Callable[Concatenate[C, P], None], guarded)


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
        address_resolver: Callable[[], str] | None = None,
    ) -> None:
        """Initialize a cross-loop unary call.

        :param channel: SDK channel that owns the call.
        :param method: Fully qualified gRPC method name.
        :param request: Request value to send.
        :param request_serializer: Optional request serializer. For a custom
            request value, the SDK calls it synchronously on the thread that
            constructs the call. It must be thread-safe, loop-neutral, and
            return promptly.
        :param response_deserializer: Optional response deserializer.
        :param timeout: Optional call timeout in seconds.
        :param metadata: Optional call metadata.
        :param credentials: Optional call credentials.
        :param wait_for_ready: Optional gRPC wait-for-ready setting.
        :param compression: Optional gRPC compression setting.
        :param address: Resolved transport address. Use ``None`` to resolve the
            address from ``method``.
        :param address_resolver: Optional SDK-loop callback that resolves a
            deferred transport address when the native call starts.

        Mutable supported protobuf request values are copied before submission.
        Other custom request values are serialized immediately on the caller
        thread when a serializer is supplied. Metadata is copied to an
        independent gRPC metadata object. These snapshots prevent a caller from
        changing native-call inputs while the SDK loop is waiting to create the
        call. A custom request value without a serializer is assumed to be
        immutable or otherwise safe to share between threads.
        """

        channel._check_process()
        self._channel = channel
        self._method = method
        self._timeout = _validate_timeout(timeout, "timeout")
        self._request: Any
        self._request_serializer: SerializingFunction | None
        request_snapshot = _snapshot_request_input(request)
        if request_serializer is None:
            self._request = (
                bytes(request_snapshot)
                if isinstance(request_snapshot, (bytearray, memoryview))
                else request_snapshot
            )
            self._request_serializer = None
        elif request_snapshot is not request:
            self._request = request_snapshot
            self._request_serializer = request_serializer
        else:
            self._request = request_serializer(request)
            self._request_serializer = None
        self._response_deserializer = response_deserializer
        self._metadata = None if metadata is None else GrpcMetadata(*metadata)
        self._credentials = credentials
        self._wait_for_ready = wait_for_ready
        self._compression = compression
        self._address = address
        self._address_resolver = address_resolver
        self._started_at = monotonic()
        self._call: UnaryUnaryCall[Req, Res] | None = None
        self._call_ready = Event()
        self._terminal_lock = RLock()
        self._terminal: dict[str, Any] = {}
        self._pending_debug_result: Awaitable[Any] | None = None
        self._terminal_capture_closed = False
        self._rpc_done: ConcurrentFuture[None] = ConcurrentFuture()
        self._terminal_ready: ConcurrentFuture[None] = ConcurrentFuture()
        self._native_terminal = False
        self._native_cancelled = False
        self._cancel_requested = False
        self._address_channel: AddressChannel | None = None
        self._released = False
        self._submitted = channel.run_async(self._invoke())
        self._submitted._add_internal_done_callback(self._submission_finished)

    def _submission_finished(self, submitted: CrossLoopAwaitable[Res]) -> None:
        """Publish terminal state when submission ends before call creation.

        Cancellation or asynchronous task-creation failure can end an accepted
        submission before its SDK coroutine starts. No ``finally`` block can
        then signal the call and terminal gates.

        :param submitted: Completed SDK submission.
        """

        with self._terminal_lock:
            call_was_never_created = self._call is None
        if not call_was_never_created:
            return
        if submitted.cancelled():
            self._publish_prestart_cancellation()
            return
        try:
            submitted.event_loop.call_soon_threadsafe(self._call_ready.set)
        except RuntimeError:
            pass
        self._publish_rpc_done()
        self._publish_terminal_ready()

    def _publish_prestart_cancellation(self) -> None:
        """Cache the standard local-cancellation status and wake waiters."""

        with self._terminal_lock:
            self._terminal.update(
                {
                    "initial_metadata": GrpcMetadata(),
                    "trailing_metadata": GrpcMetadata(),
                    "code": StatusCode.CANCELLED,
                    "details": "The application canceled the RPC.",
                    "debug_error_string": "",
                }
            )
        try:
            self._submitted.event_loop.call_soon_threadsafe(self._call_ready.set)
        except RuntimeError:
            pass
        self._publish_rpc_done()
        self._publish_terminal_ready()

    def _publish_rpc_done(self) -> None:
        """Signal the public native-RPC completion boundary once."""

        with self._terminal_lock:
            if not self._rpc_done.done():
                self._rpc_done.set_result(None)

    def _publish_terminal_ready(self) -> None:
        """Signal that no further authoritative terminal capture is pending."""

        with self._terminal_lock:
            if not self._terminal_ready.done():
                self._terminal_ready.set_result(None)

    async def _invoke(self) -> Res:
        """Create and run the native call on the SDK event loop."""

        discard = False
        try:
            if self._address is None:
                if self._address_resolver is None:
                    address_channel = self._channel.get_channel_by_method(self._method)
                else:
                    address = self._address_resolver()
                    address_channel = self._channel.get_channel_by_addr(address)
            else:
                address_channel = self._channel.get_channel_by_addr(self._address)
            with self._terminal_lock:
                publish_address = not self._cancel_requested
                if publish_address:
                    self._address_channel = address_channel
            if not publish_address:
                self._channel.release_channel(address_channel, discard=True)
                self._released = True
                raise CancelledError
            transport = address_channel.channel
            call = cast(
                UnaryUnaryCall[Req, Res],
                transport.unary_unary(
                    self._method,
                    self._request_serializer,
                    self._response_deserializer,
                )(
                    self._request,
                    timeout=self.time_remaining(),
                    metadata=self._metadata,
                    credentials=self._credentials,
                    wait_for_ready=self._wait_for_ready,
                    compression=self._compression,
                ),
            )
            with self._terminal_lock:
                publish_call = not self._cancel_requested
                if publish_call:
                    self._call = call
            if not publish_call:
                call.cancel()
                raise CancelledError
            add_done_callback = getattr(call, "add_done_callback", None)
            if callable(add_done_callback):
                add_done_callback(self._mark_native_terminal)
            self._call_ready.set()
            try:
                try:
                    result = await call
                except CancelledError:
                    # Runtime shutdown cancels wrapper tasks directly. If the
                    # native done callback won that race, recover the native
                    # outcome instead of reporting an ambiguous cancellation.
                    with self._terminal_lock:
                        native_terminal = self._native_terminal
                    if not native_terminal:
                        raise
                    result = await shield(call)
            finally:
                # Native completion and wrapper completion are distinct. The
                # latter remains pending while terminal metadata is copied.
                # Publish the former before that asynchronous copy so a late
                # caller cannot replace an RPC result with cancellation.
                with self._terminal_lock:
                    self._native_terminal = True
                self._publish_rpc_done()
            await self._capture_authoritative_terminal(call)
            return result
        except CancelledError:
            discard = True
            with self._terminal_lock:
                self._terminal.update(
                    {
                        "initial_metadata": GrpcMetadata(),
                        "trailing_metadata": GrpcMetadata(),
                        "code": StatusCode.CANCELLED,
                        "details": "The application or the SDK canceled the RPC.",
                        "debug_error_string": "",
                    }
                )
            raise
        except Exception as error:
            discard = True
            debug_details = await self._read_debug_error_string(error)
            if debug_details is not None:
                with self._terminal_lock:
                    self._terminal["debug_error_string"] = debug_details
            failed_call = self._call
            if failed_call is not None:
                with suppress(Exception):
                    await self._capture_authoritative_terminal(failed_call)
            raise
        except BaseException:
            discard = True
            raise
        finally:
            self._call_ready.set()
            try:
                if not self._released:
                    self._channel.release_channel(
                        self._address_channel,
                        discard=discard,
                    )
                    self._released = True
            finally:
                with self._terminal_lock:
                    self._terminal_capture_closed = True
                    abandoned_debug = self._pending_debug_result
                    self._pending_debug_result = None
                if abandoned_debug is not None:
                    dispose_unstarted_awaitable(abandoned_debug)
                self._publish_rpc_done()
                self._publish_terminal_ready()

    def _mark_native_terminal(self, completed: object) -> None:
        """Publish native call completion before the wrapper task resumes."""

        # Native terminality is authoritative before any optional diagnostic
        # accessor runs. A slow or failing custom accessor must not leave a
        # window in which another thread can still cancel the completed RPC.
        with self._terminal_lock:
            self._native_terminal = True
            capture_closed = self._terminal_capture_closed
        native_cancelled = False
        cancelled = getattr(completed, "cancelled", None)
        if callable(cancelled):
            try:
                native_cancelled = bool(cancelled())
            except BaseException as error:
                logger.debug(
                    "The SDK could not read the native gRPC cancellation state.",
                    exc_info=error,
                )
        with self._terminal_lock:
            self._native_cancelled = native_cancelled
        # Public completion includes synchronous cancellation state but does
        # not wait for optional debug details. Callbacks registered on the SDK
        # loop still run after this callback returns and therefore observe
        # immediately available synchronous details.
        self._publish_rpc_done()
        debug_details: str | None = None
        abandoned_debug: Awaitable[Any] | None = None
        debug_error_string = getattr(completed, "debug_error_string", None)
        if callable(debug_error_string) and not capture_closed:
            try:
                debug_result = debug_error_string()
            except BaseException as error:
                logger.debug(
                    "The SDK could not read the native gRPC debug details at "
                    "completion.",
                    exc_info=error,
                )
            else:
                if isinstance(debug_result, str):
                    debug_details = debug_result
                elif isawaitable(debug_result):
                    # Calling an asynchronous accessor creates a coroutine.
                    # Turn it into a loop-owned task immediately so wrapper
                    # cancellation cannot abandon an unstarted coroutine.
                    # The terminal-capture path still awaits the same task.
                    try:
                        pending_debug = ensure_future(debug_result)
                    except BaseException:
                        dispose_unstarted_awaitable(debug_result)
                        pending_debug = None

                    if pending_debug is not None:

                        def observe_debug_failure(future: Future[Any]) -> None:
                            """Retrieve an exception from the debug accessor."""

                            if not future.cancelled():
                                future.exception()

                        pending_debug.add_done_callback(observe_debug_failure)
                        with self._terminal_lock:
                            if self._terminal_capture_closed:
                                abandoned_debug = pending_debug
                            else:
                                abandoned_debug = self._pending_debug_result
                                self._pending_debug_result = pending_debug
                else:
                    dispose_unstarted_awaitable(debug_result)
        with self._terminal_lock:
            if debug_details is not None:
                self._terminal["debug_error_string"] = debug_details
        if abandoned_debug is not None:
            dispose_unstarted_awaitable(abandoned_debug)

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

        async def read_accessor(name: str) -> Any:
            """Normalize synchronous and asynchronous accessor failures."""

            try:
                pending = getattr(call, name)()
            except BaseException as error:
                return error
            return await pending

        values = await gather(
            *(read_accessor(name) for name in names),
            return_exceptions=True,
        )
        with self._terminal_lock:
            pending_debug = self._pending_debug_result
            self._pending_debug_result = None
            debug_already_captured = "debug_error_string" in self._terminal
        debug_details = (
            await self._read_debug_error_string(call, pending_debug)
            if pending_debug is not None or not debug_already_captured
            else None
        )
        with self._terminal_lock:
            for name, value in zip(names, values):
                if not isinstance(value, BaseException):
                    self._terminal[name] = value
            if debug_details is not None:
                self._terminal["debug_error_string"] = debug_details

    async def _read_debug_error_string(
        self,
        source: object,
        pending: Awaitable[Any] | None = None,
    ) -> str | None:
        """Read optional synchronous or asynchronous native diagnostics.

        Diagnostic accessor failures must not replace the authoritative RPC
        result. A pending accessor captured by the native done callback is
        awaited exactly once on the SDK loop.

        :param source: Native call or error that exposes the accessor.
        :param pending: Awaitable already created by the native done callback.
        :return: Debug string, or ``None`` when it is unavailable.
        """

        try:
            result: Any
            if pending is not None:
                result = await pending
            else:
                debug_error_string = getattr(source, "debug_error_string", None)
                if not callable(debug_error_string):
                    return None
                result = debug_error_string()
                if isawaitable(result):
                    result = await result
            return result if isinstance(result, str) else None
        except BaseException as error:
            logger.debug(
                "The SDK could not read the asynchronous gRPC debug error " "details.",
                exc_info=error,
            )
            return None

    async def _capture_authoritative_terminal(
        self,
        call: UnaryUnaryCall[Req, Res],
    ) -> None:
        """Finish terminal capture after native completion despite SDK close.

        Runtime shutdown cancels ordinary submissions directly. After the
        native call ends, that cancellation must not replace its result or
        error. A shielded child task copies the metadata. This submission waits
        for the child task before it finishes.

        :param call: Authoritatively completed native call.
        """

        capture_work = self._capture_terminal(call)
        try:
            capture = create_task(capture_work)
        except BaseException as error:
            # A caller-owned loop can reject task creation through its custom
            # task factory. The native result is already authoritative. Use a
            # direct Task so the factory cannot replace that result or leave
            # the terminal-capture coroutine unobserved.
            dispose_unstarted_awaitable(capture_work)
            logger.debug(
                "The event-loop task factory rejected terminal capture. The "
                "SDK will bypass the factory.",
                exc_info=error,
            )
            capture = Task(
                self._capture_terminal(call),
                loop=get_running_loop(),
            )
        try:
            await shield(capture)
        except CancelledError:
            await capture

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
            raise RuntimeError("The SDK did not create the gRPC call.")
        accessor = ensure_future(getattr(call, method)())
        try:
            return await shield(accessor)
        except CancelledError:
            # Cancelling one public accessor must not inject cancellation into
            # a custom/native accessor that can share terminal-capture state
            # with the authoritative RPC wrapper.
            def observe_abandoned(future: Future[Any]) -> None:
                """Retrieve an exception from the abandoned accessor."""

                if not future.cancelled():
                    future.exception()

            accessor.add_done_callback(observe_abandoned)
            raise

    async def _public_call_result(self, method: str) -> Any:
        """Return one call value to an external event loop.

        :param method: Name of the native call method to run.
        :return: Result of the named method.
        """

        self._submitted._check_process()
        with self._terminal_lock:
            if method in self._terminal:
                return self._terminal[method]
        try:
            return await self._channel.run_async(self._call_result(method))
        except ChannelClosedError:
            # Close may reject this new accessor submission while it is
            # already draining the call submission that owns terminal capture.
            # Wait for that owner and use the cache it publishes.
            await shield(wrap_future(self._terminal_ready))
            with self._terminal_lock:
                if method in self._terminal:
                    return self._terminal[method]
            # No native value exists when resolution, serialization, or call
            # creation failed. Preserve that authoritative submission error
            # instead of replacing it with the later lifecycle rejection.
            await self._submitted._wait_shielded()
            raise RuntimeError(
                f"The gRPC accessor {method!r} did not return a terminal value."
            )

    def __await__(self) -> Generator[Any, None, Res]:
        """Return an iterator that waits for the RPC result."""

        return self._await_submitted().__await__()

    async def _await_submitted(self) -> Res:
        """Wait for the result and its published terminal state.

        If an external asyncio task is canceled, its shield wrapper is
        canceled first. The explicit call to :meth:`cancel` then sends the
        cancellation to an active native RPC. The method rejects cancellation
        after the native result or error becomes final.

        If the SDK cannot start a task, the submitted future can complete
        before its completion callback publishes the call state. The terminal
        wait keeps :meth:`done` and the result accessors consistent when this
        method returns or raises that error.

        :return: Native RPC result.
        """

        try:
            result = await self._submitted._wait_shielded()
        except CancelledError:
            self.cancel()
            raise
        except BaseException:
            await shield(wrap_future(self._terminal_ready))
            raise
        await shield(wrap_future(self._terminal_ready))
        return result

    def cancel(self) -> bool:
        """Request cancellation of the RPC.

        The method rejects cancellation after the native RPC ends. This rule
        also applies while the wrapper copies terminal metadata on the SDK
        loop.

        :return: ``True`` if the active submission accepted cancellation.
        """

        # Check the process before taking a lock that could have been held by
        # a vanished thread when the process forked.
        self._submitted._check_process()
        with self._terminal_lock:
            if self._native_terminal:
                return False
            self._cancel_requested = True
            # Keep the terminal check and concurrent-future cancellation in
            # one critical section. ``Future.cancel`` runs callbacks inline;
            # the reentrant lock lets the pre-start callback publish status.
            cancelled = self._submitted.cancel()
        if cancelled and self._call is None:
            self._publish_prestart_cancellation()
        return cancelled

    def cancelled(self) -> bool:
        """Return whether the RPC was cancelled."""

        self._submitted._check_process()
        with self._terminal_lock:
            return (
                self._submitted.cancelled()
                or self._native_cancelled
                or (self._terminal.get("code") is StatusCode.CANCELLED)
            )

    def done(self) -> bool:
        """Return whether the RPC is complete."""

        self._submitted._check_process()
        return self._rpc_done.done()

    def time_remaining(self) -> float | None:
        """Return the remaining RPC timeout in seconds."""

        if self._timeout is None:
            return None
        return max(0.0, self._timeout - (monotonic() - self._started_at))

    def add_done_callback(self, callback: Callable[[Any], None]) -> None:
        """Add a function to call when the RPC is complete.

        The callback is scheduled asynchronously on the event loop active at
        registration. If no loop is active, it is scheduled on the SDK loop.

        :param callback: Function that receives this call.
        """

        completion = CrossLoopAwaitable(
            self._rpc_done,
            self._submitted.event_loop,
        )
        completion.add_done_callback(lambda _: callback(self))

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

    def debug_error_string(self) -> str:
        """Return cached native diagnostic details when grpc provides them.

        Async gRPC call objects do not currently define this method, while
        :class:`grpc.aio.AioRpcError` does. The cross-loop wrapper exposes the
        diagnostic for compatibility with callers that inspect both shapes.

        :return: Native debug details after a failed call, or an empty string.
        """

        # Fail before an inherited lock can deadlock a child process.
        self._submitted._check_process()
        with self._terminal_lock:
            return cast(str, self._terminal.get("debug_error_string", ""))

    async def wait_for_connection(self) -> None:
        """Wait until the native call has a connection.

        If channel close rejects a late accessor submission, wait for the
        authoritative call owner. Successful completion proves that a
        connection existed; its native error is otherwise propagated.
        """

        try:
            await self._channel.run_async(self._call_result("wait_for_connection"))
        except ChannelClosedError:
            await shield(wrap_future(self._terminal_ready))
            await self._submitted._wait_shielded()


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


class _ServiceAddressChannel:
    """Resolve and retain one operation-service address on the SDK loop."""

    def __init__(self, channel: "Channel", service_name: str) -> None:
        """Initialize a source-service channel.

        :param channel: SDK channel that owns the transport pool.
        :param service_name: Source service used for deferred address
            resolution.
        """

        self._channel = channel
        self._service_name = service_name
        self._resolved_address: str | None = None

    def _resolve_address(self) -> str:
        """Resolve the source address once and reuse it for this adapter.

        Calls reach this method only from the parent channel's SDK event loop,
        so no additional lock is needed. Failed resolution is not cached and a
        later operation call may retry it.

        :return: Stable transport address for this operation-service adapter.
        """

        if self._resolved_address is None:
            self._resolved_address = self._channel.get_addr_from_service_name(
                self._service_name
            )
        return self._resolved_address

    def unary_unary(
        self,
        method: str,
        request_serializer: SerializingFunction | None = None,
        response_deserializer: DeserializingFunction | None = None,
    ) -> UnaryUnaryMultiCallable[Any, Any]:
        """Return a unary callable routed through the source service.

        :param method: Fully qualified gRPC method name.
        :param request_serializer: Optional request serializer.
        :param response_deserializer: Optional response deserializer.
        :return: Callable that creates a cross-loop unary call.
        """

        channel = self._channel
        address_resolver = self._resolve_address

        class ServiceAddressCallable(UnaryUnaryMultiCallable[Any, Any]):
            """Create cross-loop calls resolved from one source service."""

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
                    None,
                    address_resolver,
                )

        return ServiceAddressCallable()


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


def _get_working_loop() -> AbstractEventLoop:
    """Return the loop that a newly created gRPC AsyncIO channel will use."""
    try:
        return get_running_loop()
    except RuntimeError:
        return get_event_loop()


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
      and closing the channel does not stop or reconfigure it. Its default
      executor is caller-owned too; do not occupy every worker with blocking
      synchronous SDK calls because SDK extensions may need that executor.
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
        shape (sequence of key/value tuples). The constructor copies the
        sequence; later caller mutations do not change channel behavior.
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
        an empty mapping is used. The constructor copies the mapping and each
        option sequence before SDK work can read them on another thread.
    :type address_options: optional mapping address -> list of ``tuple[str, Any]``

    :param address_interceptors:
        Optional mapping from a resolved address to a sequence of
        per-address interceptors. Per-address interceptors are invoked
        in addition to the global interceptors. The constructor copies the
        mapping and each interceptor sequence.
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

        A supplied bearer or provider runs on this channel's SDK event loop.
        Custom implementations must be thread-safe and loop-neutral. Do not
        attach one stateful instance to SDKs with different loops. Create one
        credential object per SDK unless the implementation explicitly
        supports concurrent use and independent close calls.

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
        replace its default executor. The caller must keep it running and
        responsive until close completes. Do not fill its default executor
        with synchronous SDK waits; work running on the loop may need the same
        executor, and the SDK cannot reliably identify arbitrary caller-owned
        executor threads. If omitted, the Channel eagerly starts and owns a
        dedicated daemon loop thread.
    :type event_loop: optional :class:`AbstractEventLoop`

    :param loop_exception_handler:
        Optional synchronous asyncio exception handler installed on the SDK
        event loop. Do not use an ``async def`` function. A synchronous wrapper
        must also return ``None`` instead of a coroutine or another awaitable.
        The SDK rejects directly recognizable async functions. If a
        synchronous handler returns any other value, the SDK closes a newly
        returned, unstarted native coroutine and reports both the original
        context and the contract violation through asyncio's default exception
        handler. It does not change a suspended coroutine, returned Future,
        Task, or opaque awaitable because the handler might not own that work.
        The SDK cannot know whether an invalid handler processed the original
        context, so default reporting can duplicate a diagnostic that the
        handler already emitted.
        The loop calls the handler with the loop and an exception context
        mapping. The handler runs on the loop thread and must return promptly.
        A blocking handler stops all work on that loop. On a supplied
        ``event_loop``, the handler receives diagnostics from SDK work and
        other loop users. It replaces the loop's current handler and remains
        installed after SDK close. It starts receiving diagnostics after all
        other SDK initialization succeeds. It does not automatically call
        asyncio's default handler. A later successful assignment by another
        SDK or component replaces it. The context can contain sensitive data
        and objects owned by the event loop. Read loop-owned objects only on
        that loop. Copy and redact the required immutable fields before another
        thread processes them. Do not log or export the complete context
        without checking its contents. The handler can retain objects that it
        captures until another handler replaces it or the loop closes. Request
        and operation failures continue through their returned awaitables.
        The event loop stores an SDK forwarding callable for the handler, so
        ``get_exception_handler()`` does not have to return the same callable.
        Handler installation is the final SDK initialization action. If an
        asynchronous ``BaseException`` arrives after the loop accepts the
        handler but before the constructor returns, the handler can remain
        installed even though construction did not return a Channel.
        Construction from another thread waits up to 30 seconds for a supplied
        loop to install the handler.
    :type loop_exception_handler: optional callable

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

    @_shutdown_runtime_on_init_failure
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
        loop_exception_handler: LoopExceptionHandler | None = None,
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
        :raises TypeError:
            Raised if ``loop_exception_handler`` is not a synchronous callable.
        :raises RuntimeError:
            Raised if a supplied event loop stops or does not install
            ``loop_exception_handler`` before the time limit.

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

        if loop_exception_handler is not None:
            _validate_loop_exception_handler(loop_exception_handler)

        self._metrics = metrics
        self._auth_metrics = metrics if metrics is not None else auth_metrics
        self._process_id = os.getpid()
        self._runtime = AsyncRuntime(
            event_loop,
            executor_max_workers,
            loop_exception_handler=(
                loop_exception_handler if event_loop is None else None
            ),
        )
        self._event_loop = self._runtime.event_loop
        self._runtime_finalizer = finalize(
            self,
            _finalize_runtime,
            self._runtime,
            self._process_id,
        )
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
        self._transport_closes = dict[
            int,
            tuple[AddressChannel, ConcurrentFuture[None]],
        ]()
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
        self._channel_lifecycle_ready = True
        self._methods = dict[str, str]()
        self._routes = dict[tuple[int, str, str, str], str]()
        self.user_agent = "nebius-python-sdk/" + version
        self.user_agent += f" (python/{sys.version_info.major}.{sys.version_info.minor}"
        self.user_agent += f".{sys.version_info.micro})"

        if user_agent_prefix is not None:
            self.user_agent = f"{user_agent_prefix} {self.user_agent}"

        if interceptors is None:
            interceptors = []
        self._global_options = list(options or ())
        self._global_interceptors: list[ClientInterceptor] = [
            IdempotencyKeyInterceptor()
        ]
        self._global_interceptors.extend(interceptors)

        self._address_options = {
            address: list(address_values)
            for address, address_values in (address_options or {}).items()
        }
        self._address_interceptors = {
            address: tuple(address_values)
            for address, address_values in (address_interceptors or {}).items()
        }

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

        if event_loop is not None and loop_exception_handler is not None:
            self._runtime.set_borrowed_loop_exception_handler(loop_exception_handler)

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

    def _has_authorization_provider(self) -> bool:
        """Return whether requests use this channel's fixed auth provider.

        The query is safe from caller threads because the provider reference is
        fixed during channel construction. It lets cross-loop wrappers decide
        whether an authorization-only deadline applies without constructing an
        authenticator or running authorization work outside the SDK loop.

        :return: ``True`` when the channel has an authorization provider.
        """

        return self._authorization_provider is not None

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

        :param timeout: Maximum time in seconds to wait for a token, including
            dispatch to the SDK loop. If ``None`` the operation may block
            indefinitely according to the bearer semantics.
        :type timeout: optional float
        :param options: Optional mapping of string options passed to the
            underlying token receiver.
        :type options: optional ``dict[str, str]``
        :return: A :class:`Token` instance containing the access token.
        :rtype: :class:`Token`
        :raises ValueError: If ``timeout`` is NaN or infinite. Use ``None`` for
            an unlimited timeout.
        :raises SDKError: If no token bearer was configured on the channel.
        """

        _validate_timeout(timeout, "timeout")
        options_snapshot = None if options is None else dict(options)
        deadline = None if timeout is None else monotonic() + max(timeout, 0)
        return await self._get_token_with_deadline(deadline, options_snapshot)

    async def _get_token_with_deadline(
        self,
        deadline: float | None,
        options: dict[str, str] | None,
    ) -> Token:
        """Fetch a token within a deadline captured on the caller thread.

        :param deadline: Absolute monotonic deadline that includes dispatch to
            the SDK loop, or ``None`` for no limit.
        :param options: Snapshot of the token receiver settings.
        :return: Authorization token.
        :raises TimeoutError: If dispatch or token retrieval exceeds the
            deadline.
        """

        submitted = self.run_async(self._get_token_internal(deadline, options))
        if deadline is None or submitted.done():
            return await submitted
        remaining = deadline - monotonic()
        if remaining <= 0:
            submitted.cancel()
            raise TimeoutError("The token fetch timed out before SDK-loop dispatch.")
        waiter = ensure_future(submitted)
        try:
            return await wait_for(waiter, timeout=remaining)
        except (TimeoutError, AsyncTimeoutError) as error:
            if waiter.done() and not waiter.cancelled():
                terminal_error = waiter.exception()
                if terminal_error is error:
                    raise
            submitted.cancel()
            raise TimeoutError("The token fetch timed out.") from None

    async def _get_token_internal(
        self,
        deadline: float | None,
        options: dict[str, str] | None = None,
    ) -> Token:
        """Get a token on the SDK event loop.

        :param deadline: Absolute monotonic deadline that includes caller-side
            SDK-loop dispatch, or ``None`` for no limit.
        :param options: Optional token receiver settings.
        :return: Authorization token.
        :raises SDKError: If the channel has no token bearer.
        """

        if self._token_bearer is None:
            raise SDKError("The SDK has no token bearer.")
        timeout = None if deadline is None else deadline - monotonic()
        if timeout is not None and timeout <= 0:
            raise TimeoutError("The token fetch timed out before receiver dispatch.")
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
        handoff. The method copies ``options`` before it dispatches work, so a
        later caller-side change does not affect the token request.

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

        _validate_timeout(timeout, "timeout")
        options_snapshot = None if options is None else dict(options)
        deadline = None if timeout is None else monotonic() + max(timeout, 0)
        timeout_sync = timeout
        if timeout_sync is not None:
            timeout_sync += 0.2  # 200 ms for graceful shutdown
        return self.run_sync(
            self._get_token_with_deadline(deadline, options_snapshot),
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

    def _check_process(self, awaitable: Awaitable[Any] | None = None) -> None:
        """Reject a channel inherited from another process before locking.

        After ``fork``, inherited Python locks may be permanently owned by
        vanished threads. gRPC and event-loop state is not reusable. An
        application must fork before it creates SDK or gRPC objects. It must
        create separate SDK objects after each child starts.

        :param awaitable: Optional coroutine to close when rejecting it.
        :raises RuntimeError: If this process did not create the channel.
        """

        if os.getpid() == self._process_id:
            return
        if awaitable is not None:
            dispose_unstarted_awaitable(awaitable)
        raise RuntimeError(
            "You cannot use an SDK channel after a fork. Create SDK objects "
            "after the child process starts."
        )

    def run_async(self, awaitable: Awaitable[T]) -> CrossLoopAwaitable[T]:
        """Submit SDK work to the channel's event loop.

        The returned awaitable is backed by a thread-safe concurrent future,
        so callers can await it from the SDK loop or from an external event
        loop.

        :param awaitable: Work to run on the SDK event loop.
        :return: Cross-loop awaitable for the result.
        :raises ChannelClosedError: If channel close has started.
        """

        self._check_process(awaitable)
        failure: BaseException | None = None
        rejection: ChannelClosedError | None = None
        with self._channel_pool_lock:
            if self._closed:
                rejection = ChannelClosedError("The channel is closed.")
            else:
                # Keep channel-close admission atomic with runtime admission,
                # but defer caller-controlled disposal until this lock is no
                # longer held. Self-submission rejection owns an existing
                # handle and therefore must not dispose it at all.
                self._runtime._reject_self_submission(awaitable)
                try:
                    return self._runtime._submit_without_disposal(awaitable)
                except BaseException as error:
                    failure = error
        dispose_unstarted_awaitable(awaitable)
        if failure is not None:
            raise failure
        if rejection is None:  # pragma: no cover - admission is exhaustive
            raise RuntimeError("The SDK submission failed, but no error was available.")
        raise rejection

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

        return self.run_sync(call())

    def bg_task(self, coro: Awaitable[T]) -> CrossLoopAwaitable[None]:
        """Run an awaitable in the background.

        The channel tracks the returned awaitable and cancels it during
        :meth:`close`. The method logs exceptions other than cancellation.
        The result is not an :class:`asyncio.Task`; wrap it with
        :func:`asyncio.ensure_future` before passing it to
        :func:`asyncio.wait`.

        :param coro: Work to run in the background.
        :return: Cross-loop awaitable that completes after the background work.
        """

        state_lock = Lock()
        started = False
        closed_before_start = False

        async def wrapper() -> None:
            """Claim and run background work unless cancellation closed it."""

            nonlocal started
            with state_lock:
                if closed_before_start:
                    return
                started = True

            try:
                await bridge_awaitable(coro)
            except CancelledError:
                pass
            except Exception as e:
                logger.error(
                    "Channel.bg_task raised an unhandled exception.",
                    exc_info=e,
                )

        wrapped = wrapper()
        try:
            ret = self.run_async(wrapped)
        except BaseException:
            wrapped.close()
            with state_lock:
                closed_before_start = True
                should_close = not started
            if should_close:
                dispose_unstarted_awaitable(coro)
            raise

        def close_unstarted(completed: CrossLoopAwaitable[None]) -> None:
            """Close caller work whenever the wrapper never starts."""

            nonlocal closed_before_start
            with state_lock:
                if started or closed_before_start:
                    return
                closed_before_start = True
            dispose_unstarted_awaitable(coro)

        ret._add_internal_done_callback(close_unstarted)
        with self._tasks_lock:
            self._tasks.add(ret)
        ret._add_internal_done_callback(self._discard_background_task)
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
        event loop and from any other running event loop. Async callers must
        await the cross-loop handle so their loop can continue making
        progress.

        :param awaitable: The awaitable to run to completion.
        :param timeout: Optional maximum wait time in seconds.
        :return: The awaitable's result.
        :raises LoopError: If the caller runs in any asynchronous context or
            is any SDK-owned executor worker.
        :raises ValueError: If ``timeout`` is NaN or infinite. Use ``None`` for
            an unlimited timeout.
        :raises TimeoutError: If the time limit expires.
        """

        self._check_process(awaitable)
        try:
            _validate_timeout(timeout, "timeout")
        except BaseException:
            close_rejected_sync_awaitable(awaitable)
            raise
        if self._runtime.in_executor_thread():
            close_rejected_sync_awaitable(awaitable)
            raise LoopError(
                "An SDK executor worker cannot call the SDK synchronously. "
                "Return to the caller, or use asynchronous SDK work."
            )
        try:
            current_loop = get_running_loop()
        except RuntimeError:
            current_loop = None
        if current_loop is not None:
            close_rejected_sync_awaitable(awaitable)
            if current_loop is self._event_loop:
                raise LoopError(
                    "Code on the SDK event loop cannot call the SDK "
                    "synchronously. Await the SDK handle instead."
                )
            raise LoopError(
                "Code in an asynchronous context cannot call the SDK "
                "synchronously. Await the SDK handle, or use "
                "asyncio.to_thread()."
            )

        return self._runtime.run_sync(awaitable, timeout)

    def sync_close(self, timeout: float | None = None) -> None:
        """Synchronously close the channel and wait for graceful shutdown.

        This method calls :meth:`close` and blocks until shutdown is complete
        or time expires.

        :param timeout: Optional timeout in seconds for the shutdown.
        :type timeout: optional float
        :raises LoopError: If called from the SDK event loop, an asynchronous
            context, or an SDK-owned executor worker.
        :raises ValueError: If ``timeout`` is NaN or infinite. Use ``None`` for
            an unlimited timeout.
        :raises TimeoutError: If the shutdown did not complete within the
            supplied timeout.
        """

        self._check_process()
        _validate_timeout(timeout, "timeout")
        if self._runtime.in_executor_thread():
            raise LoopError(
                "An SDK executor worker cannot close the SDK synchronously. "
                "Start shutdown outside the SDK executor."
            )
        if self._runtime.in_event_loop():
            raise LoopError(
                "The SDK event loop cannot close the SDK synchronously. "
                "Await close() instead."
            )
        try:
            current_loop = get_running_loop()
        except RuntimeError:
            current_loop = None
        if current_loop is not None:
            raise LoopError(
                "An asynchronous context cannot close the SDK synchronously. "
                "Await close() instead."
            )

        deadline = None if timeout is None else monotonic() + timeout

        def remaining() -> float | None:
            """Return the time that remains for shutdown."""

            if deadline is None:
                return None
            return max(0.0, deadline - monotonic())

        def is_terminal_timeout(
            handle: CrossLoopAwaitable[Any],
            error: ConcurrentTimeoutError,
        ) -> bool:
            """Distinguish a stored cleanup error from wait expiration.

            :param handle: Close or shutdown handle being read.
            :param error: Timeout exception raised by ``Future.result``.
            :return: ``True`` only when ``error`` is the handle's own stored
                exception.
            """

            if not handle.done():
                return False
            try:
                terminal_error = handle.exception(timeout=0)
            except ConcurrentCancelledError:
                return False
            return terminal_error is error

        closing = self._get_close_handle(None)
        try:
            closing._result(remaining())
        except ConcurrentTimeoutError as close_error:
            if is_terminal_timeout(closing, close_error):
                shutdown = self._runtime.shutdown_async()
                try:
                    shutdown._result(remaining())
                except BaseException as shutdown_error:
                    raise close_error from shutdown_error
                raise
            closing._add_internal_done_callback(
                lambda _: self._runtime.shutdown_async()
            )
            raise TimeoutError(
                "The SDK did not shut down before the time limit."
            ) from None
        except BaseException as close_error:
            shutdown = self._runtime.shutdown_async()
            try:
                shutdown._result(remaining())
            except BaseException as shutdown_error:
                raise close_error from shutdown_error
            raise

        shutdown = self._runtime.shutdown_async()
        try:
            shutdown._result(remaining())
        except ConcurrentTimeoutError as shutdown_error:
            if is_terminal_timeout(shutdown, shutdown_error):
                raise
            raise TimeoutError(
                "The SDK did not shut down before the time limit."
            ) from None

    async def close(self, grace: float | None = None) -> None:
        """Gracefully close the channel and all associated background work.

        The channel stops supplying address channels. It closes pooled gRPC
        channels and registered ``GracefulInterface`` objects, such as token
        bearers. It cancels tasks from :meth:`bg_task` and logs shutdown
        exceptions. For compatibility, individual resource-close failures are
        best-effort and logged after all cleanup has been attempted; failures
        of the SDK runtime's own finalization are propagated.

        A custom transport can belong to a different caller-owned event loop.
        This method retires that transport and schedules its close on the owner
        loop, but it does not wait for that loop. Keep the owner loop running
        and able to process callbacks until the transport close finishes.

        :param grace: Optional per-transport grace period passed to underlying
            channel close methods.
        :type grace: optional float
        :raises LoopError: If called from an SDK-owned executor worker. Such a
            worker cannot wait for shutdown of the finite pool it belongs to.
        """

        self._check_process()
        if self._runtime.in_executor_thread():
            raise LoopError(
                "An SDK executor worker cannot close the SDK. Start and await "
                "close() outside the SDK executor."
            )
        current_submission = self._runtime.protect_current_submission()
        closing = self._get_close_handle(grace)
        try:
            await shield(closing)
        except BaseException as close_error:
            if isinstance(close_error, CancelledError):
                # On Python 3.10 a Task has no ``cancelling()`` counter.
                # Cancellation can arrive after the task was protected at
                # method entry, so record it while the exception is visible.
                # Runtime shutdown must not inject a second cancellation into
                # the caller's asynchronous finalizer.
                self._runtime.mark_current_task_cancelling()
            if current_submission is None and closing.done():
                try:
                    await shield(self._runtime.shutdown_async())
                except BaseException as shutdown_error:
                    raise close_error from shutdown_error
            elif current_submission is not None:
                self._shutdown_after_internal_caller(
                    current_submission,
                    closing,
                )
                self._runtime.mark_current_submission_close_returning()
            else:
                closing._add_internal_done_callback(
                    lambda _: self._runtime.shutdown_async()
                )
            raise
        if current_submission is None:
            await shield(self._runtime.shutdown_async())
        else:
            self._shutdown_after_internal_caller(
                current_submission,
                closing,
            )
            self._runtime.mark_current_submission_close_returning()

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
            closing._add_internal_done_callback(
                lambda _: self._runtime.shutdown_async()
            )

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
                # Publish the public lifecycle boundary before queueing work.
                # A blocked SDK loop must not leave a window in which another
                # thread can submit work after close has started.
                with self._channel_pool_lock:
                    self._closed = True
                close_work = self._close_internal(grace)
                try:
                    closing = self._runtime.submit(
                        close_work,
                        track=False,
                    )
                except BaseException as error:
                    # Cache the failed close attempt so public close methods
                    # enter their normal error path and still wait for runtime
                    # finalization. AsyncRuntime.submit owns disposal of work
                    # it rejects.
                    failed = ConcurrentFuture[None]()
                    failed.set_exception(error)
                    closing = CrossLoopAwaitable(failed, self._event_loop)
                self._runtime.begin_close()
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
                for channel in channels.values():
                    # Publish retirement while the pool snapshot is locked.
                    # A stale duplicate release cannot schedule a second
                    # native close before this cleanup finishes.
                    channel._retire_by_sdk()
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
                resources = list[tuple[str, Awaitable[Any]]]()
                for chan in channels.values():
                    owner_loop = getattr(chan, "event_loop", None)
                    if owner_loop is not None and owner_loop is not self._event_loop:
                        # A caller-owned loop can remain nominally running
                        # while blocked in synchronous code. Dispatch its
                        # transport close without making SDK shutdown wait for
                        # that loop to resume.
                        self._schedule_address_channel_close(
                            chan,
                            grace,
                            already_retired=True,
                        )
                    else:
                        resources.append(
                            (
                                type(chan.channel).__name__,
                                self._close_address_channel(chan, grace),
                            )
                        )
                for graceful in gracefuls:
                    resource_type = type(graceful).__name__
                    try:
                        close_work = graceful.close(grace)
                    except BaseException as error:
                        logger.error(
                            "The SDK could not start closing the %s resource.",
                            resource_type,
                            exc_info=error,
                        )
                    else:
                        resources.append((resource_type, close_work))
                for task in tasks:
                    task.cancel()
                scheduled: list[tuple[str | None, Task[Any]]] = []

                def schedule_cleanup(
                    awaitable: Awaitable[Any],
                    resource_type: str | None,
                ) -> None:
                    """Schedule cleanup without using the loop's task factory."""

                    async def wait_for_cleanup() -> Any:
                        """Wait for one resource or background task."""

                        return await awaitable

                    wrapper = wait_for_cleanup()
                    try:
                        cleanup_task = Task(wrapper, loop=get_running_loop())
                    except BaseException as error:
                        dispose_unstarted_awaitable(wrapper)
                        dispose_unstarted_awaitable(awaitable)
                        if resource_type is None:
                            logger.error(
                                "The SDK could not wait for a background task "
                                "during shutdown.",
                                exc_info=error,
                            )
                        else:
                            logger.error(
                                "The SDK could not start closing the %s resource.",
                                resource_type,
                                exc_info=error,
                            )
                        return
                    scheduled.append((resource_type, cleanup_task))

                for resource_type, awaitable in resources:
                    schedule_cleanup(awaitable, resource_type)
                for task in tasks:
                    schedule_cleanup(task, None)
                rets = await gather(
                    *(cleanup_task for _, cleanup_task in scheduled),
                    return_exceptions=True,
                )
                for (scheduled_resource_type, _), ret in zip(scheduled, rets):
                    if isinstance(ret, BaseException) and not isinstance(
                        ret,
                        CancelledError,
                    ):
                        if scheduled_resource_type is not None:
                            logger.error(
                                "The SDK could not close the %s resource.",
                                scheduled_resource_type,
                                exc_info=ret,
                            )
                        else:
                            logger.error(
                                "An SDK background task failed during shutdown.",
                                exc_info=ret,
                            )
                with self._channel_pool_lock:
                    for channel_id, address_channel in channels.items():
                        if self._leased_channels.get(channel_id) is address_channel:
                            self._leased_channels.pop(channel_id, None)
                # A request finalizer can publish a transport close after the
                # main cleanup snapshot. Drain registrations until the set is
                # empty, and publish completion under the same lock used to
                # register them. A later registration is then unambiguously a
                # post-close best-effort cleanup.
                while True:
                    with self._tasks_lock:
                        transport_tasks = [
                            wrap_future(transport_completion)
                            for _, transport_completion in (
                                self._transport_closes.values()
                            )
                            if not transport_completion.done()
                        ]
                        if not transport_tasks:
                            completion.set_result(None)
                            break
                    await gather(*transport_tasks, return_exceptions=True)
            except BaseException as error:
                with self._channel_pool_lock:
                    for channel_id, address_channel in channels.items():
                        if self._leased_channels.get(channel_id) is address_channel:
                            self._leased_channels.pop(channel_id, None)
                with self._tasks_lock:
                    completion.set_exception(error)

        # Cleanup already runs in the runtime-protected close submission.
        # Keeping it in that task removes a second task-factory boundary that
        # could otherwise fail after the channel state was snapshotted and
        # leave ``completion`` pending forever.
        self._close_task = current_task()
        await cleanup()
        await shield(wrap_future(completion))

    def get_corresponding_operation_service(
        self,
        service_stub_class: type[ServiceStub],
    ) -> OperationServiceTransportStub:
        """Return an operations service stub for the same address as a
        generated service stub.

        Long-running operations are associated with their source service. This
        method returns an ``OperationServiceStub`` that resolves the generated
        stub's source service on the SDK event loop when its first call starts,
        then reuses that address for the lifetime of the returned adapter.
        Deferring resolution keeps this synchronous factory safe to call from
        asynchronous application code without blocking either event loop;
        retaining it keeps every poll for one operation on the same endpoint.

        :param service_stub_class: Generated gRPC service stub class (the SDK service
            descriptor type).
        :return: An operations service stub bound to the same backend used by
            the provided service.
        :rtype: ``OperationServiceStub``
        """

        service_name = from_stub_class(service_stub_class)
        registry = self._registry_for_service(service_stub_class)
        return OperationServiceTransportStub(
            cast(Any, _ServiceAddressChannel(self, service_name)),
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

        service_name = from_stub_class(service_stub_class)
        registry = self._registry_for_service(service_stub_class)
        return OperationServiceTransportStub(
            cast(Any, _ServiceAddressChannel(self, service_name)),
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
        :raises LoopError: If called from an active event loop or an SDK-owned
            executor worker.
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
        :raises LoopError: If called from an active event loop or an SDK-owned
            executor worker.
        """

        runtime = cast(AsyncRuntime | None, getattr(self, "_runtime", None))
        if runtime is not None and not runtime.in_event_loop():
            return self.run_sync(self._get_addr_from_service_name(service_name))
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
        :raises LoopError: If called from an active event loop or an SDK-owned
            executor worker.
        """

        runtime = cast(AsyncRuntime | None, getattr(self, "_runtime", None))
        if runtime is not None and not runtime.in_event_loop():
            return self.run_sync(self._get_addr_by_method(method_name))
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
            # Keep the established subclass customization point. This method
            # runs on the SDK loop, so the base implementation does not need
            # another cross-loop dispatch.
            self._methods[method_name] = self.get_addr_from_service_name(service_name)
        return self._methods[method_name]

    def get_addr_by_route(self, route: Route) -> str:
        """Resolve immutable generated route metadata without global descriptors.

        :param route: Generated route metadata.
        :return: Resolved address string.
        :raises LoopError: If called from an active event loop or an SDK-owned
            executor worker.
        """
        runtime = cast(AsyncRuntime | None, getattr(self, "_runtime", None))
        if runtime is not None and not runtime.in_event_loop():
            return self.run_sync(self._get_addr_by_route(route))
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
            # Route fallback has always honored public resolver overrides.
            # The base method recognizes the SDK loop and resolves inline.
            address = self.get_addr_from_service_name(route.service)
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
        raise ChannelClosedError("The channel is closed.")

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
        :raises LoopError: If called from an active event loop or an SDK-owned
            executor worker.

        .. warning::
           ``AddressChannel.channel`` is a native ``grpc.aio.Channel`` owned
           by the SDK loop. Direct calls on it are loop-affine. Use generated
           clients or :meth:`unary_unary` for cross-loop call handling.
        """

        self._check_process()
        with self._channel_pool_lock:
            if self._closed:
                raise ChannelClosedError("The channel is closed.")
        if not self._runtime.in_event_loop():
            try:
                return self.run_sync(self._get_channel_by_addr(addr))
            except (RuntimeError, ConcurrentCancelledError):
                with self._channel_pool_lock:
                    if self._closed:
                        raise ChannelClosedError("The channel is closed.") from None
                raise
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
                    raise ChannelClosedError("The channel is closed.")
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
        :raises LoopError: If called from an active event loop or an SDK-owned
            executor worker.
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

    def _release_channel_soon(
        self,
        chan: AddressChannel | None,
        *,
        discard: bool = False,
    ) -> None:
        """Schedule transport release without blocking the caller thread.

        :param chan: Address channel to release. Use ``None`` for no action.
        :param discard: Close the channel instead of returning it to the pool.
        """

        if chan is None:
            return
        state_lock = Lock()
        started = False

        async def release() -> None:
            """Release the transport on the SDK event loop."""

            nonlocal started
            with state_lock:
                started = True
            self._release_address_channel(
                chan,
                discard=discard,
                raise_if_closed=False,
            )

        work = release()
        try:
            submitted = self._runtime.submit(work, track=False)
        except RuntimeError:
            work.close()
            self._schedule_address_channel_close(chan, None)
            return

        def finish_release(completed: CrossLoopAwaitable[None]) -> None:
            """Observe release failure and close work that did not finish."""

            with state_lock:
                did_start = started
            error: BaseException | None = None
            try:
                error = completed.exception(timeout=0)
            except ConcurrentCancelledError as cancelled:
                error = cancelled
            if did_start and error is None:
                return
            if error is not None:
                logger.error(
                    "The SDK could not release the transport.",
                    exc_info=error,
                )
            if chan._is_closed_by_sdk():
                return
            self._schedule_address_channel_close(
                chan,
                None,
                already_retired=chan._is_retired_by_sdk(),
            )

        submitted._add_internal_done_callback(finish_release)

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

        self._check_process()
        if chan is None:
            return
        with self._channel_pool_lock:
            closed = self._closed
            if closed:
                # Before _close_internal takes its snapshot, an actual lease
                # must remain visible to that snapshot. Afterwards the local
                # cleanup snapshot already owns it, so removing the registry
                # entry cannot lose the transport.
                if self._close_completion is None:
                    leased = self._leased_channels.get(id(chan))
                else:
                    leased = self._leased_channels.pop(id(chan), None)
            else:
                leased = None
        if closed:
            already_retired = chan._is_retired_by_sdk()
            if leased is None and not already_retired:
                self._schedule_address_channel_close(chan, None)
            if raise_if_closed:
                raise ChannelClosedError("The channel is closed.")
            return
        if self._runtime.in_event_loop():
            self._release_address_channel(
                chan,
                discard=discard,
                raise_if_closed=raise_if_closed,
            )
            return
        try:
            self.run_sync(
                self._release_address_channel_async(
                    chan,
                    discard=discard,
                    raise_if_closed=raise_if_closed,
                )
            )
        except (RuntimeError, ConcurrentCancelledError):
            with self._channel_pool_lock:
                if not self._closed:
                    raise
            if raise_if_closed:
                raise ChannelClosedError("The channel is closed.") from None

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
        reserved_for_close = False
        with self._channel_pool_lock:
            closed = self._closed
            if closed and self._close_completion is None:
                leased = self._leased_channels.get(id(chan))
            else:
                leased = self._leased_channels.pop(id(chan), None)
            if not closed and discard:
                # Publish retirement while holding the pool lock so a
                # simultaneous duplicate return cannot insert the transport
                # between lease removal and close registration.
                reserved_for_close = chan._retire_by_sdk()
        already_retired = chan._is_retired_by_sdk()
        if closed:
            if leased is None and not already_retired:
                self._schedule_address_channel_close(chan, None)
            if raise_if_closed:
                raise ChannelClosedError("The channel is closed.")
            return
        reusable = (
            not discard
            and not already_retired
            and getattr(chan, "event_loop", None) is self._event_loop
            and chan.channel.get_state() != ChannelConnectivity.SHUTDOWN
        )
        pooled_lease: AddressChannel | None = None
        if reusable:
            try:
                candidate = chan._new_lease()
                valid_candidate = (
                    candidate is not chan
                    and candidate.channel is chan.channel
                    and candidate.address == chan.address
                    and getattr(candidate, "event_loop", None) is self._event_loop
                    and not candidate._is_retired_by_sdk()
                )
                if not valid_candidate:
                    raise ValueError(
                        "The address channel created an invalid pool lease."
                    )
                pooled_lease = candidate
            except BaseException as error:
                logger.error(
                    "The SDK could not create a new transport lease.",
                    exc_info=error,
                )
                reusable = False
        with self._channel_pool_lock:
            closed = self._closed
            candidate_already_tracked = pooled_lease is not None and (
                id(pooled_lease) in self._leased_channels
                or any(
                    pooled_lease is existing
                    for existing in self._free_channels.get(
                        pooled_lease.address,
                        (),
                    )
                )
            )
            if candidate_already_tracked:
                reusable = False
                logger.error(
                    "The transport lease factory returned a lease that the SDK "
                    "already tracks."
                )
            if (
                not closed
                and reusable
                and pooled_lease is not None
                and not chan._is_retired_by_sdk()
            ):
                chans = self._free_channels.setdefault(chan.address, [])
                if any(pooled is chan for pooled in chans):
                    return
                if len(chans) < self._max_free_channels_per_address:
                    chan._retire_by_sdk()
                    chans.append(pooled_lease)
                    return
        self._schedule_address_channel_close(
            chan,
            None,
            already_retired=reserved_for_close,
        )
        if closed and raise_if_closed:
            raise ChannelClosedError("The channel is closed.")

    async def _close_address_channel(
        self,
        chan: AddressChannel,
        grace: float | None,
    ) -> None:
        """Close a pooled transport on its owner loop when that loop is running."""
        owner_loop = getattr(chan, "event_loop", None)
        current_loop = get_running_loop()
        if owner_loop is not None and owner_loop is not current_loop:
            if not owner_loop.is_running():
                logger.warning(
                    "The SDK cannot close the channel because its owner event "
                    "loop stopped."
                )
                return

            async def close_on_owner() -> None:
                """Create and await the native close on its owning loop."""

                await chan.channel.close(grace)

            close_coro = close_on_owner()
            try:
                close_future = run_coroutine_threadsafe(
                    close_coro,
                    owner_loop,
                )
            except RuntimeError:
                close = getattr(close_coro, "close", None)
                if callable(close):
                    close()
                logger.warning(
                    "The SDK could not close the channel after its owner loop "
                    "stopped."
                )
            else:
                # A foreign loop can stop after accepting the callback but
                # before running or finishing it. Poll its liveness so a
                # custom transport cannot strand SDK shutdown indefinitely.
                while not close_future.done():
                    if not owner_loop.is_running():
                        close_future.cancel()
                        logger.warning(
                            "The SDK could not finish the channel close because "
                            "its owner event loop stopped."
                        )
                        return
                    await sleep(0.01)
                if close_future.cancelled():
                    logger.warning(
                        "The SDK could not finish the channel close. Its owner "
                        "event loop stopped or cancelled the close."
                    )
                    return
                await wrap_future(close_future)
                chan._mark_closed_by_sdk()
            return
        await chan.channel.close(grace)
        chan._mark_closed_by_sdk()

    def _schedule_address_channel_close(
        self,
        chan: AddressChannel,
        grace: float | None,
        *,
        already_retired: bool = False,
    ) -> None:
        """Schedule and retain an SDK-loop transport close until it finishes.

        A transport explicitly owned by another loop remains that loop's
        lifecycle responsibility. Its close is dispatched there but is not
        allowed to make SDK shutdown depend on a caller-owned loop.
        """

        with self._channel_pool_lock:
            if not already_retired:
                if not chan._retire_by_sdk():
                    return
            # A direct caller may still hold a wrapper after returning it.
            # Remove any duplicate pool entry atomically with retirement. The
            # caller can retire the wrapper before entering this method, so
            # removal must not depend on this method winning retirement.
            pooled = self._free_channels.get(chan.address)
            if pooled is not None:
                pooled[:] = [candidate for candidate in pooled if candidate is not chan]
                if not pooled:
                    self._free_channels.pop(chan.address, None)

        completion: ConcurrentFuture[None] | None = None

        async def close_and_log() -> None:
            try:
                await self._close_address_channel(chan, grace)
            except CancelledError:
                pass
            except Exception as e:
                logger.error(
                    "The SDK could not close the address channel.",
                    exc_info=e,
                )
            finally:
                if completion is not None and not completion.done():
                    completion.set_result(None)

        owner_loop = getattr(chan, "event_loop", None)
        if owner_loop is not None and owner_loop is not self._event_loop:
            if not owner_loop.is_running():
                logger.warning(
                    "The SDK cannot close the channel because its owner event "
                    "loop stopped."
                )
                return

            async def close_foreign_and_log() -> None:
                """Close without retaining the parent channel on a caller loop."""

                try:
                    await chan.channel.close(grace)
                    chan._mark_closed_by_sdk()
                except CancelledError:
                    pass
                except Exception as error:
                    logger.error(
                        "The SDK could not close the address channel.",
                        exc_info=error,
                    )

            if not _schedule_detached_close_factory(
                close_foreign_and_log,
                cast(AbstractEventLoop, owner_loop),
                "Channel transport close",
            ):
                logger.warning(
                    "The SDK could not close the channel after its owner loop "
                    "stopped."
                )
            return

        channel_id = id(chan)
        completion = ConcurrentFuture()
        with self._tasks_lock:
            if channel_id in self._transport_closes:
                return
            self._transport_closes[channel_id] = (chan, completion)

        def discard(completed: ConcurrentFuture[None]) -> None:
            """Forget this transport only after its close has completed."""

            with self._tasks_lock:
                current = self._transport_closes.get(channel_id)
                if current is not None and current[1] is completed:
                    self._transport_closes.pop(channel_id, None)

        completion.add_done_callback(discard)
        close_coro = close_and_log()
        try:
            scheduled = self._runtime.submit(close_coro, track=False)
        except RuntimeError:
            close_coro.close()
            owner_loop = getattr(chan, "event_loop", None)
            try:
                current_loop = get_running_loop()
            except RuntimeError:
                current_loop = None
            fallback_loop = cast(AbstractEventLoop, owner_loop or self._event_loop)
            if fallback_loop.is_running() and _schedule_detached_close_factory(
                close_and_log,
                fallback_loop,
                "Channel transport close",
                completion,
            ):
                return
            if current_loop is not fallback_loop:
                logger.warning(
                    "The SDK cannot close the channel because its owner event "
                    "loop stopped."
                )
            if not completion.done():
                completion.set_result(None)
            return
        except BaseException:
            close_coro.close()
            if not completion.done():
                completion.set_result(None)
            raise

        def settle_rejected_submission(
            completed: CrossLoopAwaitable[None],
        ) -> None:
            """Release lifecycle completion if the close wrapper never ran.

            A runtime submission can be accepted and then fail when its event
            loop rejects task creation. In that case ``close_and_log`` never
            reaches its ``finally`` block, so the authoritative submission
            handle must settle the parallel transport-close completion.

            :param completed: Authoritative runtime submission handle.
            """

            if completion.done():
                return
            try:
                error = completed.exception(timeout=0)
            except ConcurrentCancelledError as cancelled:
                error = cancelled
            if error is not None:
                logger.error(
                    "The transport close submission failed before cleanup ran.",
                    exc_info=error,
                )
            try:
                completion.set_result(None)
            except ConcurrentInvalidStateError:
                # ``close_and_log`` can publish completion between the check
                # and this setter when task completion callbacks race.
                pass

        scheduled._add_internal_done_callback(settle_rejected_submission)

    def discard_channel(self, chan: AddressChannel | None) -> None:
        """Dispose of an :class:`AddressChannel` by scheduling its close.

        The close is performed asynchronously on the transport's owner loop
        without blocking the caller.

        :param chan: The :class:`AddressChannel` to discard, or ``None``.
        :raises ChannelClosedError: If the SDK channel has been closed.
        :raises LoopError: If called from an active event loop or an SDK-owned
            executor worker.
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
        :raises LoopError: If called from an active event loop or an SDK-owned
            executor worker.
        """

        if not self._runtime.in_event_loop():
            return self.run_sync(self._create_address_channel(addr))
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
        self._check_process()
        with self._channel_pool_lock:
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
        self._check_process()
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
