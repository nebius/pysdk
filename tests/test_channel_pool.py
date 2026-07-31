from __future__ import annotations

import asyncio
from concurrent.futures import Future, ThreadPoolExecutor
from threading import Barrier, Event, Thread
from time import sleep

import grpc
import pytest
from grpc_service import add_service

from nebius.aio.base import AddressChannel
from nebius.aio.channel import Channel, ChannelClosedError, LoopError, NoCredentials
from nebius.api.nebius.common.v1 import (
    GetOperationRequest,
    Operation,
    OperationServiceClient,
)
from nebius.api.nebius.compute.v1 import Disk, DiskServiceClient, GetDiskRequest
from nebius.base.options import INSECURE
from nebius.base.resolver import Resolver


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


async def _checkout(channel: Channel, address: str) -> AddressChannel:
    """Use the explicit async boundary for low-level pool test access."""

    return await asyncio.to_thread(channel.get_channel_by_addr, address)


def test_pooled_channels_are_reused_through_the_internal_loop() -> None:
    channel = Channel(
        options=[(INSECURE, True)],
        credentials=NoCredentials(),
    )

    async def checkout_and_return() -> object:
        address_channel = await _checkout(channel, "127.0.0.1:1")
        await asyncio.to_thread(channel.return_channel, address_channel)
        return address_channel.channel

    try:
        loop_a_channel = asyncio.run(checkout_and_return())
        loop_b_channel = asyncio.run(checkout_and_return())

        assert loop_b_channel is loop_a_channel
    finally:
        asyncio.run(channel.close())


def test_idle_channel_is_owned_by_the_internal_loop_until_close() -> None:
    channel = Channel(
        options=[(INSECURE, True)],
        credentials=NoCredentials(),
    )

    async def checkout_and_return() -> AddressChannel:
        address_channel = await _checkout(channel, "127.0.0.1:1")
        await asyncio.to_thread(channel.return_channel, address_channel)
        return address_channel

    address_channel = asyncio.run(checkout_and_return())
    assert address_channel.event_loop is not None
    assert address_channel.event_loop.is_running()

    asyncio.run(channel.close())

    assert address_channel.channel.get_state() == grpc.ChannelConnectivity.SHUTDOWN


def test_direct_pool_release_rejects_active_external_loop() -> None:
    """Synchronous release helpers must not block an asyncio loop."""

    channel = Channel(
        options=[(INSECURE, True)],
        credentials=NoCredentials(),
    )

    async def exercise() -> None:
        returned = await _checkout(channel, "127.0.0.1:1")
        with pytest.raises(LoopError, match="not allowed inside an async context"):
            channel.return_channel(returned)
        await asyncio.to_thread(channel.return_channel, returned)

        discarded = await _checkout(channel, "127.0.0.1:2")
        with pytest.raises(LoopError, match="not allowed inside an async context"):
            channel.discard_channel(discarded)
        await asyncio.to_thread(channel.discard_channel, discarded)

    try:
        asyncio.run(exercise())
    finally:
        channel.sync_close(timeout=5)


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


def test_low_level_unary_call_and_terminal_status_cross_external_loops() -> None:
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
    call = channel.unary_unary(
        "/nebius.compute.v1.DiskService/Get",
        lambda request: request.SerializeToString(),
        Disk.FromString,
    )(GetDiskRequest(id="cross-loop"))

    async def await_call() -> Disk:
        return await call

    try:
        result = asyncio.run_coroutine_threadsafe(await_call(), loop_a).result(
            timeout=5
        )
        assert result.metadata.id == "cross-loop"
        assert call.debug_error_string() == ""

        channel.sync_close(timeout=5)

        assert (
            asyncio.run_coroutine_threadsafe(call.code(), loop_b).result(timeout=5)
            == grpc.StatusCode.OK
        )
        assert (
            asyncio.run_coroutine_threadsafe(call.details(), loop_b).result(timeout=5)
            == ""
        )
        assert (
            asyncio.run_coroutine_threadsafe(
                call.initial_metadata(),
                loop_b,
            ).result(timeout=5)
            is not None
        )
        assert (
            asyncio.run_coroutine_threadsafe(
                call.trailing_metadata(),
                loop_b,
            ).result(timeout=5)
            is not None
        )
    finally:
        if channel.get_state() != grpc.ChannelConnectivity.SHUTDOWN:
            channel.sync_close(timeout=5)
        _stop_event_loop(loop_a, thread_a)
        _stop_event_loop(loop_b, thread_b)
        server.stop(None).wait()


