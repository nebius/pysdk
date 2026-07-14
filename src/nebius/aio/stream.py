"""Typed-shape async wrappers for generated streaming RPC methods."""

from __future__ import annotations

from asyncio import (
    FIRST_COMPLETED,
    CancelledError,
    Event,
    Lock,
    ensure_future,
    gather,
    wait,
)
from collections.abc import AsyncIterator, Callable, Generator
from typing import Any, Generic, TypeVar, cast

from grpc import CallCredentials, Compression
from grpc.aio import Metadata as GrpcMetadata

from nebius.aio.authorization.options import OPTION_TYPE, Types
from nebius.aio.base import AddressChannel
from nebius.aio.idempotency import ensure_key_in_metadata
from nebius.aio.route import Route
from nebius.base.metadata import Metadata

Req = TypeVar("Req")
Res = TypeVar("Res")


class StreamRequest(Generic[Req, Res]):
    """Lazy native async call for one of the three streaming RPC shapes.

    Use server streams as async context managers when iteration may stop early::

        async with client.watch(request) as stream:
            async for item in stream:
                if done(item):
                    break

    The context exit calls :meth:`aclose`, cancelling the native stream and
    releasing its address channel deterministically.
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
        self._start_error: BaseException | None = None
        self._start_lock = Lock()
        self._cancel_event = Event()
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
            if self._cancelled:
                raise CancelledError
            ensure_key_in_metadata(self._metadata)
            await self._authenticate()
            if self._cancelled:
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
        if self._released or self._address_channel is None:
            return
        method = "discard_channel" if discard else "return_channel"
        callback = getattr(self._channel, method, None)
        if callable(callback):
            callback(self._address_channel)
        self._released = True

    def _abort(self) -> None:
        self._cancelled = True
        self._cancel_event.set()
        try:
            if self._call is not None:
                self._call.cancel()
        finally:
            self._release(discard=True)

    async def _result(self) -> Res:
        if self._server_streaming:
            raise TypeError("server-streaming RPCs are async iterators")
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
        call = await self._start()
        try:
            async for response in call:
                yield response
        except BaseException:
            self._abort()
            raise
        finally:
            self._release()

    def __aiter__(self) -> AsyncIterator[Res]:
        return self._responses()

    async def write(self, request: Req) -> None:
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
        self._cancelled = True
        self._cancel_event.set()
        if self._call is None:
            return True
        try:
            return bool(self._call.cancel())
        finally:
            self._release(discard=True)
