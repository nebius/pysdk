from __future__ import annotations

import asyncio
import gc
import inspect
from collections.abc import Coroutine
from concurrent.futures import Future, ThreadPoolExecutor
from threading import Barrier, Event, Lock, Thread
from time import monotonic, sleep
from typing import Any
from weakref import ref

import grpc
import nebius.aio.channel as channel_module
import pytest
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

from .grpc_service import add_service


def _start_event_loop() -> tuple[asyncio.AbstractEventLoop, Thread]:
    ready = Future[asyncio.AbstractEventLoop]()

    def run() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        ready.set_result(loop)
        loop.run_forever()
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
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
        user_agent_prefix="nebius-python-sdk-tests/1.0",
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


def test_stale_wrapper_cannot_release_a_reused_transport() -> None:
    """A stale wrapper cannot reclaim or close the current transport lease."""
    channel = Channel(
        user_agent_prefix="nebius-python-sdk-tests/1.0",
        options=[(INSECURE, True)],
        credentials=NoCredentials(),
    )
    first = channel.get_channel_by_addr("127.0.0.1:1")
    channel.return_channel(first)
    second = channel.get_channel_by_addr("127.0.0.1:1")
    try:
        assert second is not first
        assert second.channel is first.channel
        channel.discard_channel(first)
        with channel._channel_pool_lock:
            assert channel._leased_channels.get(id(second)) is second
            assert all(pooled is not second for pooled in channel._free_channels.get(second.address, ()))
        assert not second._is_retired_by_sdk()
    finally:
        channel.return_channel(second)
        channel.sync_close(timeout=5)


def test_failed_lease_factory_closes_untracked_transport(caplog) -> None:
    """A failed fresh-lease factory closes the removed native transport."""
    closed = Event()

    class Transport:
        def get_state(self) -> grpc.ChannelConnectivity:
            """Report a reusable native transport."""
            return grpc.ChannelConnectivity.READY

        async def close(self, grace: float | None = None) -> None:
            """Record deterministic cleanup after lease creation fails."""
            closed.set()

    class BrokenLease(AddressChannel):
        def _new_lease(self) -> AddressChannel:
            """Reject creation of a new wrapper generation."""
            raise RuntimeError("The test rejected the new transport lease.")

    class TestChannel(Channel):
        def create_address_channel(self, addr: str) -> AddressChannel:
            """Create a wrapper with a failing lease factory."""
            return BrokenLease(Transport(), addr, self._event_loop)  # type: ignore[arg-type]

    channel = TestChannel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    address = channel.get_channel_by_addr("broken-lease.example:443")
    try:
        channel.return_channel(address)
        assert closed.wait(timeout=5)
        with channel._channel_pool_lock:
            assert id(address) not in channel._leased_channels
            assert channel._free_channels.get(address.address, []) == []
        assert "The SDK could not create a new transport lease." in caplog.text
    finally:
        channel.sync_close(timeout=5)


def test_legacy_address_channel_with_only_lifecycle_lock_is_safe() -> None:
    """Lazy lifecycle setup fills fields that a legacy subclass omitted."""
    address = object.__new__(AddressChannel)
    address._close_state_lock = Lock()

    assert not address._is_retired_by_sdk()
    assert not address._is_closed_by_sdk()
    assert address._retire_by_sdk()
    assert address._is_retired_by_sdk()


def test_lease_factory_cannot_reuse_a_tracked_wrapper(caplog) -> None:
    """A lease factory cannot put a tracked wrapper in the free pool."""
    closed = Event()

    class Transport:
        def get_state(self) -> grpc.ChannelConnectivity:
            """Report a reusable native transport."""
            return grpc.ChannelConnectivity.READY

        async def close(self, grace: float | None = None) -> None:
            """Record cleanup of the wrapper that the pool removed."""
            closed.set()

    transport = Transport()
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    tracked = AddressChannel(  # type: ignore[arg-type]
        transport,
        "tracked-lease.example:443",
        channel._event_loop,
    )

    class ReusedLease(AddressChannel):
        def _new_lease(self) -> AddressChannel:
            """Return a wrapper that another caller already owns."""
            return tracked

    returned = ReusedLease(  # type: ignore[arg-type]
        transport,
        tracked.address,
        channel._event_loop,
    )
    channel._lease_address_channel(tracked)
    channel._lease_address_channel(returned)
    try:
        channel.return_channel(returned)
        assert closed.wait(timeout=5)
        with channel._channel_pool_lock:
            assert channel._leased_channels.get(id(tracked)) is tracked
            assert id(returned) not in channel._leased_channels
            assert all(pooled is not tracked for pooled in channel._free_channels.get(tracked.address, ()))
        assert ("The transport lease factory returned a lease that the SDK already tracks.") in caplog.text
    finally:
        channel.sync_close(timeout=5)


