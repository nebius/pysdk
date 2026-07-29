from __future__ import annotations

import asyncio
from concurrent.futures import Future, ThreadPoolExecutor
from threading import Barrier, Event, Thread

import grpc
import pytest
from grpc_service import add_service

from nebius.aio.base import AddressChannel
from nebius.aio.channel import Channel, ChannelClosedError, NoCredentials
from nebius.api.nebius.compute.v1 import Disk, DiskServiceClient, GetDiskRequest
from nebius.base.options import INSECURE


def _start_event_loop() -> tuple[asyncio.AbstractEventLoop, Thread]:
    ready = Future[asyncio.AbstractEventLoop]()

    def run() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        ready.set_result(loop)
        loop.run_forever()
        loop.close()

    thread = Thread(target=run, daemon=True)
    thread.start()
    return ready.result(timeout=5), thread


def _stop_event_loop(loop: asyncio.AbstractEventLoop, thread: Thread) -> None:
    loop.call_soon_threadsafe(loop.stop)
    thread.join(timeout=5)
    assert not thread.is_alive()


def test_pooled_channels_are_not_reused_across_event_loops() -> None:
    channel = Channel(
        options=[(INSECURE, True)],
        credentials=NoCredentials(),
    )

    async def checkout_and_return() -> object:
        address_channel = channel.get_channel_by_addr("127.0.0.1:1")
        channel.return_channel(address_channel)
        return address_channel.channel

    try:
        loop_a_channel = asyncio.run(checkout_and_return())
        loop_b_channel = asyncio.run(checkout_and_return())

        assert loop_b_channel is not loop_a_channel
    finally:
        asyncio.run(channel.close())


def test_close_idle_channel_after_its_owner_loop_stops() -> None:
    channel = Channel(
        options=[(INSECURE, True)],
        credentials=NoCredentials(),
    )

    async def checkout_and_return() -> AddressChannel:
        address_channel = channel.get_channel_by_addr("127.0.0.1:1")
        channel.return_channel(address_channel)
        return address_channel

    address_channel = asyncio.run(checkout_and_return())
    assert address_channel.event_loop is not None
    assert address_channel.event_loop.is_closed()

    asyncio.run(channel.close())

    assert address_channel.channel.get_state() == grpc.ChannelConnectivity.SHUTDOWN


def test_generated_requests_use_loop_owned_pooled_channels() -> None:
    class MockDiskService:
        def Get(  # noqa: N802
            self,
            request: GetDiskRequest,
            context: grpc.ServicerContext,
        ) -> Disk:
            ret = Disk()
            ret.metadata.id = request.id
            return ret

    server = grpc.server(ThreadPoolExecutor(max_workers=1))
    add_service(server, DiskServiceClient, MockDiskService())
    port = server.add_insecure_port("127.0.0.1:0")
    server.start()

    loop_a, thread_a = _start_event_loop()
    loop_b, thread_b = _start_event_loop()
    channel = Channel(
        domain=f"localhost:{port}",
        options=[(INSECURE, True)],
        credentials=NoCredentials(),
    )
    client = DiskServiceClient(channel)

    async def get_disk(disk_id: str) -> str:
        ret = await client.get(GetDiskRequest(id=disk_id), timeout=5)
        return ret.metadata.id

    try:
        assert (
            asyncio.run_coroutine_threadsafe(get_disk("loop-a"), loop_a).result(
                timeout=10
            )
            == "loop-a"
        )
        assert (
            asyncio.run_coroutine_threadsafe(get_disk("loop-b"), loop_b).result(
                timeout=10
            )
            == "loop-b"
        )
    finally:
        asyncio.run_coroutine_threadsafe(channel.close(), loop_a).result(timeout=10)
        _stop_event_loop(loop_a, thread_a)
        _stop_event_loop(loop_b, thread_b)
        server.stop(None).wait()


