"""Typed-shape async wrappers for generated streaming RPC methods."""

from __future__ import annotations

from asyncio import (
    FIRST_COMPLETED,
    CancelledError,
    Event,
    Lock,
    ensure_future,
    gather,
    get_running_loop,
    wait,
)
from collections.abc import AsyncIterator, Awaitable, Callable, Generator
from contextlib import suppress
from threading import Lock as ThreadLock
from typing import Any, Generic, TypeVar, cast

from grpc import CallCredentials, ChannelConnectivity, Compression
from grpc.aio import Metadata as GrpcMetadata

from nebius.aio.abc import release_address_channel
from nebius.aio.authorization.options import OPTION_TYPE, Types
from nebius.aio.base import AddressChannel
from nebius.aio.idempotency import ensure_key_in_metadata
from nebius.aio.route import Route
from nebius.base.metadata import Metadata

Req = TypeVar("Req")
Res = TypeVar("Res")
T = TypeVar("T")


class StreamRequest(Generic[Req, Res]):
    """Lazy native async call for one of the three streaming RPC shapes.

    Use server streams as async context managers when iteration may stop early::

        async with client.watch(request) as stream:
            async for item in stream:
                if done(item):
                    break

    The context exit calls :meth:`aclose`. This call cancels the native stream
    and releases its address channel.
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
        self._request = request
        self._result_class = result_class
        self._client_streaming = client_streaming
        self._server_streaming = server_streaming
        self._metadata = Metadata(metadata)
        self._timeout = timeout
        self._auth_timeout = auth_timeout
        self._auth_options = auth_options or {}
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
        self._released = False

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
        auth = provider.authenticator()
        authenticating = ensure_future(
            auth.authenticate(
                self._metadata,
                self._auth_timeout,
                self._auth_options,
            )
        )
        cancelled = ensure_future(self._cancel_event.wait())
        try:
            done, _ = await wait(
                (authenticating, cancelled),
                timeout=self._auth_timeout,
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
        if self._call is not None:
            return self._call
        if self._start_error is not None:
            raise self._start_error
        async with self._start_lock:
            if self._call is not None:
                return self._call
            if self._start_error is not None:
                raise self._start_error
            if self._is_cancelled():
                raise CancelledError
            ensure_key_in_metadata(self._metadata)
            await self._authenticate()
            if self._is_cancelled():
                raise CancelledError
            if self._address_channel is None:
                routed = getattr(self._channel, "get_channel_by_route", None)
                if callable(routed):
                    self._address_channel = routed(self._route)
                else:
                    self._address_channel = self._channel.get_channel_by_method(
                        self._route.method_name
                    )
            try:
                transport = self._address_channel.channel
                owner_loop = getattr(self._address_channel, "event_loop", None)
                if owner_loop is not None and owner_loop is not get_running_loop():
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
                self._call = multi(
                    *arguments,
                    timeout=self._timeout,
                    metadata=GrpcMetadata(*self._metadata),
                    credentials=self._credentials,
                    wait_for_ready=self._wait_for_ready,
                    compression=self._compression,
                )
                return self._call
            except BaseException as error:
                self._start_error = error
                self._release(discard=True)
                raise

    def _release(self, *, discard: bool = False) -> None:
        with self._state_lock:
            if self._released or self._address_channel is None:
                return
            address_channel = self._address_channel
            self._released = True
        release_address_channel(
            self._channel,
            address_channel,
            discard=discard,
        )

    def _is_cancelled(self) -> bool:
        with self._state_lock:
            return self._cancelled

    def _is_released(self) -> bool:
        with self._state_lock:
            return self._released

    def _abort(self) -> None:
        with self._state_lock:
            self._cancelled = True
        self._cancel_event.set()
        try:
            if self._call is not None:
                self._call.cancel()
        finally:
            self._release(discard=True)

    async def _on_sdk_loop(self, awaitable: Awaitable[T]) -> T:
        submit = getattr(self._channel, "run_async", None)
        if callable(submit):
            return cast(T, await submit(awaitable))
        return await awaitable

    async def _result(self) -> Res:
        if self._server_streaming:
            raise TypeError("server-streaming RPCs are async iterators")
        return await self._on_sdk_loop(self._result_internal())

    async def _result_internal(self) -> Res:
        call = await self._start()
        try:
            return cast(Res, await call)
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
            async for response in self._responses_internal():
                yield response
            return
        try:
            while True:
                try:
                    response = await submit(self._next_response())
                except StopAsyncIteration:
                    return
                yield response
        finally:
            if not self._is_released():
                with suppress(Exception):
                    await submit(self._aclose())

    async def _responses_internal(self) -> AsyncIterator[Res]:
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
        return self._responses()

    async def write(self, request: Req) -> None:
        await self._on_sdk_loop(self._write(request))

    async def _write(self, request: Req) -> None:
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
        await self._on_sdk_loop(self._aclose())

    async def _aclose(self) -> None:
        self._abort()

    async def __aenter__(self) -> "StreamRequest[Req, Res]":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        await self.aclose()

    def cancel(self) -> bool:
        with self._state_lock:
            if self._cancel_requested or self._cancelled or self._released:
                return False
            self._cancel_requested = True
        submit = getattr(self._channel, "run_async", None)
        if callable(submit):
            closing = self._aclose()
            try:
                submit(closing)
            except Exception:
                closing.close()
                get_state = getattr(self._channel, "get_state", None)
                if callable(get_state) and get_state() == ChannelConnectivity.SHUTDOWN:
                    return False
                with self._state_lock:
                    self._cancel_requested = False
                raise
            return True
        self._abort()
        return True
