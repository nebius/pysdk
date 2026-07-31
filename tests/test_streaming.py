from __future__ import annotations

import asyncio
from concurrent.futures import Future
from threading import Barrier, Event, Thread

import pytest

from nebius.aio.channel import Channel as SDKChannel
from nebius.aio.channel import NoCredentials
from nebius.aio.route import Route
from nebius.aio.stream import StreamRequest
from nebius.api.nebius.compute.v1 import Disk, GetDiskRequest


def test_concurrent_stream_cancel_racing_sdk_close_is_boolean_and_atomic() -> None:
    class Result:
        @classmethod
        def FromString(cls, data):  # noqa: N802
            return cls()

    channel = SDKChannel(credentials=NoCredentials())
    stream = StreamRequest(
        channel=channel,
        route=Route("acme.Service", "Watch"),
        request=object(),
        result_class=Result,
        client_streaming=False,
        server_streaming=True,
    )
    barrier = Barrier(11)
    results: list[bool] = []
    errors: list[BaseException] = []

    def cancel() -> None:
        barrier.wait()
        try:
            results.append(stream.cancel())
        except BaseException as error:
            errors.append(error)

    def close() -> None:
        barrier.wait()
        channel.sync_close(timeout=5)

    threads = [Thread(target=cancel) for _ in range(10)]
    threads.append(Thread(target=close))
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)
        assert not thread.is_alive()

    assert errors == []
    assert sum(results) <= 1


def test_sdk_stream_cancel_during_route_resolution_never_opens_transport() -> None:
    """Accepted cross-thread cancellation prevents native call creation."""

    resolver_entered = Event()
    release_resolver = Event()
    call_factory_used = Event()
    discarded: list[object] = []
    errors: list[BaseException] = []

    class Transport:
        def unary_stream(self, path, serializer, deserializer):
            call_factory_used.set()
            raise AssertionError("cancelled stream must not open a transport")

    channel = SDKChannel(credentials=NoCredentials())
    address = type(
        "Address",
        (),
        {"channel": Transport(), "event_loop": channel._event_loop},
    )()

    def resolve(route):
        resolver_entered.set()
        release_resolver.wait(timeout=5)
        return address

    channel.get_channel_by_route = resolve  # type: ignore[method-assign]
    channel.release_channel = (  # type: ignore[method-assign]
        lambda value, *, discard=False: discarded.append(value)
    )
    stream = StreamRequest(
        channel=channel,
        route=Route("acme.Service", "Watch"),
        request=GetDiskRequest(id="before"),
        result_class=Disk,
        client_streaming=False,
        server_streaming=True,
    )

    def consume() -> None:
        async def first_response() -> None:
            await anext(stream.__aiter__())

        try:
            asyncio.run(first_response())
        except BaseException as error:
            errors.append(error)

    thread = Thread(target=consume)
    thread.start()
    assert resolver_entered.wait(timeout=5)
    try:
        assert stream.cancel()
    finally:
        release_resolver.set()
        thread.join(timeout=5)
        channel.sync_close(timeout=5)

    assert not thread.is_alive()
    assert len(errors) == 1
    assert isinstance(errors[0], asyncio.CancelledError)
    assert not call_factory_used.is_set()
    assert discarded == [address]