def test_pooled_channels_are_reused_on_the_same_event_loop() -> None:
    channel = Channel(
        options=[(INSECURE, True)],
        credentials=NoCredentials(),
    )

    async def checkout_twice() -> tuple[object, object]:
        first = channel.get_channel_by_addr("127.0.0.1:1")
        channel.return_channel(first)
        second = channel.get_channel_by_addr("127.0.0.1:1")
        channel.return_channel(second)
        return first.channel, second.channel

    try:
        first_channel, second_channel = asyncio.run(checkout_twice())

        assert second_channel is first_channel
    finally:
        asyncio.run(channel.close())


def test_legacy_address_channel_factory_override_is_compatible() -> None:
    class LegacyAddressChannel(AddressChannel):
        def __init__(self, channel: grpc.aio.Channel, address: str) -> None:
            self.channel = channel
            self.address = address

    class LegacyFactoryChannel(Channel):
        def create_address_channel(self, addr: str) -> AddressChannel:
            return LegacyAddressChannel(grpc.aio.insecure_channel(addr), addr)

    channel = LegacyFactoryChannel(credentials=NoCredentials())

    async def checkout_twice() -> tuple[AddressChannel, AddressChannel]:
        first = channel.get_channel_by_addr("127.0.0.1:1")
        channel.return_channel(first)
        second = channel.get_channel_by_addr("127.0.0.1:1")
        channel.return_channel(second)
        return first, second

    try:
        first, second = asyncio.run(checkout_twice())

        assert first.event_loop is not None
        assert second is first
    finally:
        asyncio.run(channel.close())


def test_legacy_constructor_keeps_creation_loop_ownership() -> None:
    address = "127.0.0.1:1"
    loop_a, thread_a = _start_event_loop()
    loop_b, thread_b = _start_event_loop()
    channel = Channel(
        options=[(INSECURE, True)],
        credentials=NoCredentials(),
    )

    async def create_legacy_wrapper() -> AddressChannel:
        return AddressChannel(grpc.aio.insecure_channel(address), address)

    async def return_and_checkout(
        legacy_wrapper: AddressChannel,
    ) -> AddressChannel:
        channel.return_channel(legacy_wrapper)
        return channel.get_channel_by_addr(address)

    try:
        legacy_wrapper = asyncio.run_coroutine_threadsafe(
            create_legacy_wrapper(),
            loop_a,
        ).result(timeout=5)
        checked_out = asyncio.run_coroutine_threadsafe(
            return_and_checkout(legacy_wrapper),
            loop_b,
        ).result(timeout=5)

        assert legacy_wrapper.event_loop is loop_a
        assert checked_out is not legacy_wrapper
        assert checked_out.event_loop is loop_b

        asyncio.run(channel.close())
    finally:
        _stop_event_loop(loop_a, thread_a)
        _stop_event_loop(loop_b, thread_b)


def test_unknown_legacy_wrapper_is_not_pooled_without_a_running_loop() -> None:
    class LegacyAddressChannel(AddressChannel):
        def __init__(self) -> None:
            self.channel = object()  # type: ignore[assignment]
            self.address = "127.0.0.1:1"

    channel = Channel(credentials=NoCredentials())

    try:
        channel.return_channel(LegacyAddressChannel())

        assert channel._free_channels == {}
    finally:
        asyncio.run(channel.close())


def test_discard_on_another_loop_does_not_block_close() -> None:
    class BlockingTransport:
        async def close(self, grace: float | None = None) -> None:
            started.set()
            while not release.is_set():
                await asyncio.sleep(0)
            finished.set()

    started = Event()
    release = Event()
    finished = Event()
    loop, thread = _start_event_loop()
    channel = Channel(credentials=NoCredentials())
    address_channel = AddressChannel(  # type: ignore[arg-type]
        BlockingTransport(),
        "127.0.0.1:1",
        loop,
    )

    async def discard() -> None:
        channel.discard_channel(address_channel)

    try:
        asyncio.run_coroutine_threadsafe(discard(), loop).result(timeout=5)
        assert started.wait(timeout=5)

        asyncio.run(channel.close())

        release.set()
        assert finished.wait(timeout=5)
    finally:
        release.set()
        _stop_event_loop(loop, thread)


