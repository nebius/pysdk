from __future__ import annotations

import asyncio
from concurrent.futures import CancelledError as ConcurrentCancelledError
from concurrent.futures import Future
from pathlib import Path
from threading import Barrier, Event, Thread
from threading import enumerate as enumerate_threads
from time import monotonic, sleep

import grpc
import pytest

from nebius.aio.authorization.authorization import Authenticator, Provider
from nebius.aio.base import AddressChannel
from nebius.aio.channel import Channel, LoopError, NoCredentials
from nebius.aio.cli_config import Config
from nebius.aio.token.exchangeable import Bearer as ExchangeableBearer
from nebius.api.nebius.compute.v1 import Disk, GetDiskRequest
from nebius.api.nebius.iam.v1 import ExchangeTokenRequest
from nebius.base.metadata import Metadata
from nebius.base.service_account.service_account import TokenRequester


def _start_loop() -> tuple[asyncio.AbstractEventLoop, Thread]:
    ready: Future[asyncio.AbstractEventLoop] = Future()

    def run() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        ready.set_result(loop)
        loop.run_forever()
        loop.close()

    thread = Thread(target=run, daemon=True)
    thread.start()
    return ready.result(timeout=5), thread


def _stop_loop(loop: asyncio.AbstractEventLoop, thread: Thread) -> None:
    loop.call_soon_threadsafe(loop.stop)
    thread.join(timeout=5)
    assert not thread.is_alive()


def test_owned_runtime_threads_are_daemons_and_stop_on_close() -> None:
    channel = Channel(credentials=NoCredentials(), executor_max_workers=3)
    runtime_threads = [
        thread
        for thread in enumerate_threads()
        if thread.name == "nebius-sdk-loop"
        or thread.name.startswith("nebius-sdk-worker_")
    ]

    assert len([t for t in runtime_threads if "worker" in t.name]) == 3
    assert all(thread.daemon for thread in runtime_threads)

    channel.sync_close(timeout=5)

    assert all(not thread.is_alive() for thread in runtime_threads)


def test_cross_loop_awaitable_can_be_shared_by_external_loops() -> None:
    channel = Channel(credentials=NoCredentials())
    started = Event()
    release = Event()

    async def work() -> int:
        started.set()
        while not release.is_set():
            await asyncio.sleep(0)
        return id(asyncio.get_running_loop())

    submitted = channel.run_async(work())
    loop_a, thread_a = _start_loop()
    loop_b, thread_b = _start_loop()

    async def wait_for_result() -> int:
        return await submitted

    try:
        future_a = asyncio.run_coroutine_threadsafe(wait_for_result(), loop_a)
        future_b = asyncio.run_coroutine_threadsafe(wait_for_result(), loop_b)
        assert started.wait(timeout=5)
        release.set()
        assert future_a.result(timeout=5) == id(channel._event_loop)
        assert future_b.result(timeout=5) == id(channel._event_loop)
    finally:
        release.set()
        channel.sync_close(timeout=5)
        _stop_loop(loop_a, thread_a)
        _stop_loop(loop_b, thread_b)


def test_run_sync_is_safe_from_many_threads() -> None:
    channel = Channel(credentials=NoCredentials())
    barrier = Barrier(11)
    results: list[int] = []

    def run(index: int) -> None:
        barrier.wait()
        results.append(channel.run_sync(asyncio.sleep(0, result=index), timeout=5))

    threads = [Thread(target=run, args=(index,)) for index in range(10)]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join(timeout=5)
        assert not thread.is_alive()

    channel.sync_close(timeout=5)
    assert sorted(results) == list(range(10))


def test_foreign_loop_future_is_bridged() -> None:
    loop, thread = _start_loop()
    channel = Channel(credentials=NoCredentials())

    async def create_future() -> asyncio.Future[int]:
        return asyncio.get_running_loop().create_future()

    source = asyncio.run_coroutine_threadsafe(create_future(), loop).result(timeout=5)
    bridged = channel.run_async(source)
    try:
        loop.call_soon_threadsafe(source.set_result, 42)
        assert bridged.result(timeout=5) == 42
    finally:
        channel.sync_close(timeout=5)
        _stop_loop(loop, thread)


def test_bg_task_bridges_foreign_loop_future() -> None:
    loop, thread = _start_loop()
    channel = Channel(credentials=NoCredentials())

    async def create_future() -> asyncio.Future[int]:
        return asyncio.get_running_loop().create_future()

    source = asyncio.run_coroutine_threadsafe(create_future(), loop).result(timeout=5)
    background = channel.bg_task(source)
    try:
        loop.call_soon_threadsafe(source.set_result, 42)
        assert background.result(timeout=5) is None
        assert source.result() == 42
    finally:
        channel.sync_close(timeout=5)
        _stop_loop(loop, thread)