def test_low_level_unary_call_snapshots_request_and_metadata() -> None:
    observed: list[tuple[str, str]] = []

    class MockDiskService:
        def Get(  # noqa: N802
            self,
            request: GetDiskRequest,
            context: grpc.ServicerContext,
        ) -> Disk:
            metadata = dict(context.invocation_metadata())
            observed.append((request.id, metadata["x-scope"]))
            return Disk()

    server = grpc.server(ThreadPoolExecutor(max_workers=1))
    add_service(server, DiskServiceClient, MockDiskService())
    port = server.add_insecure_port("127.0.0.1:0")
    server.start()
    channel = Channel(
        domain=f"localhost:{port}",
        options=[(INSECURE, True)],
        credentials=NoCredentials(),
    )
    loop_entered = Event()
    unblock_loop = Event()

    async def block_sdk_loop() -> None:
        loop_entered.set()
        unblock_loop.wait(timeout=5)

    blocker = channel.run_async(block_sdk_loop())
    assert loop_entered.wait(timeout=5)
    request = GetDiskRequest(id="before")
    metadata = [("x-scope", "before")]
    call = channel.unary_unary(
        "/nebius.compute.v1.DiskService/Get",
        lambda value: value.SerializeToString(),
        Disk.FromString,
    )(request, metadata=metadata)
    request.id = "after"
    metadata[0] = ("x-scope", "after")

    async def await_call() -> Disk:
        return await call

    try:
        unblock_loop.set()
        blocker.result(timeout=5)
        asyncio.run(await_call())
        assert observed == [("before", "before")]
    finally:
        unblock_loop.set()
        channel.sync_close(timeout=5)
        server.stop(None).wait()


def test_low_level_unary_call_caches_debug_error_string() -> None:
    class MockDiskService:
        def Get(  # noqa: N802
            self,
            request: GetDiskRequest,
            context: grpc.ServicerContext,
        ) -> Disk:
            context.abort(grpc.StatusCode.INTERNAL, "boom")

    server = grpc.server(ThreadPoolExecutor(max_workers=1))
    add_service(server, DiskServiceClient, MockDiskService())
    port = server.add_insecure_port("127.0.0.1:0")
    server.start()
    channel = Channel(
        domain=f"localhost:{port}",
        options=[(INSECURE, True)],
        credentials=NoCredentials(),
    )
    call = channel.unary_unary(
        "/nebius.compute.v1.DiskService/Get",
        lambda value: value.SerializeToString(),
        Disk.FromString,
    )(GetDiskRequest(id="failure"))

    async def await_call() -> Disk:
        return await call

    try:
        with pytest.raises(grpc.aio.AioRpcError) as raised:
            asyncio.run(await_call())
        native_debug = raised.value.debug_error_string()
        assert native_debug
        assert call.debug_error_string() == native_debug
    finally:
        channel.sync_close(timeout=5)
        server.stop(None).wait()


@pytest.mark.asyncio
async def test_operation_service_factory_defers_and_executes_resolution() -> None:
    """An async caller can create and invoke a source-routed operation stub."""

    class MockOperationService:
        def Get(  # noqa: N802
            self,
            request: GetOperationRequest,
            context: grpc.ServicerContext,
        ) -> Operation:
            return Operation(id=request.id)

    server = grpc.server(ThreadPoolExecutor(max_workers=1))
    add_service(server, OperationServiceClient, MockOperationService())
    port = server.add_insecure_port("127.0.0.1:0")
    server.start()
    channel = Channel(
        domain=f"localhost:{port}",
        options=[(INSECURE, True)],
        credentials=NoCredentials(),
    )

    try:
        transport = channel.get_corresponding_operation_service(DiskServiceClient)
        response = await transport.Get(GetOperationRequest(id="deferred-resolution"))
        assert response.id == "deferred-resolution"
    finally:
        await channel.close()
        server.stop(None).wait()