def test_idle_channel_is_owned_by_the_internal_loop_until_close() -> None:
    channel = Channel(
        user_agent_prefix="nebius-python-sdk-tests/1.0",
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


def test_constructor_snapshots_mutable_channel_configuration() -> None:
    """Caller mutation cannot race SDK-loop option and interceptor reads."""
    global_options = [("global", "before")]
    address_values = [("address", "before")]
    address_options = {"snapshot.example:443": address_values}
    first_interceptor = object()
    later_interceptor = object()
    address_interceptor_values = [first_interceptor]
    address_interceptors = {
        "snapshot.example:443": address_interceptor_values,
    }
    channel = Channel(
        user_agent_prefix="nebius-python-sdk-tests/1.0",
        credentials=NoCredentials(),
        options=global_options,
        address_options=address_options,
        address_interceptors=address_interceptors,  # type: ignore[arg-type]
    )
    global_options.append(("global", "after"))
    address_values.append(("address", "after"))
    address_options.clear()
    address_interceptor_values.append(later_interceptor)
    address_interceptors.clear()
    try:
        effective_options = channel.get_address_options("snapshot.example:443")
        assert ("global", "before") in effective_options
        assert ("address", "before") in effective_options
        assert ("global", "after") not in effective_options
        assert ("address", "after") not in effective_options
        effective_interceptors = channel.get_address_interceptors("snapshot.example:443")
        assert first_interceptor in effective_interceptors
        assert later_interceptor not in effective_interceptors
    finally:
        channel.sync_close(timeout=5)


def test_direct_pool_release_rejects_active_external_loop() -> None:
    """Synchronous release helpers must not block an asyncio loop."""
    channel = Channel(
        user_agent_prefix="nebius-python-sdk-tests/1.0",
        options=[(INSECURE, True)],
        credentials=NoCredentials(),
    )

    async def exercise() -> None:
        returned = await _checkout(channel, "127.0.0.1:1")
        with pytest.raises(LoopError, match="asynchronous context cannot"):
            channel.return_channel(returned)
        await asyncio.to_thread(channel.return_channel, returned)

        discarded = await _checkout(channel, "127.0.0.1:2")
        with pytest.raises(LoopError, match="asynchronous context cannot"):
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
        user_agent_prefix="nebius-python-sdk-tests/1.0",
        domain=f"localhost:{port}",
        options=[(INSECURE, True)],
        credentials=NoCredentials(),
    )
    client = DiskServiceClient(channel)

    async def get_disk(disk_id: str) -> str:
        ret = await client.get(GetDiskRequest(id=disk_id), timeout=5)
        return ret.metadata.id

    try:
        assert asyncio.run_coroutine_threadsafe(get_disk("loop-a"), loop_a).result(timeout=10) == "loop-a"
        assert asyncio.run_coroutine_threadsafe(get_disk("loop-b"), loop_b).result(timeout=10) == "loop-b"
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
        user_agent_prefix="nebius-python-sdk-tests/1.0",
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
        result = asyncio.run_coroutine_threadsafe(await_call(), loop_a).result(timeout=5)
        assert result.metadata.id == "cross-loop"
        assert call.debug_error_string() == ""

        channel.sync_close(timeout=5)

        asyncio.run_coroutine_threadsafe(
            call.wait_for_connection(),
            loop_b,
        ).result(timeout=5)
        assert asyncio.run_coroutine_threadsafe(call.code(), loop_b).result(timeout=5) == grpc.StatusCode.OK
        assert asyncio.run_coroutine_threadsafe(call.details(), loop_b).result(timeout=5) == ""
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
        user_agent_prefix="nebius-python-sdk-tests/1.0",
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
        user_agent_prefix="nebius-python-sdk-tests/1.0",
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


@pytest.mark.asyncio()
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
        user_agent_prefix="nebius-python-sdk-tests/1.0",
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


@pytest.mark.asyncio()
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
        user_agent_prefix="nebius-python-sdk-tests/1.0",
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
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    address_channel = AddressChannel(  # type: ignore[arg-type]
        Transport(),
        "127.0.0.1:1",
        owner_loop,
    )
    try:
        channel.discard_channel(address_channel)
        assert not close_called.is_set()
        assert "owner event loop stopped" in caplog.text
    finally:
        channel.sync_close(timeout=5)
        owner_loop.close()