def test_close_cancels_bg_task_foreign_loop_future() -> None:
    loop, thread = _start_loop()
    channel = Channel(credentials=NoCredentials())

    async def create_future() -> asyncio.Future[None]:
        return asyncio.get_running_loop().create_future()

    source = asyncio.run_coroutine_threadsafe(create_future(), loop).result(timeout=5)
    channel.bg_task(source)
    try:
        channel.sync_close(timeout=5)

        async def wait_until_cancelled() -> bool:
            for _ in range(100):
                if source.cancelled():
                    return True
                await asyncio.sleep(0.01)
            return source.cancelled()

        cancelled = asyncio.run_coroutine_threadsafe(
            wait_until_cancelled(),
            loop,
        ).result(timeout=5)
        assert cancelled
    finally:
        if not source.done():
            loop.call_soon_threadsafe(source.cancel)
        _stop_loop(loop, thread)


def test_supplied_loop_is_not_stopped_or_reconfigured() -> None:
    loop, thread = _start_loop()
    original_executor = getattr(loop, "_default_executor", None)
    channel = Channel(credentials=NoCredentials(), event_loop=loop)
    try:
        assert channel.run_sync(asyncio.sleep(0, result=42), timeout=5) == 42
        channel.sync_close(timeout=5)
        assert loop.is_running()
        assert getattr(loop, "_default_executor", None) is original_executor
    finally:
        _stop_loop(loop, thread)


def test_public_authorization_provider_dispatches_to_internal_loop() -> None:
    calls: list[int] = []

    class RecordingAuthenticator(Authenticator):
        async def authenticate(
            self,
            metadata: Metadata,
            timeout: float | None = None,
            options: dict[str, str] | None = None,
        ) -> None:
            calls.append(id(asyncio.get_running_loop()))

        def can_retry(
            self,
            err: Exception,
            options: dict[str, str] | None = None,
        ) -> bool:
            calls.append(id(asyncio.get_running_loop()))
            return False

    class RecordingProvider(Provider):
        def authenticator(self) -> Authenticator:
            calls.append(id(asyncio.get_running_loop()))
            return RecordingAuthenticator()

    configured_provider = RecordingProvider()
    channel = Channel(credentials=configured_provider)
    try:
        provider = channel.get_authorization_provider()
        assert provider is configured_provider
        provider = channel._get_runtime_authorization_provider()
        assert provider is not None
        authenticator = provider.authenticator()
        asyncio.run(authenticator.authenticate(Metadata()))

        async def retry() -> bool:
            return authenticator.can_retry(RuntimeError("test"))

        assert channel.run_sync(retry(), timeout=5) is False
        assert calls == [id(channel._event_loop)] * 3
    finally:
        channel.sync_close(timeout=5)


def test_async_metric_callback_is_owned_and_cancelled_by_runtime() -> None:
    started = Event()
    cancelled = Event()
    callback_loops: list[int] = []

    class Metrics:
        async def token_acquire(self, metric: object) -> None:
            callback_loops.append(id(asyncio.get_running_loop()))
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

    channel = Channel(credentials="token", metrics=Metrics())
    channel.get_token_sync(timeout=5)
    assert started.wait(timeout=5)

    channel.sync_close(timeout=5)

    assert cancelled.wait(timeout=5)
    assert callback_loops == [id(channel._event_loop)]


@pytest.mark.parametrize("supplied", [False, True])
def test_sync_close_from_internal_loop_raises_without_deadlock(
    supplied: bool,
) -> None:
    loop: asyncio.AbstractEventLoop | None = None
    thread: Thread | None = None
    if supplied:
        loop, thread = _start_loop()
    channel = Channel(credentials=NoCredentials(), event_loop=loop)

    async def attempt() -> None:
        with pytest.raises(LoopError, match="await close"):
            channel.sync_close(timeout=0.1)

    try:
        channel.run_async(attempt()).result(timeout=5)
        channel.sync_close(timeout=5)
    finally:
        if loop is not None and thread is not None:
            _stop_loop(loop, thread)


def test_sync_close_timeout_still_finishes_runtime_shutdown() -> None:
    class BlockingGraceful:
        def __init__(self) -> None:
            self.started = Event()
            self.release = Event()

        async def close(self, grace: float | None = None) -> None:
            self.started.set()
            while not self.release.is_set():
                await asyncio.sleep(0)

    channel = Channel(credentials=NoCredentials())
    graceful = BlockingGraceful()
    channel._gracefuls.add(graceful)
    runtime_threads = [
        channel._runtime._loop_thread,
        *channel._runtime._executor._threads,
    ]

    with pytest.raises(TimeoutError, match="shutdown timed out"):
        channel.sync_close(timeout=0.05)
    assert graceful.started.wait(timeout=5)
    graceful.release.set()

    deadline = monotonic() + 5
    while any(thread is not None and thread.is_alive() for thread in runtime_threads):
        assert monotonic() < deadline
        sleep(0.01)


