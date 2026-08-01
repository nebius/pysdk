"""Typed-shape async wrappers for generated streaming RPC methods."""

from __future__ import annotations

import os
from asyncio import (
    FIRST_COMPLETED,
    CancelledError,
    Event,
    Lock,
    ensure_future,
    gather,
    get_running_loop,
    shield,
    wait,
    wait_for,
)
from asyncio import TimeoutError as AsyncTimeoutError
from collections.abc import AsyncIterator, Awaitable, Callable, Generator
from logging import getLogger
from threading import Lock as ThreadLock
from time import monotonic
from typing import Any, Generic, TypeVar, cast

from grpc import CallCredentials, ChannelConnectivity, Compression
from grpc.aio import Metadata as GrpcMetadata

from nebius.aio._task_context import bridge_awaitable, dispose_unstarted_awaitable
from nebius.aio.abc import release_address_channel
from nebius.aio.authorization.options import OPTION_TYPE, Types
from nebius.aio.base import AddressChannel
from nebius.aio.idempotency import ensure_key_in_metadata
from nebius.aio.request import (
    _authorization_deadline_applies,
    _snapshot_request_input,
    _validate_timeout,
)
from nebius.aio.route import Route
from nebius.base.metadata import Metadata

Req = TypeVar("Req")
Res = TypeVar("Res")
T = TypeVar("T")

logger = getLogger(__name__)