def test_stream_snapshots_unary_request_and_auth_options() -> None:
    """Stream setup observes values fixed before caller-side mutation."""

    received_requests: list[str] = []
    received_options: list[str] = []
    discarded: list[object] = []

    class Authenticator:
        async def authenticate(self, metadata, timeout, options):
            received_options.append(options["scope"])

    class Provider:
        def authenticator(self):
            return Authenticator()

    class Call:
        def __aiter__(self):
            async def responses():
                yield Disk()

            return responses()

        def cancel(self) -> bool:
            return True

    class Transport:
        def unary_stream(self, path, serializer, deserializer):
            def create(request, **kwargs):
                received_requests.append(request.id)
                return Call()

            return create

    channel = SDKChannel(credentials=NoCredentials())
    address = type(
        "Address",
        (),
        {"channel": Transport(), "event_loop": channel._event_loop},
    )()
    channel.get_authorization_provider = lambda: Provider()  # type: ignore[method-assign]
    channel.get_channel_by_route = lambda route: address  # type: ignore[method-assign]
    channel.release_channel = (  # type: ignore[method-assign]
        lambda value, *, discard=False: discarded.append(value)
    )
    source = GetDiskRequest(id="before")
    options = {"scope": "before"}
    stream = StreamRequest(
        channel=channel,
        route=Route("acme.Service", "Watch"),
        request=source,
        result_class=Disk,
        client_streaming=False,
        server_streaming=True,
        auth_options=options,
    )
    source.id = "after"
    options["scope"] = "after"

    async def consume() -> None:
        async with stream:
            assert isinstance(await anext(stream.__aiter__()), Disk)

    try:
        asyncio.run(consume())
    finally:
        channel.sync_close(timeout=5)

    assert received_requests == ["before"]
    assert received_options == ["before"]
    assert discarded == [address]


def test_sdk_stream_bridges_foreign_loop_authenticator_future() -> None:
    """Streaming auth accepts a Future owned by another running loop."""

    auth_ready: Future[tuple[asyncio.AbstractEventLoop, asyncio.Future[None]]] = (
        Future()
    )

    def run_auth_loop() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        auth_ready.set_result((loop, loop.create_future()))
        loop.run_forever()
        loop.close()

    auth_thread = Thread(target=run_auth_loop, daemon=True)
    auth_thread.start()
    auth_loop, auth_future = auth_ready.result(timeout=5)
    auth_started = Event()
    opened = Event()

    class Authenticator:
        def authenticate(
            self,
            metadata: object,
            timeout: float | None,
            options: object,
        ) -> asyncio.Future[None]:
            auth_started.set()
            return auth_future

    class Provider:
        def authenticator(self) -> Authenticator:
            return Authenticator()

    class Call:
        def __aiter__(self):
            async def responses():
                yield Disk()

            return responses()

        def cancel(self) -> bool:
            return True

    class Transport:
        def unary_stream(self, path, serializer, deserializer):
            def create(request, **kwargs):
                opened.set()
                return Call()

            return create

    channel = SDKChannel(credentials=NoCredentials())
    address = type(
        "Address",
        (),
        {"channel": Transport(), "event_loop": channel._event_loop},
    )()
    channel.get_authorization_provider = lambda: Provider()  # type: ignore[method-assign]
    channel.get_channel_by_route = lambda route: address  # type: ignore[method-assign]
    channel.release_channel = lambda value, *, discard=False: None  # type: ignore[method-assign]
    stream = StreamRequest(
        channel=channel,
        route=Route("acme.Service", "Watch"),
        request=GetDiskRequest(id="foreign-auth"),
        result_class=Disk,
        client_streaming=False,
        server_streaming=True,
    )

    def complete_authentication() -> None:
        assert auth_started.wait(timeout=5)
        auth_loop.call_soon_threadsafe(auth_future.set_result, None)

    completion_thread = Thread(target=complete_authentication)
    completion_thread.start()

    async def consume() -> None:
        async with stream:
            assert isinstance(await anext(stream.__aiter__()), Disk)

    try:
        asyncio.run(consume())
        completion_thread.join(timeout=5)
        assert not completion_thread.is_alive()
        assert opened.is_set()
    finally:
        channel.sync_close(timeout=5)
        auth_loop.call_soon_threadsafe(auth_loop.stop)
        auth_thread.join(timeout=5)
        assert not auth_thread.is_alive()