def test_foreign_loop_stopping_after_close_dispatch_does_not_hang(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Shutdown detaches a foreign close before its owner loop stops."""
    close_called = Event()
    accepted: list[tuple[object, tuple[object, ...]]] = []

    class Transport:
        def get_state(self) -> grpc.ChannelConnectivity:
            return grpc.ChannelConnectivity.READY

        async def close(self, grace: float | None = None) -> None:
            close_called.set()

    owner_loop, owner_thread = _start_event_loop()

    class ForeignChannel(Channel):
        def create_address_channel(self, addr: str) -> AddressChannel:
            return AddressChannel(  # type: ignore[arg-type]
                Transport(),
                addr,
                owner_loop,
            )

    channel = ForeignChannel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    channel.get_channel_by_addr("127.0.0.1:1")
    original_schedule = owner_loop.call_soon_threadsafe

    def accept_then_stop(callback: object, *args: object) -> object:
        """Accept but strand the close factory, then stop the owner loop."""
        accepted.append((callback, args))
        return original_schedule(owner_loop.stop)

    monkeypatch.setattr(
        owner_loop,
        "call_soon_threadsafe",
        accept_then_stop,
    )
    try:
        channel.sync_close(timeout=5)
        owner_thread.join(timeout=5)
        assert not owner_thread.is_alive()
        assert not close_called.is_set()
        assert len(accepted) == 1
    finally:
        if owner_thread.is_alive():
            original_schedule(owner_loop.stop)
            owner_thread.join(timeout=5)


def test_blocked_foreign_loop_transport_does_not_block_sdk_close() -> None:
    """SDK close does not wait for a blocked caller-owned transport loop."""
    owner_loop, owner_thread = _start_event_loop()
    loop_blocked = Event()
    release_loop = Event()
    close_called = Event()

    def block_owner_loop() -> None:
        """Block the owner loop until SDK close has returned."""
        loop_blocked.set()
        release_loop.wait(timeout=5)

    class Transport:
        """Report native close on the caller-owned loop."""

        def get_state(self) -> grpc.ChannelConnectivity:
            """Return a reusable transport state."""
            return grpc.ChannelConnectivity.READY

        async def close(self, grace: float | None = None) -> None:
            """Report that the deferred transport close ran."""
            close_called.set()

    class ForeignChannel(Channel):
        """Create transports that belong to the blocked owner loop."""

        def create_address_channel(self, addr: str) -> AddressChannel:
            """Create one foreign-loop address channel."""
            return AddressChannel(  # type: ignore[arg-type]
                Transport(),
                addr,
                owner_loop,
            )

    channel = ForeignChannel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    try:
        channel.get_channel_by_addr("blocked-owner.example:443")
        owner_loop.call_soon_threadsafe(block_owner_loop)
        assert loop_blocked.wait(timeout=5)
        channel.sync_close(timeout=5)
        assert not close_called.is_set()
        release_loop.set()
        assert close_called.wait(timeout=5)
    finally:
        release_loop.set()
        try:
            channel.sync_close(timeout=5)
        finally:
            if owner_thread.is_alive():
                _stop_event_loop(owner_loop, owner_thread)


def test_close_log_identifies_each_failing_resource_type(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Close logs the type of each resource that it cannot close."""

    class FirstResource:
        """Fail the first test cleanup."""

        def close(self, grace: float | None = None) -> None:
            """Raise before the first cleanup returns an awaitable."""
            raise RuntimeError("The first test resource rejected the close request.")

    class SecondResource:
        """Fail the second test cleanup."""

        async def close(self, grace: float | None = None) -> None:
            """Raise the second cleanup error."""
            raise RuntimeError("The second test resource rejected the close request.")

    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    channel._gracefuls.update((FirstResource(), SecondResource()))
    channel.sync_close(timeout=5)

    assert "could not start closing the FirstResource resource" in caplog.text
    assert "could not close the SecondResource resource" in caplog.text


def test_foreign_transport_close_accepts_general_owner_loop_awaitable() -> None:
    """Custom close awaitables are created and awaited on their owning loop."""
    owner_loop, owner_thread = _start_event_loop()
    invoked_loops: list[asyncio.AbstractEventLoop] = []

    class Transport:
        """Return a general awaitable from the owner event loop."""

        def close(self, grace: float | None = None):
            """Create an observable close future on the current loop."""
            current_loop = asyncio.get_running_loop()
            invoked_loops.append(current_loop)
            completion = current_loop.create_future()
            current_loop.call_soon(completion.set_result, None)
            return completion

    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    address = AddressChannel(  # type: ignore[arg-type]
        Transport(),
        "foreign-awaitable.example:443",
        owner_loop,
    )
    try:
        channel.run_async(channel._close_address_channel(address, None)).result(timeout=5)
        assert invoked_loops == [owner_loop]
        assert address._is_closed_by_sdk()
    finally:
        channel.sync_close(timeout=5)
        _stop_event_loop(owner_loop, owner_thread)


def test_detached_foreign_close_does_not_retain_parent_channel() -> None:
    """A hung caller-owned close retains its transport, not the whole SDK."""
    owner_loop, owner_thread = _start_event_loop()
    close_started = Event()
    release_close = Event()

    class Transport:
        """Keep close work pending until the test releases it."""

        async def close(self, grace: float | None = None) -> None:
            """Wait for the test to permit transport closure."""
            close_started.set()
            while not release_close.is_set():
                await asyncio.sleep(0.001)

    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    address = AddressChannel(  # type: ignore[arg-type]
        Transport(),
        "detached-close.example:443",
        owner_loop,
    )
    scheduled = Future[None]()
    channel_holder = [channel]
    address_holder = [address]

    def schedule_on_owner() -> None:
        """Schedule transport cleanup from its owner loop."""
        try:
            channel_holder[0]._schedule_address_channel_close(
                address_holder[0],
                None,
            )
        except BaseException as error:
            scheduled.set_exception(error)
        else:
            scheduled.set_result(None)

    channel_reference = ref(channel)
    owner_loop.call_soon_threadsafe(schedule_on_owner)
    scheduled.result(timeout=5)
    assert close_started.wait(timeout=5)
    channel_holder.clear()
    address_holder.clear()
    del schedule_on_owner
    del address
    del channel
    try:
        deadline = monotonic() + 5
        while channel_reference() is not None:
            gc.collect()
            assert monotonic() < deadline
            sleep(0.01)
    finally:
        release_close.set()
        _stop_event_loop(owner_loop, owner_thread)


def test_cross_thread_foreign_close_handle_is_retained_until_completion() -> None:
    """The concurrent dispatch handle owns a detached foreign close."""
    import nebius.aio.channel as channel_module

    owner_loop, owner_thread = _start_event_loop()
    close_started = Event()
    release_close = Event()
    close_finished = Event()

    class Transport:
        """Expose the lifetime of detached transport cleanup."""

        async def close(self, grace: float | None = None) -> None:
            """Wait until the test permits detached cleanup to finish."""
            close_started.set()
            while not release_close.is_set():
                await asyncio.sleep(0.001)
            close_finished.set()

    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    address = AddressChannel(  # type: ignore[arg-type]
        Transport(),
        "cross-thread-close.example:443",
        owner_loop,
    )
    with channel_module._detached_foreign_close_tasks_lock:
        baseline = len(channel_module._detached_foreign_close_handles)
    try:
        channel._schedule_address_channel_close(address, None)
        assert close_started.wait(timeout=5)
        with channel_module._detached_foreign_close_tasks_lock:
            assert len(channel_module._detached_foreign_close_handles) == baseline + 1
        gc.collect()
        assert not close_finished.is_set()
        release_close.set()
        assert close_finished.wait(timeout=5)
        deadline = monotonic() + 5
        while True:
            with channel_module._detached_foreign_close_tasks_lock:
                retained = len(channel_module._detached_foreign_close_handles)
            if retained == baseline:
                break
            assert monotonic() < deadline
            sleep(0.01)
    finally:
        release_close.set()
        channel.sync_close(timeout=5)
        _stop_event_loop(owner_loop, owner_thread)


def test_channel_close_does_not_duplicate_a_scheduled_transport_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Shutdown awaits the published close instead of starting another one."""
    submit_blocked = Event()
    release_submit = Event()
    close_calls: list[float | None] = []
    errors: list[BaseException] = []

    class Transport:
        """Record every native transport close call."""

        async def close(self, grace: float | None = None) -> None:
            """Record the grace value and keep cleanup briefly active."""
            close_calls.append(grace)
            await asyncio.sleep(0.05)

    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    address_channel = AddressChannel(  # type: ignore[arg-type]
        Transport(),
        "127.0.0.1:1",
        channel._event_loop,
    )
    original_submit = channel._runtime.submit
    first_submission = True

    def pause_first_submission(awaitable, *, track=True):
        """Pause the first close submission at its publication boundary."""
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
        """Close the channel and record an unexpected failure."""
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


def test_rejected_transport_close_task_does_not_strand_shutdown(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Asynchronous task-start rejection settles transport lifecycle state."""
    task_rejected = Event()
    close_called = Event()

    class Transport:
        """Record whether rejected close work reaches the transport."""

        async def close(self, grace: float | None = None) -> None:
            """Record native transport cleanup."""
            close_called.set()

    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    address = AddressChannel(  # type: ignore[arg-type]
        Transport(),
        "rejected-close-task.example:443",
        channel._event_loop,
    )

    def reject_once(
        loop: asyncio.AbstractEventLoop,
        coroutine: object,
        **kwargs: object,
    ) -> None:
        """Reject one transport close task and restore the default factory."""
        loop.set_task_factory(None)
        task_rejected.set()
        raise RuntimeError("The test rejected the transport close task.")

    async def install_task_factory() -> None:
        """Install the rejecting task factory on the SDK loop."""
        asyncio.get_running_loop().set_task_factory(reject_once)  # type: ignore[arg-type]

    channel.run_async(install_task_factory()).result(timeout=5)
    channel._schedule_address_channel_close(address, None)
    assert task_rejected.wait(timeout=5)
    deadline = monotonic() + 5
    while True:
        with channel._tasks_lock:
            if not channel._transport_closes:
                break
        assert monotonic() < deadline
        sleep(0.01)

    channel.sync_close(timeout=5)
    assert channel._runtime._shutdown_complete.done()
    assert not close_called.is_set()
    assert "transport close submission failed before cleanup ran" in caplog.text


def test_stopped_owner_loop_transport_is_not_closed_on_caller_loop(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Post-shutdown cleanup never moves a close to an unrelated loop."""
    close_loops: list[asyncio.AbstractEventLoop] = []

    class Transport:
        async def close(self, grace: float | None = None) -> None:
            close_loops.append(asyncio.get_running_loop())

    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    address = AddressChannel(  # type: ignore[arg-type]
        Transport(),
        "stopped-owner-loop.example:443",
        channel._event_loop,
    )
    channel.sync_close(timeout=5)

    async def release_after_shutdown() -> None:
        channel._schedule_address_channel_close(address, None)

    asyncio.run(release_after_shutdown())
    assert close_loops == []
    with channel._tasks_lock:
        assert channel._transport_closes == {}
    assert "owner event loop stopped" in caplog.text


def test_close_snapshot_retires_transport_before_native_close() -> None:
    """A stale release cannot duplicate a snapshotted transport close."""
    close_started = Event()
    release_close = Event()
    close_calls = 0
    errors: list[BaseException] = []

    class Transport:
        async def close(self, grace: float | None = None) -> None:
            nonlocal close_calls
            close_calls += 1
            close_started.set()
            while not release_close.is_set():
                await asyncio.sleep(0.001)

    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    address = AddressChannel(  # type: ignore[arg-type]
        Transport(),
        "snapshot-retirement.example:443",
        channel._event_loop,
    )
    with channel._channel_pool_lock:
        channel._free_channels.setdefault(address.address, []).append(address)

    def close() -> None:
        try:
            channel.sync_close(timeout=5)
        except BaseException as error:
            errors.append(error)

    closer = Thread(target=close)
    closer.start()
    try:
        assert close_started.wait(timeout=5)
        channel.release_channel(address)
        sleep(0.05)
        assert close_calls == 1
    finally:
        release_close.set()
        closer.join(timeout=5)

    assert not closer.is_alive()
    assert errors == []
    assert address._is_closed_by_sdk()


def test_transport_in_flight_close_cannot_be_returned_to_pool() -> None:
    """A duplicate return cannot resurrect a transport being discarded."""
    close_started = Event()
    release_close = Event()

    class Transport:
        def get_state(self) -> grpc.ChannelConnectivity:
            return grpc.ChannelConnectivity.READY

        async def close(self, grace: float | None = None) -> None:
            close_started.set()
            while not release_close.is_set():
                await asyncio.sleep(0.001)

    transport = Transport()

    class RecordingChannel(Channel):
        def create_address_channel(self, addr: str) -> AddressChannel:
            return AddressChannel(transport, addr, self._event_loop)  # type: ignore[arg-type]

    channel = RecordingChannel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    address = channel.get_channel_by_addr("retired.example:443")
    try:
        channel.discard_channel(address)
        assert close_started.wait(timeout=5)

        channel.return_channel(address)

        with channel._channel_pool_lock:
            assert all(pooled is not address for pooled in channel._free_channels.get(address.address, ()))
        assert address._is_retired_by_sdk()
    finally:
        release_close.set()
        channel.sync_close(timeout=5)


def test_stale_returned_wrapper_cannot_discard_free_transport() -> None:
    """Discarding a stale wrapper does not close the reusable transport."""
    release_close = Event()
    created: list[AddressChannel] = []

    class Transport:
        def __init__(self) -> None:
            """Create a transport with an observable close boundary."""
            self.close_started = Event()

        def get_state(self) -> grpc.ChannelConnectivity:
            """Report a reusable state until the test releases close."""
            return grpc.ChannelConnectivity.READY

        async def close(self, grace: float | None = None) -> None:
            """Keep native close in flight until the test releases it."""
            self.close_started.set()
            while not release_close.is_set():
                await asyncio.sleep(0.001)

    class RecordingChannel(Channel):
        def create_address_channel(self, addr: str) -> AddressChannel:
            """Create and record one wrapper for each pool miss."""
            wrapper = AddressChannel(
                Transport(),  # type: ignore[arg-type]
                addr,
                self._event_loop,
            )
            created.append(wrapper)
            return wrapper

    channel = RecordingChannel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    address = channel.get_channel_by_addr("returned-discard.example:443")
    try:
        channel.return_channel(address)
        channel.discard_channel(address)
        assert not address.channel.close_started.wait(timeout=0.05)  # type: ignore[attr-defined]

        replacement = channel.get_channel_by_addr(address.address)
        channel.discard_channel(replacement)
        assert address.channel.close_started.wait(timeout=5)  # type: ignore[attr-defined]

        assert replacement is not address
        assert replacement.channel is address.channel
        assert created == [address]
    finally:
        release_close.set()
        channel.sync_close(timeout=5)


def test_transport_retirement_wins_return_publication_race(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Retirement published between return checks prevents pool insertion."""
    return_checked = Event()
    resume_return = Event()
    release_close = Event()
    errors: list[BaseException] = []

    class Transport:
        def get_state(self) -> grpc.ChannelConnectivity:
            return grpc.ChannelConnectivity.READY

        async def close(self, grace: float | None = None) -> None:
            while not release_close.is_set():
                await asyncio.sleep(0.001)

    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    address = AddressChannel(  # type: ignore[arg-type]
        Transport(),
        "retirement-race.example:443",
        channel._event_loop,
    )
    channel._lease_address_channel(address)
    original_is_retired = address._is_retired_by_sdk
    first_check = True

    def pause_first_check() -> bool:
        nonlocal first_check
        retired = original_is_retired()
        if first_check:
            first_check = False
            return_checked.set()
            resume_return.wait(timeout=5)
        return retired

    monkeypatch.setattr(address, "_is_retired_by_sdk", pause_first_check)

    def return_channel() -> None:
        try:
            channel._release_address_channel(
                address,
                discard=False,
                raise_if_closed=True,
            )
        except BaseException as error:
            errors.append(error)

    returning = Thread(target=return_channel)
    returning.start()
    assert return_checked.wait(timeout=5)
    try:
        channel._schedule_address_channel_close(address, None)
    finally:
        resume_return.set()
        returning.join(timeout=5)

    try:
        assert not returning.is_alive()
        assert errors == []
        with channel._channel_pool_lock:
            assert all(pooled is not address for pooled in channel._free_channels.get(address.address, ()))
    finally:
        release_close.set()
        channel.sync_close(timeout=5)


@pytest.mark.parametrize("borrowed_loop", [False, True])
def test_close_drains_transport_registered_after_cleanup_snapshot(
    borrowed_loop: bool,
) -> None:
    """Close completion includes transport closes published during cleanup."""
    supplied_loop: asyncio.AbstractEventLoop | None = None
    supplied_thread: Thread | None = None
    if borrowed_loop:
        supplied_loop, supplied_thread = _start_event_loop()
    channel = Channel(
        user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials(), event_loop=supplied_loop
    )
    graceful_started = Event()
    release_graceful = Event()
    graceful_finished = Event()
    transport_started = Event()
    release_transport = Event()
    close_calls = 0
    errors: list[BaseException] = []

    class Graceful:
        async def close(self, grace: float | None = None) -> None:
            graceful_started.set()
            while not release_graceful.is_set():
                await asyncio.sleep(0.001)
            graceful_finished.set()

    class Transport:
        async def close(self, grace: float | None = None) -> None:
            nonlocal close_calls
            close_calls += 1
            transport_started.set()
            while not release_transport.is_set():
                await asyncio.sleep(0.001)

    channel._gracefuls.add(Graceful())
    address = AddressChannel(  # type: ignore[arg-type]
        Transport(),
        "late-close.example:443",
        channel._event_loop,
    )

    def close() -> None:
        try:
            channel.sync_close(timeout=5)
        except BaseException as error:
            errors.append(error)

    closer = Thread(target=close)
    closer.start()
    try:
        assert graceful_started.wait(timeout=5)
        channel._schedule_address_channel_close(address, None)
        assert transport_started.wait(timeout=5)
        release_graceful.set()
        assert graceful_finished.wait(timeout=5)
        assert closer.is_alive()
        release_transport.set()
        closer.join(timeout=5)
        assert not closer.is_alive()
        assert errors == []
        assert close_calls == 1
        assert address._is_closed_by_sdk()
        with channel._tasks_lock:
            assert channel._transport_closes == {}
    finally:
        release_graceful.set()
        release_transport.set()
        closer.join(timeout=5)
        if supplied_loop is not None and supplied_thread is not None:
            _stop_event_loop(supplied_loop, supplied_thread)


def test_release_between_close_boundary_and_snapshot_closes_lease_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A release cannot remove the lease before close snapshots ownership."""
    close_boundary = Event()
    resume_close = Event()
    close_calls: list[float | None] = []
    errors: list[BaseException] = []

    class Transport:
        def get_state(self) -> grpc.ChannelConnectivity:
            return grpc.ChannelConnectivity.READY

        async def close(self, grace: float | None = None) -> None:
            close_calls.append(grace)

    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    address = AddressChannel(  # type: ignore[arg-type]
        Transport(),
        "close-boundary.example:443",
        channel._event_loop,
    )
    channel._lease_address_channel(address)
    original_submit = channel._runtime.submit

    def pause_close_submission(awaitable, *, track=True):
        if not track:
            close_boundary.set()
            resume_close.wait(timeout=5)
        return original_submit(awaitable, track=track)

    monkeypatch.setattr(channel._runtime, "submit", pause_close_submission)

    def close() -> None:
        try:
            channel.sync_close(timeout=5)
        except BaseException as error:
            errors.append(error)

    closer = Thread(target=close)
    closer.start()
    assert close_boundary.wait(timeout=5)
    try:
        channel.release_channel(address)
        with channel._channel_pool_lock:
            assert channel._leased_channels.get(id(address)) is address
    finally:
        resume_close.set()
        closer.join(timeout=5)

    assert not closer.is_alive()
    assert errors == []
    assert close_calls == [None]
    with channel._channel_pool_lock:
        assert channel._leased_channels == {}


def test_concurrent_foreign_release_schedules_one_close() -> None:
    """One foreign wrapper has at most one in-flight native close."""
    owner_loop, owner_thread = _start_event_loop()
    close_started = Event()
    release_close = Event()
    close_calls = 0
    close_lock = Lock()

    class Transport:
        async def close(self, grace: float | None = None) -> None:
            nonlocal close_calls
            with close_lock:
                close_calls += 1
            close_started.set()
            while not release_close.is_set():
                await asyncio.sleep(0.001)

    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    address = AddressChannel(  # type: ignore[arg-type]
        Transport(),
        "foreign-close.example:443",
        owner_loop,
    )
    channel.sync_close(timeout=5)
    barrier = Barrier(3)
    errors: list[BaseException] = []

    def release() -> None:
        barrier.wait()
        try:
            channel.release_channel(address)
        except BaseException as error:
            errors.append(error)

    releasers = [Thread(target=release) for _ in range(2)]
    for releaser in releasers:
        releaser.start()
    barrier.wait()
    try:
        assert close_started.wait(timeout=5)
        sleep(0.05)
        with close_lock:
            assert close_calls == 1
    finally:
        release_close.set()
        for releaser in releasers:
            releaser.join(timeout=5)
        _stop_event_loop(owner_loop, owner_thread)

    assert errors == []
    assert all(not releaser.is_alive() for releaser in releasers)


def test_stranded_foreign_close_dispatch_has_no_sdk_reservation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A stranded close factory has no coroutine or process-global root."""
    owner_loop, owner_thread = _start_event_loop()
    owner_loop_holder = [owner_loop]
    accepted: list[tuple[object, tuple[object, ...]]] = []
    original_schedule = owner_loop.call_soon_threadsafe
    with channel_module._detached_foreign_close_tasks_lock:
        baseline = len(channel_module._detached_foreign_close_handles)

    class Transport:
        async def close(self, grace: float | None = None) -> None:
            return None

    def strand_dispatch(callback: object, *args: object) -> None:
        """Accept the callback without running its close factory."""
        assert owner_loop_holder
        accepted.append((callback, args))

    monkeypatch.setattr(owner_loop, "call_soon_threadsafe", strand_dispatch)
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    address = AddressChannel(  # type: ignore[arg-type]
        Transport(),
        "stranded-close.example:443",
        owner_loop,
    )
    try:
        channel._schedule_address_channel_close(address, None)
        original_schedule(owner_loop.stop)
        owner_thread.join(timeout=5)
        assert not owner_thread.is_alive()
        assert len(accepted) == 1
        with channel_module._detached_foreign_close_tasks_lock:
            assert len(channel_module._detached_foreign_close_handles) == baseline
    finally:
        channel.sync_close(timeout=5)
        if owner_thread.is_alive():
            _stop_event_loop(owner_loop, owner_thread)

    channel_reference = ref(channel)
    address_reference = ref(address)
    loop_reference = ref(owner_loop)
    accepted.clear()
    owner_loop_holder.clear()
    monkeypatch.undo()
    del strand_dispatch
    del original_schedule
    del channel
    del address
    del owner_loop
    del owner_thread
    gc.collect()

    assert channel_reference() is None
    assert address_reference() is None
    assert loop_reference() is None
    with channel_module._detached_foreign_close_tasks_lock:
        assert len(channel_module._detached_foreign_close_handles) == baseline


def test_foreign_close_task_factory_rejection_disposes_coroutine(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A foreign owner-loop task rejection disposes detached close work."""
    rejected: list[object] = []

    class Transport:
        async def close(self, grace: float | None = None) -> None:
            """Provide close work that the test task factory rejects."""
            return

    def reject_task(coro: object, *, name: str) -> None:
        """Reject and record the detached close coroutine."""
        rejected.append(coro)
        raise RuntimeError("The test rejected the transport close task.")

    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    monkeypatch.setattr(channel_module, "create_task", reject_task)

    async def discard_on_owner_loop() -> AddressChannel:
        """Discard a foreign transport from its current owner loop."""
        owner_loop = asyncio.get_running_loop()
        address = AddressChannel(  # type: ignore[arg-type]
            Transport(),
            "foreign-task-rejection.example:443",
            owner_loop,
        )
        channel._schedule_address_channel_close(address, None)
        return address

    try:
        address = asyncio.run(discard_on_owner_loop())
        assert address._is_retired_by_sdk()
        assert len(rejected) == 1
        assert inspect.getcoroutinestate(rejected[0]) == inspect.CORO_CLOSED
        assert "The SDK could not start the transport close task." in caplog.text
    finally:
        channel.sync_close(timeout=5)


def test_stopped_foreign_loop_releases_real_detached_task() -> None:
    """A stopped owner loop does not root a real detached close task globally."""
    ready = Future[asyncio.AbstractEventLoop]()
    ready_holder = [ready]
    close_started = Event()

    def run_owner_loop() -> None:
        """Run an owner loop that stops without draining pending tasks."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        ready_holder[0].set_result(loop)
        loop.run_forever()
        for task in asyncio.all_tasks(loop):
            task._log_destroy_pending = False  # type: ignore[attr-defined]
            task.get_coro().close()
        loop.close()

    class Transport:
        async def close(self, grace: float | None = None) -> None:
            """Keep a real close task pending until its stopped loop is dropped."""
            close_started.set()
            await asyncio.Event().wait()

    owner_thread = Thread(target=run_owner_loop, daemon=True)
    owner_thread.start()
    owner_loop = ready.result(timeout=5)
    with channel_module._detached_foreign_close_tasks_lock:
        baseline = len(channel_module._detached_foreign_close_handles)

    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    address = AddressChannel(  # type: ignore[arg-type]
        Transport(),
        "stopped-real-close.example:443",
        owner_loop,
    )
    channel._schedule_address_channel_close(address, None)
    assert close_started.wait(timeout=5)
    with channel_module._detached_foreign_close_tasks_lock:
        assert len(channel_module._detached_foreign_close_handles) == baseline + 1

    owner_loop.call_soon_threadsafe(owner_loop.stop)
    owner_thread.join(timeout=5)
    assert not owner_thread.is_alive()
    channel.sync_close(timeout=5)

    channel_reference = ref(channel)
    address_reference = ref(address)
    loop_reference = ref(owner_loop)
    del channel
    del address
    del owner_loop
    del owner_thread
    ready_holder.clear()
    del run_owner_loop
    del ready
    gc.collect()

    assert channel_reference() is None
    assert address_reference() is None
    assert loop_reference() is None
    with channel_module._detached_foreign_close_tasks_lock:
        assert len(channel_module._detached_foreign_close_handles) == baseline


def test_detached_close_retention_supports_fixed_slot_loop() -> None:
    """Detached retention does not add private state to an owner loop."""

    class Timer:
        """Record cancellation of a fixed-slot loop timer."""

        def __init__(self) -> None:
            """Create an active timer."""
            self.cancelled = False

        def cancel(self) -> None:
            """Record timer cancellation."""
            self.cancelled = True

    class FixedSlotLoop:
        """Provide the public scheduling boundary without an instance dictionary."""

        __slots__ = ("callbacks", "timers", "__weakref__")

        def __init__(self) -> None:
            """Create an empty thread-safe callback queue."""
            self.callbacks: list[tuple[object, tuple[object, ...]]] = []
            self.timers: list[tuple[float, object, Timer]] = []

        def call_soon_threadsafe(self, callback, *args):
            """Retain a callback as a real loop ready queue would."""
            self.callbacks.append((callback, args))

        def call_later(self, delay: float, callback) -> Timer:
            """Retain a timer callback and return its handle."""
            timer = Timer()
            self.timers.append((delay, callback, timer))
            return timer

        def is_closed(self) -> bool:
            """Report that the synthetic owner loop is open."""
            return False

    loop = FixedSlotLoop()
    with pytest.raises(AttributeError):
        setattr(loop, "private_sdk_state", object())
    handle = Future[None]()
    with channel_module._detached_foreign_close_tasks_lock:
        baseline = len(channel_module._detached_foreign_close_handles)

    channel_module._retain_detached_foreign_close(  # type: ignore[arg-type]
        handle,
        loop,
    )

    assert len(loop.callbacks) == 1
    retain_callback, retain_args = loop.callbacks.pop()
    retain_callback(*retain_args)  # type: ignore[operator]
    assert len(loop.timers) == 1
    with channel_module._detached_foreign_close_tasks_lock:
        assert len(channel_module._detached_foreign_close_handles) == baseline + 1
    handle.set_result(None)
    cancel_callback, cancel_args = loop.callbacks.pop()
    cancel_callback(*cancel_args)  # type: ignore[operator]
    assert loop.timers[0][2].cancelled
    with channel_module._detached_foreign_close_tasks_lock:
        assert len(channel_module._detached_foreign_close_handles) == baseline


def test_fallback_close_task_factory_rejection_settles_reservation(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A fallback task rejection settles its transport-close reservation."""
    rejected: list[object] = []

    class Transport:
        async def close(self, grace: float | None = None) -> None:
            """Provide close work that the test task factory rejects."""
            return

    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    address = AddressChannel(  # type: ignore[arg-type]
        Transport(),
        "fallback-task-rejection.example:443",
        channel._event_loop,
    )

    def reject_submission(awaitable: object, *, track: bool = True) -> None:
        """Reject the primary runtime close submission."""
        raise RuntimeError("The test rejected the transport close submission.")

    def reject_task(coro: object, *, name: str) -> None:
        """Reject and record the fallback close coroutine."""
        rejected.append(coro)
        raise RuntimeError("The test rejected the fallback close task.")

    original_submit = channel._runtime.submit
    monkeypatch.setattr(channel._runtime, "submit", reject_submission)
    monkeypatch.setattr(channel_module, "create_task", reject_task)

    async def discard_on_sdk_loop() -> None:
        """Enter the same-loop fallback close path."""
        channel._schedule_address_channel_close(address, None)

    try:
        channel.run_async(discard_on_sdk_loop()).result(timeout=5)
        assert id(address) not in channel._transport_closes
        assert len(rejected) == 1
        assert inspect.getcoroutinestate(rejected[0]) == inspect.CORO_CLOSED
        assert "The SDK could not start the transport close task." in caplog.text
    finally:
        monkeypatch.setattr(channel._runtime, "submit", original_submit)
        channel.sync_close(timeout=5)


def test_stopped_loop_releases_stranded_close_factory_reservation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A stopped owner loop releases a queued close reservation."""
    accepted: list[tuple[object, tuple[object, ...]]] = []
    owner_loop, owner_thread = _start_event_loop()
    original_schedule = owner_loop.call_soon_threadsafe
    completions = [Future[None]() for _ in range(3)]
    watcher_threads: list[Thread | None] = []

    def strand_dispatch(callback: object, *args: object) -> None:
        """Accept the fallback callback without running its factory."""
        accepted.append((callback, args))

    def close_factory() -> Coroutine[Any, Any, None]:
        """Create close work only if the stranded callback executes."""
        raise AssertionError("The stranded factory must not execute.")

    monkeypatch.setattr(owner_loop, "call_soon_threadsafe", strand_dispatch)
    try:
        for completion in completions:
            assert channel_module._schedule_detached_close_factory(
                close_factory,
                owner_loop,
                "Test transport close",
                completion,
            )
            watcher_threads.append(channel_module._transport_close_watch_thread)
        assert len(accepted) == 3
        assert len({id(thread) for thread in watcher_threads}) == 1
        original_schedule(owner_loop.stop)
        owner_thread.join(timeout=5)
        assert not owner_thread.is_alive()
        assert all(completion.result(timeout=5) is None for completion in completions)
    finally:
        accepted.clear()
        if owner_thread.is_alive():
            original_schedule(owner_loop.stop)
            owner_thread.join(timeout=5)


def test_detached_close_factory_failure_settles_completion(caplog) -> None:
    """A close-factory failure logs the error and settles its completion."""

    async def run() -> Future[None]:
        """Call the failing factory on its owner loop."""
        completion: Future[None] = Future()

        def fail_factory() -> Coroutine[Any, Any, None]:
            """Fail before the factory can create close work."""
            raise RuntimeError("The test could not create close work.")

        assert not channel_module._schedule_detached_close_factory(
            fail_factory,
            asyncio.get_running_loop(),
            "Test transport close",
            completion,
        )
        return completion

    completion = asyncio.run(run())
    assert completion.result(timeout=0) is None
    assert "The SDK could not create the transport close work." in caplog.text


def test_async_release_failure_is_observed_and_retries_close(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A started asynchronous release reports failure and retries cleanup."""
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    address = AddressChannel(  # type: ignore[arg-type]
        object(),
        "release-failure.example:443",
        channel._event_loop,
    )
    retried = Event()
    original_release = channel._release_address_channel
    original_schedule = channel._schedule_address_channel_close

    def fail_release(*args: object, **kwargs: object) -> None:
        """Fail after the asynchronous release task starts."""
        raise RuntimeError("The test rejected the transport release.")

    def record_retry(*args: object, **kwargs: object) -> None:
        """Record the ownership-aware close retry."""
        retried.set()

    monkeypatch.setattr(channel, "_release_address_channel", fail_release)
    monkeypatch.setattr(channel, "_schedule_address_channel_close", record_retry)
    try:
        channel._release_channel_soon(address, discard=True)
        assert retried.wait(timeout=5)
        assert "The SDK could not release the transport." in caplog.text
    finally:
        monkeypatch.setattr(channel, "_release_address_channel", original_release)
        monkeypatch.setattr(
            channel,
            "_schedule_address_channel_close",
            original_schedule,
        )
        channel.sync_close(timeout=5)


def test_unexpected_transport_close_submission_failure_is_not_retained(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-runtime rejection settles the transport lifecycle reservation."""

    class Transport:
        async def close(self, grace: float | None = None) -> None:
            return None

    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    address = AddressChannel(  # type: ignore[arg-type]
        Transport(),
        "rejected-close.example:443",
        channel._event_loop,
    )
    original_submit = channel._runtime.submit

    def reject(awaitable: object, *, track: bool = True) -> None:
        raise ValueError("The test rejected the close task unexpectedly.")

    monkeypatch.setattr(channel._runtime, "submit", reject)
    try:
        with pytest.raises(ValueError, match="rejected the close task unexpectedly"):
            channel._schedule_address_channel_close(address, None)
        assert id(address) not in channel._transport_closes
    finally:
        monkeypatch.setattr(channel._runtime, "submit", original_submit)
        channel.sync_close(timeout=5)


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
        user_agent_prefix="nebius-python-sdk-tests/1.0",
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
        user_agent_prefix="nebius-python-sdk-tests/1.0",
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
            self.custom_state = "preserved"

    class LegacyFactoryChannel(Channel):
        def create_address_channel(self, addr: str) -> AddressChannel:
            return LegacyAddressChannel(grpc.aio.insecure_channel(addr), addr)

    channel = LegacyFactoryChannel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())

    async def checkout_twice() -> tuple[AddressChannel, AddressChannel]:
        first = await _checkout(channel, "127.0.0.1:1")
        await asyncio.to_thread(channel.return_channel, first)
        second = await _checkout(channel, "127.0.0.1:1")
        await asyncio.to_thread(channel.return_channel, second)
        return first, second

    try:
        first, second = asyncio.run(checkout_twice())

        assert first.event_loop is not None
        assert second is not first
        assert isinstance(second, LegacyAddressChannel)
        assert second.channel is first.channel
        assert second.custom_state == "preserved"
    finally:
        asyncio.run(channel.close())


def test_legacy_constructor_keeps_creation_loop_ownership() -> None:
    address = "127.0.0.1:1"
    loop_a, thread_a = _start_event_loop()
    loop_b, thread_b = _start_event_loop()
    channel = Channel(
        user_agent_prefix="nebius-python-sdk-tests/1.0",
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

    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())

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
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
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
        user_agent_prefix="nebius-python-sdk-tests/1.0",
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
        user_agent_prefix="nebius-python-sdk-tests/1.0",
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
        channel = RecordingChannel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
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
        channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
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
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
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
        channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
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
        channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
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
        for _ in range(3):
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
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials(), event_loop=loop)

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
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
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
        user_agent_prefix="nebius-python-sdk-tests/1.0",
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
            super().__init__(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
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