@pytest.mark.asyncio
async def test_operation_service_adapter_retains_first_resolved_address() -> None:
    """Successive operation calls stay on the adapter's first endpoint."""

    class AlternatingResolver(Resolver):
        def __init__(self, first_address: str) -> None:
            self._first_address = first_address
            self.calls = 0

        def resolve(self, service_id: str) -> str:
            self.calls += 1
            if self.calls == 1:
                return self._first_address
            return "127.0.0.1:1"

    class MockOperationService:
        def Get(  # noqa: N802
            self,
            request: GetOperationRequest,
            context: grpc.ServicerContext,
        ) -> Operation:
            return Operation(id=request.id)

    server = grpc.server(ThreadPoolExecutor(max_workers=1))
    add_service(server, OperationServiceClient, MockOperationService())
    port = server.add_insecure_port("127.0.0.1:0")
    server.start()
    resolver = AlternatingResolver(f"localhost:{port}")
    channel = Channel(
        resolver=resolver,
        options=[(INSECURE, True)],
        credentials=NoCredentials(),
    )

    try:
        transport = channel.get_corresponding_operation_service(DiskServiceClient)
        first = await transport.Get(GetOperationRequest(id="first"))
        second = await transport.Get(GetOperationRequest(id="second"))
        assert first.id == "first"
        assert second.id == "second"
        assert resolver.calls == 1
    finally:
        await channel.close()
        server.stop(None).wait()


def test_stopped_foreign_loop_transport_close_is_not_queued(caplog) -> None:
    """Discard reports an unreachable owner loop instead of queuing forever."""

    close_called = Event()

    class Transport:
        async def close(self, grace: float | None = None) -> None:
            close_called.set()

    owner_loop = asyncio.new_event_loop()
    channel = Channel(credentials=NoCredentials())
    address_channel = AddressChannel(  # type: ignore[arg-type]
        Transport(),
        "127.0.0.1:1",
        owner_loop,
    )
    try:
        channel.discard_channel(address_channel)
        assert not close_called.is_set()
        assert "owner event loop is stopped" in caplog.text
    finally:
        channel.sync_close(timeout=5)
        owner_loop.close()