def test_stream_write_snapshots_request_before_sdk_loop_dispatch() -> None:
    """Explicit writes cannot observe mutation while the SDK loop is busy."""

    loop_blocked = Event()
    release_loop = Event()
    received: list[str] = []
    discarded: list[object] = []

    class Call:
        async def write(self, request) -> None:
            received.append(request.id)

        def cancel(self) -> bool:
            return True

    call = Call()

    class Transport:
        def stream_unary(self, path, serializer, deserializer):
            return lambda **kwargs: call

    channel = SDKChannel(credentials=NoCredentials())
    address = type(
        "Address",
        (),
        {"channel": Transport(), "event_loop": channel._event_loop},
    )()
    channel.get_channel_by_route = lambda route: address  # type: ignore[method-assign]
    channel.release_channel = (  # type: ignore[method-assign]
        lambda value, *, discard=False: discarded.append(value)
    )

    async def block_sdk_loop() -> None:
        loop_blocked.set()
        release_loop.wait(timeout=5)

    blocker = channel.run_async(block_sdk_loop())
    assert loop_blocked.wait(timeout=5)
    stream = StreamRequest(
        channel=channel,
        route=Route("acme.Service", "Upload"),
        request=None,
        result_class=Disk,
        client_streaming=True,
        server_streaming=False,
    )
    source = GetDiskRequest(id="before")

    async def write_then_mutate() -> None:
        writing = asyncio.create_task(stream.write(source))
        await asyncio.sleep(0)
        source.id = "after"
        release_loop.set()
        await writing
        await stream.aclose()

    try:
        asyncio.run(write_then_mutate())
        blocker.result(timeout=5)
    finally:
        release_loop.set()
        channel.sync_close(timeout=5)

    assert received == ["before"]
    assert discarded == [address]


@pytest.mark.parametrize("closes_during_dispatch", [False, True])
def test_legacy_stream_cancel_stopped_dispatch_is_retryable(
    closes_during_dispatch: bool,
) -> None:
    class Result:
        @classmethod
        def FromString(cls, data):  # noqa: N802
            return cls()

    class OwnerLoop:
        def __init__(self) -> None:
            self.running = closes_during_dispatch
            self.fail_dispatch = closes_during_dispatch
            self.callbacks = []

        def is_running(self) -> bool:
            return self.running

        def call_soon_threadsafe(self, callback) -> None:
            if self.fail_dispatch:
                raise RuntimeError("event loop is closed")
            self.callbacks.append(callback)

    stream = StreamRequest(
        channel=object(),
        route=Route("acme.Service", "Watch"),
        request=object(),
        result_class=Result,
        client_streaming=False,
        server_streaming=True,
    )
    owner_loop = OwnerLoop()
    stream._owner_loop = owner_loop

    assert stream.cancel() is False
    assert stream.cancel() is False
    owner_loop.running = True
    owner_loop.fail_dispatch = False
    assert stream.cancel() is True
    assert len(owner_loop.callbacks) == 1


def test_legacy_stream_rejects_a_second_loop_before_write_lock() -> None:
    write_entered = Event()
    release_write = Event()
    errors: list[BaseException] = []
    discarded: list[object] = []

    class Call:
        async def write(self, request) -> None:
            write_entered.set()
            await asyncio.to_thread(release_write.wait)

        def cancel(self) -> bool:
            return True

    call = Call()

    class Transport:
        def stream_unary(self, path, serializer, deserializer):
            return lambda **kwargs: call

    class Address:
        channel = Transport()

    address = Address()

    class Channel:
        def get_channel_by_route(self, route):
            return address

        def discard_channel(self, value):
            discarded.append(value)

    class Result:
        @classmethod
        def FromString(cls, data):  # noqa: N802
            return cls()

    stream = StreamRequest(
        channel=Channel(),
        route=Route("acme.Service", "Upload"),
        request=None,
        result_class=Result,
        client_streaming=True,
        server_streaming=False,
    )

    def first_loop() -> None:
        async def run() -> None:
            try:
                await stream.write(object())
            finally:
                await stream.aclose()

        try:
            asyncio.run(run())
        except BaseException as error:
            errors.append(error)

    thread = Thread(target=first_loop)
    thread.start()
    assert write_entered.wait(timeout=5)
    try:
        with pytest.raises(RuntimeError, match="different event loop"):
            asyncio.run(stream.write(object()))
    finally:
        release_write.set()
        thread.join(timeout=5)
    assert not thread.is_alive()
    assert errors == []
    assert discarded == [address]