def test_sync_close_timeout_covers_blocked_executor_shutdown() -> None:
    channel = Channel(credentials=NoCredentials())
    worker_started = Event()
    release_worker = Event()

    def worker() -> None:
        worker_started.set()
        release_worker.wait(timeout=5)

    async def internal_work() -> None:
        await asyncio.get_running_loop().run_in_executor(None, worker)

    channel.run_async(internal_work())
    assert worker_started.wait(timeout=5)

    try:
        with pytest.raises(TimeoutError, match="shutdown timed out"):
            channel.sync_close(timeout=0.05)
    finally:
        release_worker.set()
        channel._runtime._shutdown_complete.result(timeout=5)


def test_supplied_loop_close_cancels_and_drains_submissions() -> None:
    loop, thread = _start_loop()
    channel = Channel(credentials=NoCredentials(), event_loop=loop)
    started = Event()
    finalized = Event()

    async def pending() -> None:
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            await asyncio.sleep(0)
            finalized.set()

    submitted = channel.run_async(pending())
    try:
        assert started.wait(timeout=5)
        channel.sync_close(timeout=5)
        assert submitted.cancelled()
        assert finalized.wait(timeout=5)
        assert loop.is_running()
    finally:
        _stop_loop(loop, thread)


def test_internal_close_caller_completes_before_runtime_stops() -> None:
    channel = Channel(credentials=NoCredentials())

    async def close_from_internal_loop() -> int:
        await channel.close()
        return 42

    assert channel.run_async(close_from_internal_loop()).result(timeout=5) == 42


def test_internal_close_stops_continuation_on_its_next_await() -> None:
    channel = Channel(credentials=NoCredentials())
    close_returned = Event()
    finalized = Event()

    async def close_then_block() -> None:
        try:
            await channel.close()
            close_returned.set()
            await asyncio.Event().wait()
        finally:
            finalized.set()

    submitted = channel.run_async(close_then_block())
    with pytest.raises(ConcurrentCancelledError):
        submitted.result(timeout=5)
    assert close_returned.wait(timeout=5)
    assert finalized.wait(timeout=5)


def test_run_sync_preserves_runtime_error_from_awaitable() -> None:
    channel = Channel(credentials=NoCredentials())

    async def fail() -> None:
        raise RuntimeError("boom")

    try:
        with pytest.raises(RuntimeError, match="boom"):
            channel.run_sync(fail(), timeout=5)
    finally:
        channel.sync_close(timeout=5)


def test_constructor_config_metrics_run_on_internal_loop_and_are_drained(
    tmp_path: Path,
) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "\n".join(
            [
                "default: test",
                "profiles:",
                "  test:",
                "    endpoint: api.example.test:443",
            ]
        )
    )
    started = Event()
    finalized = Event()
    callback_loops: list[int] = []

    class Metrics:
        async def config_load(self, metric: object) -> None:
            callback_loops.append(id(asyncio.get_running_loop()))
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                finalized.set()

    config = Config(config_file=config_file, no_env=True)
    channel = Channel(
        config_reader=config,
        credentials=NoCredentials(),
        metrics=Metrics(),
    )
    assert started.wait(timeout=5)

    channel.sync_close(timeout=5)

    assert finalized.wait(timeout=5)
    assert callback_loops == [id(channel._event_loop)]


def test_deferred_credential_channel_future_is_bridged_from_foreign_loop() -> None:
    class Requester(TokenRequester):
        def get_exchange_token_request(self) -> ExchangeTokenRequest:
            raise AssertionError("request creation is not expected")

    foreign_loop, foreign_thread = _start_loop()
    sdk_channel = Channel(credentials=NoCredentials())

    async def create_future() -> asyncio.Future[Channel]:
        return asyncio.get_running_loop().create_future()

    source = asyncio.run_coroutine_threadsafe(
        create_future(),
        foreign_loop,
    ).result(timeout=5)
    bearer = ExchangeableBearer(Requester(), source)
    submitted = sdk_channel.run_async(bearer._token_exchange_service_stub())
    try:
        foreign_loop.call_soon_threadsafe(source.set_result, sdk_channel)
        service = submitted.result(timeout=5)
        assert service is not None
    finally:
        sdk_channel.sync_close(timeout=5)
        _stop_loop(foreign_loop, foreign_thread)