def test_pool_limit_remains_global_across_event_loops() -> None:
    address = "127.0.0.1:1"
    channel = Channel(
        options=[(INSECURE, True)],
        credentials=NoCredentials(),
        max_free_channels_per_address=1,
    )

    async def checkout_and_return() -> None:
        address_channel = channel.get_channel_by_addr(address)
        channel.return_channel(address_channel)

    try:
        asyncio.run(checkout_and_return())
        asyncio.run(checkout_and_return())

        assert len(channel._free_channels[address]) == 1
    finally:
        asyncio.run(channel.close())


def test_concurrent_returns_cannot_exceed_pool_limit() -> None:
    address = "127.0.0.1:1"
    channel = Channel(
        options=[(INSECURE, True)],
        credentials=NoCredentials(),
        max_free_channels_per_address=1,
    )
    loop_a, thread_a = _start_event_loop()
    loop_b, thread_b = _start_event_loop()
    barrier = Barrier(2)

    async def checkout() -> AddressChannel:
        return channel.get_channel_by_addr(address)

    async def return_together(address_channel: AddressChannel) -> None:
        barrier.wait(timeout=5)
        channel.return_channel(address_channel)

    try:
        first = asyncio.run_coroutine_threadsafe(checkout(), loop_a).result(timeout=5)
        second = asyncio.run_coroutine_threadsafe(checkout(), loop_b).result(timeout=5)
        returned_a = asyncio.run_coroutine_threadsafe(
            return_together(first),
            loop_a,
        )
        returned_b = asyncio.run_coroutine_threadsafe(
            return_together(second),
            loop_b,
        )

        returned_a.result(timeout=5)
        returned_b.result(timeout=5)
        assert len(channel._free_channels[address]) == 1

        asyncio.run(channel.close())
    finally:
        _stop_event_loop(loop_a, thread_a)
        _stop_event_loop(loop_b, thread_b)


def test_close_closes_a_checked_out_transport() -> None:
    class RecordingTransport:
        def __init__(self) -> None:
            self.close_calls = 0

        def get_state(self) -> grpc.ChannelConnectivity:
            return grpc.ChannelConnectivity.READY

        async def close(self, grace: float | None = None) -> None:
            self.close_calls += 1

    transport = RecordingTransport()

    class RecordingChannel(Channel):
        def create_address_channel(self, addr: str) -> AddressChannel:
            return AddressChannel(transport, addr)  # type: ignore[arg-type]

    async def run() -> None:
        channel = RecordingChannel(credentials=NoCredentials())
        channel.get_channel_by_addr("127.0.0.1:1")

        await channel.close()

    asyncio.run(run())
    assert transport.close_calls == 1


def test_concurrent_close_runs_graceful_cleanup_once() -> None:
    class BlockingGraceful:
        def __init__(self) -> None:
            self.close_calls = 0
            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def close(self, grace: float | None = None) -> None:
            self.close_calls += 1
            self.started.set()
            await self.release.wait()

    async def run() -> int:
        channel = Channel(credentials=NoCredentials())
        graceful = BlockingGraceful()
        channel._gracefuls.add(graceful)
        first = asyncio.create_task(channel.close())
        await graceful.started.wait()
        second = asyncio.create_task(channel.close())
        await asyncio.sleep(0)
        graceful.release.set()
        await asyncio.gather(first, second)
        await channel.close()
        return graceful.close_calls

    assert asyncio.run(run()) == 1