def test_channel_close_does_not_duplicate_a_scheduled_transport_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Shutdown awaits the published close instead of starting another one."""

    submit_blocked = Event()
    release_submit = Event()
    close_calls: list[float | None] = []
    errors: list[BaseException] = []

    class Transport:
        async def close(self, grace: float | None = None) -> None:
            close_calls.append(grace)
            await asyncio.sleep(0.05)

    channel = Channel(credentials=NoCredentials())
    address_channel = AddressChannel(  # type: ignore[arg-type]
        Transport(),
        "127.0.0.1:1",
        channel._event_loop,
    )
    original_submit = channel._runtime.submit
    first_submission = True

    def pause_first_submission(awaitable, *, track=True):
        nonlocal first_submission
        pause = first_submission
        first_submission = False
        if pause:
            submit_blocked.set()
            release_submit.wait(timeout=5)
        return original_submit(awaitable, track=track)

    monkeypatch.setattr(channel._runtime, "submit", pause_first_submission)
    scheduler = Thread(
        target=channel._schedule_address_channel_close,
        args=(address_channel, None),
    )
    scheduler.start()
    assert submit_blocked.wait(timeout=5)

    def close() -> None:
        try:
            channel.sync_close(timeout=5)
        except BaseException as error:
            errors.append(error)

    closer = Thread(target=close)
    closer.start()
    try:
        for _ in range(100):
            if channel._close_completion is not None:
                break
            sleep(0.01)
        assert channel._close_completion is not None
        sleep(0.05)
    finally:
        release_submit.set()
        scheduler.join(timeout=5)
        closer.join(timeout=5)

    assert not scheduler.is_alive()
    assert not closer.is_alive()
    assert errors == []
    assert close_calls == [None]


def test_generated_requests_complete_from_many_sync_threads() -> None:
    class MockDiskService:
        def Get(  # noqa: N802
            self,
            request: GetDiskRequest,
            context: grpc.ServicerContext,
        ) -> Disk:
            ret = Disk()
            ret.metadata.id = request.id
            return ret

    server = grpc.server(ThreadPoolExecutor(max_workers=4))
    add_service(server, DiskServiceClient, MockDiskService())
    port = server.add_insecure_port("127.0.0.1:0")
    server.start()
    channel = Channel(
        domain=f"localhost:{port}",
        options=[(INSECURE, True)],
        credentials=NoCredentials(),
    )
    client = DiskServiceClient(channel)
    barrier = Barrier(11)
    results: list[str] = []

    def call(index: int) -> None:
        barrier.wait()
        result = client.get(GetDiskRequest(id=str(index)), timeout=5).wait()
        results.append(result.metadata.id)

    threads = [Thread(target=call, args=(index,)) for index in range(10)]
    try:
        for thread in threads:
            thread.start()
        barrier.wait()
        for thread in threads:
            thread.join(timeout=10)
            assert not thread.is_alive()
        assert sorted(results, key=int) == [str(index) for index in range(10)]
    finally:
        channel.sync_close(timeout=5)
        server.stop(0).wait()


def test_pooled_channels_are_reused_on_the_same_event_loop() -> None:
    channel = Channel(
        options=[(INSECURE, True)],
        credentials=NoCredentials(),
    )

    async def checkout_twice() -> tuple[object, object]:
        first = await _checkout(channel, "127.0.0.1:1")
        await asyncio.to_thread(channel.return_channel, first)
        second = await _checkout(channel, "127.0.0.1:1")
        await asyncio.to_thread(channel.return_channel, second)
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
        first = await _checkout(channel, "127.0.0.1:1")
        await asyncio.to_thread(channel.return_channel, first)
        second = await _checkout(channel, "127.0.0.1:1")
        await asyncio.to_thread(channel.return_channel, second)
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
        await asyncio.to_thread(channel.return_channel, legacy_wrapper)
        return await _checkout(channel, address)

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
        assert checked_out.event_loop is channel._event_loop

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
        await asyncio.to_thread(channel.discard_channel, address_channel)

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
        address_channel = await _checkout(channel, address)
        await asyncio.to_thread(channel.return_channel, address_channel)

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
        return await _checkout(channel, address)

    async def return_together(address_channel: AddressChannel) -> None:
        barrier.wait(timeout=5)
        await asyncio.to_thread(channel.return_channel, address_channel)

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

    async def run() -> Channel:
        channel = RecordingChannel(credentials=NoCredentials())
        await _checkout(channel, "127.0.0.1:1")

        await channel.close()
        return channel

    channel = asyncio.run(run())
    assert transport.close_calls == 1
    assert channel._leased_channels == {}


def test_concurrent_close_runs_graceful_cleanup_once() -> None:
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

    async def run() -> int:
        channel = Channel(credentials=NoCredentials())
        graceful = BlockingGraceful()
        channel._gracefuls.add(graceful)
        first = asyncio.create_task(channel.close())
        while not graceful.started.is_set():
            await asyncio.sleep(0)
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
            self.started = Event()
            self.release = Event()

        async def close(self, grace: float | None = None) -> None:
            self.close_calls += 1
            self.started.set()
            while not self.release.is_set():
                await asyncio.sleep(0)

    async def run() -> int:
        channel = Channel(credentials=NoCredentials())
        graceful = BlockingGraceful()
        channel._gracefuls.add(graceful)
        first = asyncio.create_task(channel.close())
        while not graceful.started.is_set():
            await asyncio.sleep(0)
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


@pytest.mark.parametrize("borrowed", [False, True])
def test_close_drains_scheduled_unpooled_transport(borrowed: bool) -> None:
    """SDK close waits for retained transport cleanup on its own loop."""

    started = Event()
    release = Event()
    close_entered = Event()
    close_done = Event()
    errors: list[BaseException] = []
    loop: asyncio.AbstractEventLoop | None = None
    loop_thread: Thread | None = None
    if borrowed:
        loop, loop_thread = _start_event_loop()
    channel = Channel(credentials=NoCredentials(), event_loop=loop)

    class SlowTransport:
        async def close(self, grace: float | None = None) -> None:
            started.set()
            while not release.is_set():
                await asyncio.sleep(0.01)

    address_channel = AddressChannel(  # type: ignore[arg-type]
        SlowTransport(),
        "127.0.0.1:1",
        channel._event_loop,
    )
    channel.discard_channel(address_channel)
    assert started.wait(timeout=5)

    def close() -> None:
        try:
            close_entered.set()
            channel.sync_close(timeout=5)
        except BaseException as error:
            errors.append(error)
        finally:
            close_done.set()

    closer = Thread(target=close)
    closer.start()
    assert close_entered.wait(timeout=5)
    assert not close_done.wait(timeout=0.1)
    release.set()
    closer.join(timeout=5)

    assert not closer.is_alive()
    assert errors == []
    if loop is not None and loop_thread is not None:
        _stop_event_loop(loop, loop_thread)


def test_get_close_dispatch_race_raises_channel_closed() -> None:
    """A close that wins after the pool check keeps the pool exception type."""

    channel = Channel(credentials=NoCredentials())
    entered = Event()
    resume = Event()
    original_run_sync = channel._runtime.run_sync
    errors: list[BaseException] = []

    def paused_run_sync(awaitable: object, timeout: float | None = None) -> object:
        entered.set()
        resume.wait(timeout=5)
        return original_run_sync(awaitable, timeout)  # type: ignore[arg-type]

    channel._runtime.run_sync = paused_run_sync  # type: ignore[method-assign]

    def checkout() -> None:
        try:
            channel.get_channel_by_addr("127.0.0.1:1")
        except BaseException as error:
            errors.append(error)

    worker = Thread(target=checkout)
    worker.start()
    assert entered.wait(timeout=5)
    channel.sync_close(timeout=5)
    resume.set()
    worker.join(timeout=5)

    assert not worker.is_alive()
    assert len(errors) == 1
    assert isinstance(errors[0], ChannelClosedError)


def test_return_close_dispatch_race_raises_channel_closed() -> None:
    """Direct return preserves ChannelClosedError when close wins dispatch."""

    channel = Channel(
        options=[(INSECURE, True)],
        credentials=NoCredentials(),
    )
    address_channel = channel.get_channel_by_addr("127.0.0.1:1")
    entered = Event()
    resume = Event()
    original_run_sync = channel._runtime.run_sync
    errors: list[BaseException] = []

    def paused_run_sync(awaitable: object, timeout: float | None = None) -> object:
        entered.set()
        resume.wait(timeout=5)
        return original_run_sync(awaitable, timeout)  # type: ignore[arg-type]

    channel._runtime.run_sync = paused_run_sync  # type: ignore[method-assign]

    def return_channel() -> None:
        try:
            channel.return_channel(address_channel)
        except BaseException as error:
            errors.append(error)

    worker = Thread(target=return_channel)
    worker.start()
    assert entered.wait(timeout=5)
    channel.sync_close(timeout=5)
    resume.set()
    worker.join(timeout=5)

    assert not worker.is_alive()
    assert len(errors) == 1
    assert isinstance(errors[0], ChannelClosedError)


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
        internal = await _checkout(channel, "127.0.0.1:1")
        direct = await _checkout(channel, "127.0.0.1:2")

        await channel.close()

        channel.release_channel(internal)
        with pytest.raises(ChannelClosedError):
            channel.return_channel(direct)
        await asyncio.sleep(0)
        return internal_transport.close_calls, direct_transport.close_calls

    assert asyncio.run(run()) == (1, 1)