class StreamRequest(Generic[Req, Res]):
    """Lazy native async call for one of the three streaming RPC shapes.

    Use server streams as async context managers when iteration may stop early::

        async with client.watch(request) as stream:
            async for item in stream:
                if done(item):
                    break

    The context exit calls :meth:`aclose`. This call cancels the native stream
    and releases its address channel.

    A caller-supplied asynchronous request iterator is consumed on the SDK
    loop. It must not contain state bound to a different event loop. The SDK
    cannot detect hidden loop ownership in an arbitrary iterator.

    A unary request message and authentication options are copied when this
    wrapper is created. Each explicit :meth:`write` copies a supported message
    before dispatch to the SDK loop. Unknown custom values keep their previous
    pass-through behavior and must be safe to share between threads.

    Timeout budgets start with the first stream operation. They include time
    waiting for SDK-loop dispatch, authentication, and the native RPC rather
    than starting only after a queued operation reaches the internal loop. The
    authorization budget applies only when a provider is active and
    authorization is not explicitly disabled.

    :raises ValueError: If ``timeout`` or ``auth_timeout`` is NaN or infinite.
        Use ``None`` for an unlimited timeout.
    """

    def __init__(
        self,
        *,
        channel: Any,
        route: Route,
        request: Any,
        result_class: type[Any],
        client_streaming: bool,
        server_streaming: bool,
        metadata: Metadata | list[tuple[str, str]] | None = None,
        timeout: float | None = None,
        auth_timeout: float | None = None,
        auth_options: dict[str, str] | None = None,
        credentials: CallCredentials | None = None,
        compression: Compression | None = None,
        wait_for_ready: bool | None = True,
        grpc_channel_override: AddressChannel | None = None,
        **unsupported: object,
    ) -> None:
        if not (client_streaming or server_streaming):
            raise ValueError("StreamRequest requires a streaming RPC shape")
        if unsupported:
            name = min(unsupported)
            raise TypeError(f"unsupported streaming request option {name!r}")
        self._channel = channel
        self._route = route
        # A request iterator is stateful and cannot be cloned generically. A
        # unary request, however, must be fixed before it crosses to the SDK
        # loop so caller-side mutation cannot change what is transmitted.
        self._request = (
            request if client_streaming else _snapshot_request_input(request)
        )
        self._result_class = result_class
        self._client_streaming = client_streaming
        self._server_streaming = server_streaming
        self._metadata = Metadata(metadata)
        self._timeout = _validate_timeout(timeout, "timeout")
        self._auth_timeout = _validate_timeout(auth_timeout, "auth_timeout")
        self._auth_options = dict(auth_options or {})
        self._authorization_deadline_enabled = _authorization_deadline_applies(
            channel,
            self._auth_options,
        )
        self._credentials = credentials
        self._compression = compression
        self._wait_for_ready = wait_for_ready
        self._address_channel = grpc_channel_override
        self._call: Any = None
        self._response_iterator: AsyncIterator[Res] | None = None
        self._start_error: BaseException | None = None
        self._start_lock = Lock()
        self._read_lock = Lock()
        self._write_lock = Lock()
        self._cancel_event = Event()
        self._state_lock = ThreadLock()
        self._cancel_requested = False
        self._cancelled = False
        self._native_terminal = False
        self._released = False
        self._owner_loop: Any = None
        self._deadlines_started = False
        self._request_deadline: float | None = None
        self._authorization_deadline: float | None = None
        self._process_id = os.getpid()

    def _check_process(self) -> None:
        """Reject a stream inherited across ``fork`` before taking its locks."""

        if os.getpid() != self._process_id:
            raise RuntimeError(
                "an SDK stream cannot be used after fork; construct SDK "
                "objects only after the child process starts"
            )

    @staticmethod
    def _serialize(message: object) -> bytes:
        serializer = getattr(message, "SerializeToString", None)
        if not callable(serializer):
            raise TypeError(f"unsupported streaming message type {type(message)}")
        return cast(bytes, serializer(deterministic=True))

    async def _authenticate(self) -> None:
        provider_getter = getattr(self._channel, "get_authorization_provider", None)
        provider = provider_getter() if callable(provider_getter) else None
        if provider is None or self._auth_options.get(OPTION_TYPE) == Types.DISABLE:
            return
        # Legacy channels do not expose the caller-safe provider probe used to
        # start an auth deadline before dispatch. Once provider discovery has
        # run on the stream owner loop, restore their historical auth timeout
        # without shortening streams that are unauthenticated or disabled.
        with self._state_lock:
            if not self._authorization_deadline_enabled:
                self._authorization_deadline_enabled = True
                if self._auth_timeout is not None:
                    self._authorization_deadline = monotonic() + max(
                        self._auth_timeout,
                        0,
                    )
        timeout = self._remaining_deadline()
        if timeout is not None and timeout <= 0:
            raise TimeoutError("stream authorization timed out before dispatch")
        auth = provider.authenticator()
        authenticating = ensure_future(
            bridge_awaitable(
                auth.authenticate(
                    self._metadata,
                    timeout,
                    self._auth_options,
                )
            )
        )
        cancelled = ensure_future(self._cancel_event.wait())
        try:
            done, _ = await wait(
                (authenticating, cancelled),
                timeout=timeout,
                return_when=FIRST_COMPLETED,
            )
        except BaseException:
            authenticating.cancel()
            cancelled.cancel()
            await gather(authenticating, cancelled, return_exceptions=True)
            raise
        if self._cancel_event.is_set():
            authenticating.cancel()
            cancelled.cancel()
            await gather(authenticating, cancelled, return_exceptions=True)
            raise CancelledError
        cancelled.cancel()
        if authenticating not in done:
            authenticating.cancel()
            await gather(authenticating, cancelled, return_exceptions=True)
            raise TimeoutError("stream authorization timed out")
        await gather(cancelled, return_exceptions=True)
        await authenticating

    async def _start(self) -> Any:
        current_loop = get_running_loop()
        with self._state_lock:
            if self._owner_loop is None:
                self._owner_loop = current_loop
            elif self._owner_loop is not current_loop:
                raise RuntimeError("stream work belongs to a different event loop")
            current_call = self._call
        if current_call is not None:
            return current_call
        if self._start_error is not None:
            raise self._start_error
        async with self._start_lock:
            with self._state_lock:
                current_call = self._call
            if current_call is not None:
                return current_call
            if self._start_error is not None:
                raise self._start_error
            if self._is_cancelled():
                raise CancelledError
            try:
                ensure_key_in_metadata(self._metadata)
                await self._authenticate()
                if self._is_cancelled():
                    raise CancelledError
            except BaseException as error:
                # An explicit override is already a lease owned by this
                # wrapper. Authentication and metadata setup happen before a
                # native call exists, but must still release that lease.
                self._start_error = error
                try:
                    self._release(discard=isinstance(error, CancelledError))
                except BaseException as release_error:
                    logger.warning(
                        "Failed to release a stream transport after setup failed",
                        exc_info=release_error,
                    )
                raise
            with self._state_lock:
                address_channel = self._address_channel
            if address_channel is None:
                routed = getattr(self._channel, "get_channel_by_route", None)
                if callable(routed):
                    address_channel = routed(self._route)
                else:
                    address_channel = self._channel.get_channel_by_method(
                        self._route.method_name
                    )
                with self._state_lock:
                    publish_address = (
                        not self._cancel_requested
                        and not self._cancelled
                        and not self._released
                    )
                    if publish_address:
                        self._address_channel = address_channel
                if not publish_address:
                    release_address_channel(
                        self._channel,
                        address_channel,
                        discard=True,
                    )
                    raise CancelledError
            try:
                transport = address_channel.channel
                owner_loop = getattr(address_channel, "event_loop", None)
                if owner_loop is not None and owner_loop is not current_loop:
                    raise RuntimeError(
                        "grpc_channel_override belongs to a different event loop"
                    )
                shape = (
                    "stream_stream"
                    if self._client_streaming and self._server_streaming
                    else "stream_unary" if self._client_streaming else "unary_stream"
                )
                multi: Callable[..., Any] = getattr(transport, shape)(
                    f"/{self._route.service}/{self._route.method}",
                    self._serialize,
                    self._result_class.FromString,
                )
                arguments: tuple[object, ...] = (
                    () if self._request is None else (self._request,)
                )
                timeout = self._remaining_deadline()
                if timeout is not None and timeout <= 0:
                    raise TimeoutError("stream timed out before RPC dispatch")
                call = multi(
                    *arguments,
                    timeout=timeout,
                    metadata=GrpcMetadata(*self._metadata),
                    credentials=self._credentials,
                    wait_for_ready=self._wait_for_ready,
                    compression=self._compression,
                )
                with self._state_lock:
                    publish_call = (
                        not self._cancel_requested
                        and not self._cancelled
                        and not self._released
                    )
                    if publish_call:
                        self._call = call
                if not publish_call:
                    call.cancel()
                    raise CancelledError
                add_done_callback = getattr(call, "add_done_callback", None)
                if callable(add_done_callback):
                    add_done_callback(self._mark_native_terminal)
                return call
            except BaseException as error:
                self._start_error = error
                self._release(discard=True)
                raise

    def _release(self, *, discard: bool = False) -> None:
        self._check_process()
        with self._state_lock:
            if self._released or self._address_channel is None:
                return
            address_channel = self._address_channel
            self._released = True
        try:
            release_address_channel(
                self._channel,
                address_channel,
                discard=discard,
            )
        except BaseException:
            # Preserve the one-owner claim during release, but allow a later
            # close/abort path to retry when a custom legacy hook fails.
            with self._state_lock:
                if self._address_channel is address_channel:
                    self._released = False
            raise

    def _is_cancelled(self) -> bool:
        """Return the cancellation state under the state lock."""

        self._check_process()
        with self._state_lock:
            return self._cancel_requested or self._cancelled

    def _mark_native_terminal(self, _: object) -> None:
        """Publish native completion before the stream wrapper resumes."""

        with self._state_lock:
            self._native_terminal = True

    def _cancel_submission_finished(self, completed: Any) -> None:
        """Observe asynchronous cancellation cleanup and restore retryability.

        :param completed: Future-like cancellation submission.
        """

        try:
            error = completed.exception()
        except BaseException as completion_error:
            error = completion_error
        if error is None:
            return
        with self._state_lock:
            if not self._released:
                self._cancel_requested = False
                self._cancelled = False
        logger.warning("Asynchronous stream cancellation failed", exc_info=error)

    def _is_released(self) -> bool:
        """Return the channel-release state under the state lock."""

        self._check_process()
        with self._state_lock:
            return self._released

    def _abort(self) -> None:
        self._check_process()
        with self._state_lock:
            self._cancelled = True
            call = self._call
        self._cancel_event.set()
        try:
            if call is not None:
                call.cancel()
        finally:
            self._release(discard=True)

    def _remaining_deadline(self, *, initialize: bool = False) -> float | None:
        """Return the shared stream deadline remaining in seconds.

        The first caller-side operation fixes monotonic request and
        applicable authorization deadlines under the state lock. Later
        operations reuse those deadlines, so concurrent reads and writes
        cannot each obtain a fresh budget and SDK-loop queueing is charged to
        the same native RPC lifetime.

        :param initialize: Start the deadlines when no prior stream operation
            has done so. Cleanup calls leave this false because they must be
            able to release transport state after a deadline expires.
        :return: The smaller remaining request/authorization budget, or
            ``None`` when both configured limits are infinite.
        """

        now = monotonic()
        with self._state_lock:
            if initialize and not self._deadlines_started:
                self._deadlines_started = True
                self._request_deadline = (
                    None if self._timeout is None else now + max(self._timeout, 0)
                )
                self._authorization_deadline = (
                    None
                    if (
                        self._auth_timeout is None
                        or not self._authorization_deadline_enabled
                    )
                    else now + max(self._auth_timeout, 0)
                )
            deadlines = [
                deadline
                for deadline in (self._request_deadline, self._authorization_deadline)
                if deadline is not None
            ]
        return None if not deadlines else min(deadlines) - now

    async def _on_sdk_loop(
        self,
        awaitable: Awaitable[T],
        *,
        enforce_deadline: bool = True,
    ) -> T:
        """Run an awaitable on the SDK loop when the channel supports dispatch.

        :param awaitable: Stream work to run.
        :param enforce_deadline: Apply the stream's caller-side deadline. Close
            cleanup disables this limit so an expired stream can release its
            transport.
        :return: Result of the stream work.
        """

        self._check_process()
        self._remaining_deadline(initialize=enforce_deadline)
        submit = getattr(self._channel, "run_async", None)
        if callable(submit):
            try:
                operation = submit(awaitable)
            except BaseException:
                dispose_unstarted_awaitable(awaitable)
                try:
                    self._release(discard=True)
                except BaseException as release_error:
                    logger.warning(
                        "Failed to release stream transport after submission "
                        "rejection",
                        exc_info=release_error,
                    )
                raise
        else:
            current_loop = get_running_loop()
            with self._state_lock:
                if self._owner_loop is None:
                    self._owner_loop = current_loop
                elif self._owner_loop is not current_loop:
                    dispose_unstarted_awaitable(awaitable)
                    raise RuntimeError("stream work belongs to a different event loop")
            operation = awaitable
        try:
            if not enforce_deadline:
                return cast(T, await operation)
            # ``run_async`` normally performs only a short, synchronized
            # admission. Recompute from the absolute deadline nevertheless so
            # its elapsed time cannot grant the operation a fresh timeout.
            remaining = self._remaining_deadline()
            if remaining is None:
                return cast(T, await operation)
            if remaining <= 0:
                dispose_unstarted_awaitable(operation)
                self.cancel()
                raise TimeoutError("Stream timed out before SDK-loop dispatch")
            waiter = ensure_future(operation)
            try:
                return cast(T, await wait_for(waiter, timeout=remaining))
            except (TimeoutError, AsyncTimeoutError) as error:
                if waiter.done() and not waiter.cancelled():
                    terminal_error = waiter.exception()
                    if terminal_error is error:
                        raise
                self.cancel()
                raise TimeoutError("Stream timed out") from None
        except CancelledError:
            # The runtime may cancel a queued submission before its wrapper
            # coroutine starts. Establish cancellation and queue transport
            # cleanup from the caller side in that case.
            try:
                self.cancel()
            except BaseException as cleanup_error:
                logger.warning(
                    "Failed to schedule stream cleanup after cancellation",
                    exc_info=cleanup_error,
                )
            raise

    async def _result(self) -> Res:
        if self._server_streaming:
            raise TypeError("server-streaming RPCs are async iterators")
        return await self._on_sdk_loop(self._result_internal())

    async def _result_internal(self) -> Res:
        """Read a unary response and release the leased channel."""

        call = await self._start()
        try:
            try:
                result = await call
            except CancelledError:
                with self._state_lock:
                    native_terminal = self._native_terminal
                if not native_terminal:
                    raise
                result = await shield(call)
            with self._state_lock:
                self._native_terminal = True
            return cast(Res, result)
        except BaseException:
            self._abort()
            raise
        finally:
            self._release()

    def __await__(self) -> Generator[Any, None, Res]:
        return self._result().__await__()

    async def _responses(self) -> AsyncIterator[Res]:
        if not self._server_streaming:
            raise TypeError("stream-unary RPCs are awaitable, not async iterators")
        submit = getattr(self._channel, "run_async", None)
        if not callable(submit):
            self._remaining_deadline(initialize=True)
            async for response in self._responses_internal():
                yield response
            return
        try:
            while True:
                try:
                    response = await self._on_sdk_loop(self._next_response())
                except StopAsyncIteration:
                    return
                yield response
        finally:
            if not self._is_released():
                # Import locally to keep the streaming wrapper independent of
                # the concrete Channel module during module initialization.
                from nebius.aio.channel import ChannelClosedError

                try:
                    await self._on_sdk_loop(
                        self._aclose(),
                        enforce_deadline=False,
                    )
                except ChannelClosedError:
                    # Channel shutdown already owns every snapshotted lease.
                    pass

    async def _responses_internal(self) -> AsyncIterator[Res]:
        """Yield streaming responses directly on the call owner loop."""

        call = await self._start()
        try:
            async for response in call:
                yield response
        except BaseException:
            self._abort()
            raise
        finally:
            self._release()

    async def _next_response(self) -> Res:
        """Read one response while serializing access to the iterator.

        :return: Next streaming response.
        :raises StopAsyncIteration: If the response stream is complete.
        """

        async with self._read_lock:
            if self._response_iterator is None:
                call = await self._start()
                self._response_iterator = call.__aiter__()
            try:
                return await anext(self._response_iterator)
            except StopAsyncIteration:
                self._release()
                raise
            except BaseException:
                self._abort()
                raise

    def __aiter__(self) -> AsyncIterator[Res]:
        self._check_process()
        return self._responses()

    async def write(self, request: Req) -> None:
        """Snapshot and write one request on the SDK event loop.

        :param request: Request message to write. Supported mutable protobuf
            messages are copied before dispatch. Unknown custom values retain
            their historical pass-through behavior and must be thread-safe.
        """

        snapshot = _snapshot_request_input(request)
        await self._on_sdk_loop(self._write(snapshot))

    async def _write(self, request: Req) -> None:
        """Write one request on the call owner loop.

        :param request: Request message to write.
        :raises TypeError: If the RPC does not accept explicit writes.
        """

        async with self._write_lock:
            if not self._client_streaming:
                raise TypeError("RPC does not accept a client stream")
            if self._request is not None:
                raise TypeError("cannot mix a request iterator with write()")
            call = await self._start()
            try:
                await call.write(request)
            except BaseException:
                self._abort()
                raise

    async def done_writing(self) -> None:
        await self._on_sdk_loop(self._done_writing())

    async def _done_writing(self) -> None:
        """Finish explicit request writes on the call owner loop.

        :raises TypeError: If the RPC does not accept explicit writes.
        """

        async with self._write_lock:
            if not self._client_streaming:
                raise TypeError("RPC does not accept a client stream")
            if self._request is not None:
                raise TypeError("request iterators finish their own writes")
            call = await self._start()
            try:
                await call.done_writing()
            except BaseException:
                self._abort()
                raise

    async def aclose(self) -> None:
        """Cancel the native call and discard its address channel."""
        await self._on_sdk_loop(self._aclose(), enforce_deadline=False)

    async def _aclose(self) -> None:
        """Abort the native call and release its leased channel."""

        self._abort()

    async def __aenter__(self) -> "StreamRequest[Req, Res]":
        self._check_process()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        await self.aclose()

    def cancel(self) -> bool:
        """Request cancellation without accessing loop-owned state off-loop.

        SDK channels dispatch cancellation to the SDK loop. A compatibility
        channel without immediate scheduling support—including an adapter
        whose ``run_async`` returns the original one-shot awaitable—uses the
        loop that started the stream instead. A foreign caller receives
        ``False`` if that owner loop is not running or closes during dispatch;
        it may retry after restoring the loop. As with every accepted
        event-loop callback, the owner must remain running long enough to
        execute it. A later asynchronous cleanup failure is logged and makes
        cancellation retryable when the transport was not released.

        :return: ``True`` if native cancellation was applied or accepted for
            dispatch; otherwise ``False``. A terminal server stream returns
            ``False`` even when its remaining lease cleanup was scheduled.
        """

        self._check_process()
        with self._state_lock:
            if self._cancel_requested or self._cancelled or self._released:
                return False
            native_terminal = self._native_terminal
            # A terminal stream-unary call still has one authoritative result
            # owner that releases its lease after wrapper finalization. A
            # server stream can instead be terminal while buffered responses
            # leave its iterator and lease open; cancel() must clean that
            # lease even though native cancellation is no longer accepted.
            if native_terminal and not self._server_streaming:
                return False
            self._cancel_requested = True
            cancellation_accepted = not native_terminal
        submit = getattr(self._channel, "run_async", None)
        if callable(submit):
            closing = self._aclose()
            try:
                scheduled = submit(closing)
            except BaseException as error:
                closing.close()
                try:
                    self._release(discard=True)
                except BaseException as release_error:
                    logger.warning(
                        "Failed to release stream transport after cancellation "
                        "submission rejection",
                        exc_info=release_error,
                    )
                with self._state_lock:
                    self._cancel_requested = False
                if isinstance(error, Exception):
                    get_state = getattr(self._channel, "get_state", None)
                    if (
                        callable(get_state)
                        and get_state() == ChannelConnectivity.SHUTDOWN
                    ):
                        return False
                raise
            # SDK channels return an already-scheduled Future-like handle.
            # Constant and other legacy adapters can instead return the same
            # one-shot awaitable unchanged. Dispose that unscheduled wrapper
            # and use the stream's recorded owner loop below.
            if callable(getattr(scheduled, "done", None)):
                observe = getattr(scheduled, "_add_internal_done_callback", None)
                if not callable(observe):
                    observe = getattr(scheduled, "add_done_callback", None)
                if callable(observe):
                    observe(self._cancel_submission_finished)
                return cancellation_accepted
            dispose = getattr(scheduled, "close", None)
            if callable(dispose):
                dispose()
            if scheduled is not closing:
                closing.close()
        with self._state_lock:
            owner_loop = self._owner_loop
        try:
            current_loop = get_running_loop()
        except RuntimeError:
            current_loop = None
        if owner_loop is None or owner_loop is current_loop:
            self._abort()
            return cancellation_accepted
        if owner_loop.is_running():
            try:
                owner_loop.call_soon_threadsafe(self._abort)
            except RuntimeError:
                pass
            else:
                return cancellation_accepted
        with self._state_lock:
            if not self._cancelled and not self._released:
                self._cancel_requested = False
        return False