def test_low_level_deadline_includes_internal_queue_delay() -> None:
    timeouts: list[float | None] = []

    class FakeCall:
        def __await__(self):
            async def result() -> Disk:
                return Disk()

            return result().__await__()

        async def initial_metadata(self) -> tuple[()]:
            return ()

        async def trailing_metadata(self) -> tuple[()]:
            return ()

        async def code(self) -> grpc.StatusCode:
            return grpc.StatusCode.OK

        async def details(self) -> str:
            return ""

    class FakeTransport:
        def unary_unary(self, *args: object, **kwargs: object):
            def invoke(request: object, **call_kwargs: object) -> FakeCall:
                timeouts.append(call_kwargs.get("timeout"))  # type: ignore[arg-type]
                return FakeCall()

            return invoke

        def get_state(self) -> grpc.ChannelConnectivity:
            return grpc.ChannelConnectivity.READY

        async def close(self, grace: float | None = None) -> None:
            return None

    transport = FakeTransport()

    class FakeChannel(Channel):
        def create_address_channel(self, addr: str) -> AddressChannel:
            return AddressChannel(transport, addr)  # type: ignore[arg-type]

    channel = FakeChannel(credentials=NoCredentials())
    started = Event()
    release = Event()

    async def block_loop() -> None:
        started.set()
        release.wait(timeout=5)

    blocking = channel.run_async(block_loop())
    assert started.wait(timeout=5)
    call = channel.unary_unary(
        "/nebius.compute.v1.DiskService/Get",
        lambda request: request.SerializeToString(),
        Disk.FromString,
    )(GetDiskRequest(id="queued"), timeout=0.5)
    sleep(0.15)
    release.set()

    async def await_call() -> Disk:
        return await call

    try:
        asyncio.run(await_call())
        blocking.result(timeout=5)
        assert len(timeouts) == 1
        assert timeouts[0] is not None
        assert 0 < timeouts[0] < 0.45
    finally:
        release.set()
        channel.sync_close(timeout=5)


def test_low_level_prestart_cancel_publishes_terminal_status() -> None:
    channel = Channel(credentials=NoCredentials())
    loop_blocked = Event()
    release_loop = Event()

    async def block_loop() -> None:
        loop_blocked.set()
        release_loop.wait(timeout=5)

    channel.run_async(block_loop())
    assert loop_blocked.wait(timeout=5)
    call = channel.unary_unary(
        "/nebius.compute.v1.DiskService/Get",
        lambda request: request.SerializeToString(),
        Disk.FromString,
    )(GetDiskRequest(id="cancel-before-start"))
    assert call.cancel()
    release_loop.set()

    async def terminal_status() -> None:
        code = await asyncio.wait_for(call.code(), timeout=5)
        assert code == grpc.StatusCode.CANCELLED
        assert await asyncio.wait_for(call.initial_metadata(), timeout=5) is not None
        assert await asyncio.wait_for(call.trailing_metadata(), timeout=5) is not None
        assert "cancel" in (await asyncio.wait_for(call.details(), timeout=5)).lower()

    try:
        asyncio.run(terminal_status())
    finally:
        release_loop.set()
        channel.sync_close(timeout=5)


def test_async_close_does_not_block_external_loop_needed_by_worker() -> None:
    async def run() -> None:
        external_loop = asyncio.get_running_loop()
        channel = Channel(credentials=NoCredentials())
        worker_started = Event()
        worker_finished = Event()

        def worker() -> None:
            worker_started.set()
            asyncio.run_coroutine_threadsafe(
                asyncio.sleep(0.1),
                external_loop,
            ).result(timeout=5)
            worker_finished.set()

        async def internal_work() -> None:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, worker)

        channel.run_async(internal_work())
        await asyncio.to_thread(worker_started.wait, 5)

        await asyncio.wait_for(channel.close(), timeout=5)
        assert worker_finished.is_set()

    asyncio.run(run())


def test_sync_close_from_external_async_context_preserves_loop_error() -> None:
    async def run() -> None:
        channel = Channel(credentials=NoCredentials())
        with pytest.raises(LoopError, match="await close"):
            channel.sync_close(timeout=0.1)
        await channel.close()

    asyncio.run(run())


def test_external_close_does_not_cancel_concurrent_internal_close_result() -> None:
    async def run_once() -> None:
        channel = Channel(credentials=NoCredentials())
        entered = Event()

        async def internal() -> int:
            entered.set()
            await channel.close()
            return 42

        submitted = channel.run_async(internal())
        await asyncio.to_thread(entered.wait, 5)
        await channel.close()
        assert submitted.result(timeout=5) == 42

    for _ in range(20):
        asyncio.run(run_once())


def test_sync_close_does_not_cancel_concurrent_internal_close_result() -> None:
    for _ in range(20):
        channel = Channel(credentials=NoCredentials())
        entered = Event()

        async def internal() -> int:
            entered.set()
            await channel.close()
            return 42

        submitted = channel.run_async(internal())
        assert entered.wait(timeout=5)
        channel.sync_close(timeout=5)
        assert submitted.result(timeout=5) == 42