@pytest.mark.asyncio
async def test_cancel_during_authentication_never_opens_transport() -> None:
    entered = asyncio.Event()
    resume = asyncio.Event()
    opened: list[Route] = []

    class Authenticator:
        async def authenticate(self, metadata, timeout, options):
            entered.set()
            await resume.wait()

    class Provider:
        def authenticator(self):
            return Authenticator()

    class Channel:
        def get_authorization_provider(self):
            return Provider()

        def get_channel_by_route(self, route):
            opened.append(route)
            raise AssertionError("cancelled stream must not resolve a channel")

    class Result:
        @classmethod
        def FromString(cls, data):  # noqa: N802
            return cls()

    stream = StreamRequest(
        channel=Channel(),
        route=Route("acme.Service", "Watch"),
        request=object(),
        result_class=Result,
        client_streaming=False,
        server_streaming=True,
    )
    iteration = stream.__aiter__()
    pending = asyncio.create_task(anext(iteration))
    await entered.wait()

    assert stream.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(pending, 0.1)
    assert opened == []


@pytest.mark.asyncio
async def test_reentrant_resolver_cancellation_discards_unpublished_address() -> None:
    cancelled: list[bool] = []
    discarded: list[object] = []

    class Transport:
        def unary_stream(self, path, serializer, deserializer):
            raise AssertionError("cancelled stream must not create a call")

    class Address:
        channel = Transport()

    address = Address()

    class Channel:
        def get_channel_by_route(self, route):
            cancelled.append(stream.cancel())
            return address

        def discard_channel(self, value):
            discarded.append(value)

    class Result:
        @classmethod
        def FromString(cls, data):  # noqa: N802
            return cls()

    stream = StreamRequest(
        channel=Channel(),
        route=Route("acme.Service", "Watch"),
        request=object(),
        result_class=Result,
        client_streaming=False,
        server_streaming=True,
    )

    with pytest.raises(asyncio.CancelledError):
        await anext(stream.__aiter__())
    assert cancelled == [True]
    assert discarded == [address]


@pytest.mark.asyncio
async def test_reentrant_call_factory_cancels_unpublished_call() -> None:
    cancelled: list[bool] = []
    call_cancellations: list[bool] = []
    discarded: list[object] = []

    class Call:
        def cancel(self) -> bool:
            call_cancellations.append(True)
            return True

    call = Call()

    class Transport:
        def unary_stream(self, path, serializer, deserializer):
            def create(*args, **kwargs):
                cancelled.append(stream.cancel())
                return call

            return create

    class Address:
        channel = Transport()

    address = Address()

    class Channel:
        def get_channel_by_route(self, route):
            return address

        def discard_channel(self, value):
            discarded.append(value)

    class Result:
        @classmethod
        def FromString(cls, data):  # noqa: N802
            return cls()

    stream = StreamRequest(
        channel=Channel(),
        route=Route("acme.Service", "Watch"),
        request=object(),
        result_class=Result,
        client_streaming=False,
        server_streaming=True,
    )

    with pytest.raises(asyncio.CancelledError):
        await anext(stream.__aiter__())
    assert cancelled == [True]
    assert call_cancellations == [True]
    assert discarded == [address]