def test_concurrent_close_waits_across_event_loops() -> None:
    class BlockingGraceful:
        def __init__(self) -> None:
            self.close_calls = 0
            self.started = Event()
            self.release = Event()

        async def close(self, grace: float | None = None) -> None:
            self.close_calls += 1
            self.started.set()
            while not self.release.is_set():
                await asyncio.sleep(0)

    loop_a, thread_a = _start_event_loop()
    loop_b, thread_b = _start_event_loop()
    channel = Channel(credentials=NoCredentials())
    graceful = BlockingGraceful()
    channel._gracefuls.add(graceful)

    try:
        first = asyncio.run_coroutine_threadsafe(channel.close(), loop_a)
        assert graceful.started.wait(timeout=5)
        second = asyncio.run_coroutine_threadsafe(channel.close(), loop_b)
        graceful.release.set()

        first.result(timeout=5)
        second.result(timeout=5)
        assert graceful.close_calls == 1
    finally:
        graceful.release.set()
        _stop_event_loop(loop_a, thread_a)
        _stop_event_loop(loop_b, thread_b)


def test_cancelled_close_caller_does_not_cancel_cleanup() -> None:
    class BlockingGraceful:
        def __init__(self) -> None:
            self.close_calls = 0
            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def close(self, grace: float | None = None) -> None:
            self.close_calls += 1
            self.started.set()
            await self.release.wait()

    async def run() -> int:
        channel = Channel(credentials=NoCredentials())
        graceful = BlockingGraceful()
        channel._gracefuls.add(graceful)
        first = asyncio.create_task(channel.close())
        await graceful.started.wait()
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        graceful.release.set()
        await channel.close()
        return graceful.close_calls

    assert asyncio.run(run()) == 1


def test_release_after_close_preserves_direct_api_behavior() -> None:
    class RecordingTransport:
        def __init__(self) -> None:
            self.close_calls = 0

        async def close(self, grace: float | None = None) -> None:
            self.close_calls += 1

    async def run() -> tuple[int, int]:
        channel = Channel(credentials=NoCredentials())
        await channel.close()
        loop = asyncio.get_running_loop()
        internal_transport = RecordingTransport()
        direct_transport = RecordingTransport()
        internal = AddressChannel(  # type: ignore[arg-type]
            internal_transport,
            "127.0.0.1:1",
            loop,
        )
        direct = AddressChannel(  # type: ignore[arg-type]
            direct_transport,
            "127.0.0.1:1",
            loop,
        )

        channel.release_channel(internal)
        with pytest.raises(ChannelClosedError):
            channel.return_channel(direct)
        await asyncio.sleep(0)
        return internal_transport.close_calls, direct_transport.close_calls

    assert asyncio.run(run()) == (1, 1)


def test_release_does_not_close_a_reclaimed_lease_twice() -> None:
    class RecordingTransport:
        def __init__(self) -> None:
            self.close_calls = 0

        def get_state(self) -> grpc.ChannelConnectivity:
            return grpc.ChannelConnectivity.READY

        async def close(self, grace: float | None = None) -> None:
            self.close_calls += 1

    internal_transport = RecordingTransport()
    direct_transport = RecordingTransport()

    class RecordingChannel(Channel):
        def __init__(self) -> None:
            super().__init__(credentials=NoCredentials())
            self.transports = [internal_transport, direct_transport]

        def create_address_channel(self, addr: str) -> AddressChannel:
            return AddressChannel(  # type: ignore[arg-type]
                self.transports.pop(0),
                addr,
            )

    async def run() -> tuple[int, int]:
        channel = RecordingChannel()
        internal = channel.get_channel_by_addr("127.0.0.1:1")
        direct = channel.get_channel_by_addr("127.0.0.1:2")

        await channel.close()

        channel.release_channel(internal)
        with pytest.raises(ChannelClosedError):
            channel.return_channel(direct)
        await asyncio.sleep(0)
        return internal_transport.close_calls, direct_transport.close_calls

    assert asyncio.run(run()) == (1, 1)
