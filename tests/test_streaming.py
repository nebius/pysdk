from __future__ import annotations

import asyncio

import pytest

from nebius.aio.route import Route
from nebius.aio.stream import StreamRequest


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