@pytest.mark.asyncio
async def test_start_failure_discards_acquired_channel() -> None:
    address = object()
    discarded: list[object] = []

    class Channel:
        def get_channel_by_route(self, route):
            class Address:
                channel = object()

            nonlocal address
            address = Address()
            return address

        def discard_channel(self, value):
            discarded.append(value)

    class Result:
        @classmethod
        def FromString(cls, data):  # noqa: N802
            return cls()

    stream = StreamRequest(
        channel=Channel(),
        route=Route("acme.Service", "Watch"),
        request=object(),
        result_class=Result,
        client_streaming=False,
        server_streaming=True,
    )

    with pytest.raises(AttributeError):
        await anext(stream.__aiter__())
    with pytest.raises(AttributeError):
        await anext(stream.__aiter__())
    assert discarded == [address]


@pytest.mark.asyncio
async def test_cancelled_write_aborts_call_and_discards_channel() -> None:
    entered = asyncio.Event()
    cancelled: list[bool] = []
    discarded: list[object] = []

    class Call:
        async def write(self, request):
            entered.set()
            await asyncio.Event().wait()

        def cancel(self):
            cancelled.append(True)
            return True

    call = Call()

    class Transport:
        def stream_unary(self, path, serializer, deserializer):
            return lambda **kwargs: call

    class Address:
        channel = Transport()

    address = Address()

    class Channel:
        def get_channel_by_route(self, route):
            return address

        def discard_channel(self, value):
            discarded.append(value)

    class Result:
        @classmethod
        def FromString(cls, data):  # noqa: N802
            return cls()

    stream = StreamRequest(
        channel=Channel(),
        route=Route("acme.Service", "Upload"),
        request=None,
        result_class=Result,
        client_streaming=True,
        server_streaming=False,
    )
    writing = asyncio.create_task(stream.write(object()))
    await entered.wait()
    writing.cancel()
    with pytest.raises(asyncio.CancelledError):
        await writing

    assert cancelled == [True]
    assert discarded == [address]


@pytest.mark.asyncio
async def test_context_manager_closes_server_stream_after_early_break() -> None:
    cancelled: list[bool] = []
    discarded: list[object] = []

    class Call:
        def __aiter__(self):
            async def responses():
                yield Result()
                await asyncio.Event().wait()

            return responses()

        def cancel(self):
            cancelled.append(True)
            return True

    class Transport:
        def unary_stream(self, path, serializer, deserializer):
            return lambda *args, **kwargs: Call()

    class Address:
        channel = Transport()

    address = Address()

    class Channel:
        def get_channel_by_route(self, route):
            return address

        def discard_channel(self, value):
            discarded.append(value)

    class Result:
        @classmethod
        def FromString(cls, data):  # noqa: N802
            return cls()

    stream = StreamRequest(
        channel=Channel(),
        route=Route("acme.Service", "Watch"),
        request=object(),
        result_class=Result,
        client_streaming=False,
        server_streaming=True,
    )
    async with stream:
        async for _ in stream:
            break

    assert cancelled == [True]
    assert discarded == [address]


def test_failed_stream_release_can_be_retried() -> None:
    """A failing custom release hook must leave a later close retryable."""

    release_calls = 0
    successful_releases = 0

    class Channel:
        def release_channel(self, address, *, discard=False) -> None:
            nonlocal release_calls, successful_releases
            release_calls += 1
            if release_calls == 1:
                raise RuntimeError("release failed")
            successful_releases += 1

    class Call:
        def cancel(self) -> bool:
            return True

    stream = StreamRequest(
        channel=Channel(),
        route=Route("acme.Service", "Watch"),
        request=object(),
        result_class=object,
        client_streaming=False,
        server_streaming=True,
    )
    address = object()
    stream._address_channel = address  # type: ignore[assignment]
    stream._call = Call()

    with pytest.raises(RuntimeError, match="release failed"):
        stream._release()
    assert not stream._released

    asyncio.run(stream.aclose())
    assert stream._released
    assert release_calls == 2
    assert successful_releases == 1
