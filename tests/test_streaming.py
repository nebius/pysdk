from __future__ import annotations

import asyncio
from threading import Barrier, Event, Thread

import pytest

from nebius.aio.channel import Channel as SDKChannel
from nebius.aio.channel import NoCredentials
from nebius.aio.route import Route
from nebius.aio.stream import StreamRequest


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
