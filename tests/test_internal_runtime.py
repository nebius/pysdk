from __future__ import annotations

import asyncio
import inspect
import os
import signal
from concurrent.futures import CancelledError as ConcurrentCancelledError
from concurrent.futures import Future
from pathlib import Path
from threading import Barrier, Event, Lock, Thread
from threading import enumerate as enumerate_threads
from time import monotonic, sleep

import grpc
import pytest

import nebius.aio._runtime as runtime_module
from nebius.aio._runtime import AsyncRuntime, DaemonThreadPoolExecutor
from nebius.aio.authorization.authorization import Authenticator, Provider
from nebius.aio.base import AddressChannel
from nebius.aio.channel import Channel, LoopError, NoCredentials
from nebius.aio.cli_config import Config
from nebius.aio.operation import Operation
from nebius.aio.request import Request
from nebius.aio.stream import StreamRequest
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


def test_runtime_startup_failure_is_reported_and_workers_stop(monkeypatch) -> None:
    """An exception in loop-thread setup must not strand the constructor."""

    original = asyncio.BaseEventLoop.set_default_executor

    def fail_setup(
        loop: asyncio.BaseEventLoop,
        executor: object,
    ) -> None:
        raise RuntimeError("setup failed")

    monkeypatch.setattr(asyncio.BaseEventLoop, "set_default_executor", fail_setup)
    before = set(enumerate_threads())
    with pytest.raises(RuntimeError, match="setup failed"):
        AsyncRuntime(None, 2)
    monkeypatch.setattr(asyncio.BaseEventLoop, "set_default_executor", original)

    leaked = [
        thread
        for thread in set(enumerate_threads()) - before
        if thread.name.startswith("nebius-sdk-") and thread.is_alive()
    ]
    assert leaked == []


def test_executor_partial_start_failure_stops_started_workers(monkeypatch) -> None:
    """A failed worker start must not leak workers that already started."""

    original_start = Thread.start
    worker_starts = 0

    def fail_second_worker(thread: Thread) -> None:
        nonlocal worker_starts
        if thread.name.startswith("nebius-test-worker_"):
            worker_starts += 1
            if worker_starts == 2:
                raise RuntimeError("worker start failed")
        original_start(thread)

    monkeypatch.setattr(Thread, "start", fail_second_worker)
    before = set(enumerate_threads())
    with pytest.raises(RuntimeError, match="worker start failed"):
        DaemonThreadPoolExecutor(3, "nebius-test-worker")

    leaked = [
        thread
        for thread in set(enumerate_threads()) - before
        if thread.name.startswith("nebius-test-worker_") and thread.is_alive()
    ]
    assert leaked == []


def test_executor_construction_failure_closes_new_event_loop(monkeypatch) -> None:
    """Runtime construction must close a loop if executor creation fails."""

    created: list[asyncio.AbstractEventLoop] = []
    new_event_loop = asyncio.new_event_loop

    def capture_loop() -> asyncio.AbstractEventLoop:
        loop = new_event_loop()
        created.append(loop)
        return loop

    def fail_executor(*args: object, **kwargs: object) -> object:
        raise RuntimeError("executor construction failed")

    monkeypatch.setattr(asyncio, "new_event_loop", capture_loop)
    monkeypatch.setattr(runtime_module, "DaemonThreadPoolExecutor", fail_executor)

    with pytest.raises(RuntimeError, match="executor construction failed"):
        AsyncRuntime(None, 2)

    assert len(created) == 1
    assert created[0].is_closed()


def test_loop_thread_start_failure_stops_executor_workers(monkeypatch) -> None:
    """A failed loop-thread start must clean the loop and owned executor."""

    original_start = Thread.start

    def fail_loop_thread(thread: Thread) -> None:
        if thread.name == "nebius-sdk-loop":
            raise RuntimeError("loop start failed")
        original_start(thread)

    monkeypatch.setattr(Thread, "start", fail_loop_thread)
    before = set(enumerate_threads())
    with pytest.raises(RuntimeError, match="loop start failed"):
        AsyncRuntime(None, 2)

    leaked = [
        thread
        for thread in set(enumerate_threads()) - before
        if thread.name.startswith("nebius-sdk-") and thread.is_alive()
    ]
    assert leaked == []


def test_failed_channel_constructor_stops_its_runtime() -> None:
    """A retained constructor traceback must not retain live SDK threads."""

    before = set(enumerate_threads())
    retained_errors: list[BaseException] = []
    try:
        Channel(credentials=NoCredentials(), parent_id="")
    except BaseException as error:
        retained_errors.append(error)
    assert retained_errors
    leaked = [
        thread
        for thread in set(enumerate_threads()) - before
        if thread.name.startswith("nebius-sdk-") and thread.is_alive()
    ]
    assert leaked == []


def test_failed_channel_constructor_uses_graceful_async_shutdown(monkeypatch) -> None:
    """Constructor rollback uses the loop-pumping shutdown path."""

    called = Event()
    original_shutdown_async = AsyncRuntime.shutdown_async

    def observed_shutdown_async(self: AsyncRuntime):
        called.set()
        return original_shutdown_async(self)

    monkeypatch.setattr(AsyncRuntime, "shutdown_async", observed_shutdown_async)

    with pytest.raises(Exception, match="Parent id is empty"):
        Channel(credentials=NoCredentials(), parent_id="")

    assert called.is_set()


@pytest.mark.skipif(not hasattr(os, "fork"), reason="requires os.fork")
def test_runtime_rejects_use_after_fork_without_hanging() -> None:
    """A child must create its own SDK instead of using inherited threads."""

    channel = Channel(credentials=NoCredentials())
    submitted = channel.run_async(asyncio.Event().wait())
    request = Request(
        channel,
        "nebius.compute.v1.DiskService",
        "Get",
        GetDiskRequest(id="forked"),
        Disk,
    )
    stream = object.__new__(StreamRequest)
    stream._process_id = os.getpid()
    stream._state_lock = Lock()
    operation = object.__new__(Operation)
    operation._process_id = os.getpid()
    operation._state_lock = Lock()
    read_fd, write_fd = os.pipe()
    channel._channel_pool_lock.acquire()
    submitted._future._condition.acquire()
    request._future_lock.acquire()
    stream._state_lock.acquire()
    operation._state_lock.acquire()
    child = os.fork()
    if child == 0:
        os.close(read_fd)
        signal.alarm(5)
        outcomes: list[str] = []
        try:
            channel.run_sync(asyncio.sleep(0), timeout=1)
        except RuntimeError as error:
            outcomes.append(str(error))
        else:
            outcomes.append("channel: no error")
        try:
            submitted.done()
        except RuntimeError as error:
            outcomes.append(str(error))
        else:
            outcomes.append("awaitable: no error")
        try:
            request.cancel()
        except RuntimeError as error:
            outcomes.append(str(error))
        else:
            outcomes.append("request: no error")
        try:
            stream.cancel()
        except RuntimeError as error:
            outcomes.append(str(error))
        else:
            outcomes.append("stream: no error")
        try:
            operation.progress_tracker()
        except RuntimeError as error:
            outcomes.append(str(error))
        else:
            outcomes.append("operation: no error")
        os.write(write_fd, "\n".join(outcomes).encode())
        os.close(write_fd)
        os._exit(0)

    operation._state_lock.release()
    stream._state_lock.release()
    request._future_lock.release()
    submitted._future._condition.release()
    channel._channel_pool_lock.release()
    os.close(write_fd)
    try:
        outcome = os.read(read_fd, 4096).decode()
        waited, status = os.waitpid(child, 0)
        assert waited == child
        assert os.waitstatus_to_exitcode(status) == 0
        assert "channel cannot be used after fork" in outcome
        assert "awaitable cannot be used after fork" in outcome
        assert "request cannot be used after fork" in outcome
        assert "stream cannot be used after fork" in outcome
        assert "operation cannot be used after fork" in outcome
    finally:
        os.close(read_fd)
        channel.sync_close(timeout=5)


def test_cross_loop_callback_runs_on_registration_loop() -> None:
    """Public completion callbacks retain Task-like loop affinity."""

    channel = Channel(credentials=NoCredentials())

    async def register() -> tuple[int, int]:
        loop = asyncio.get_running_loop()
        callback_loop: asyncio.Future[int] = loop.create_future()
        submitted = channel.run_async(asyncio.sleep(0, result=42))

        def complete(_: object) -> None:
            callback_loop.set_result(id(asyncio.get_running_loop()))

        submitted.add_done_callback(complete)
        assert await submitted == 42
        return id(loop), await asyncio.wait_for(callback_loop, timeout=5)

    try:
        registration_loop, callback_loop = asyncio.run(register())
        assert callback_loop == registration_loop
    finally:
        channel.sync_close(timeout=5)


def test_completed_callback_rejects_closed_sdk_loop() -> None:
    """Registration fails promptly when no callback loop can run."""

    channel = Channel(credentials=NoCredentials())
    submitted = channel.run_async(asyncio.sleep(0, result=42))
    assert submitted.result(timeout=5) == 42
    channel.sync_close(timeout=5)
    with pytest.raises(RuntimeError, match="callback event loop is closed"):
        submitted.add_done_callback(lambda _: None)


def test_pending_cross_loop_result_does_not_block_async_loop() -> None:
    """A synchronous pending-result read in async code fails promptly."""

    channel = Channel(credentials=NoCredentials())
    release = Event()

    async def pending() -> int:
        while not release.is_set():
            await asyncio.sleep(0)
        return 42

    submitted = channel.run_async(pending())

    async def inspect() -> None:
        with pytest.raises(RuntimeError, match="await it instead"):
            submitted.result()
        with pytest.raises(RuntimeError, match="await it instead"):
            submitted.exception()

    try:
        asyncio.run(inspect())
    finally:
        release.set()
        assert submitted.result(timeout=5) == 42
        channel.sync_close(timeout=5)


def test_stopped_borrowed_loop_rejects_submission_promptly() -> None:
    """The caller must keep a supplied loop running until SDK close."""

    loop, thread = _start_loop()
    channel = Channel(credentials=NoCredentials(), event_loop=loop)
    _stop_loop(loop, thread)

    with pytest.raises(RuntimeError, match="event loop is not running"):
        channel.run_async(asyncio.sleep(0))
    channel._runtime.shutdown()


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


def test_submit_and_close_race_leaves_no_untracked_work() -> None:
    """Close waits until an accepted submission is registered for draining."""

    channel = Channel(credentials=NoCredentials())
    tracking = Event()
    allow_tracking = Event()
    original_track = channel._runtime._track_submission

    def paused_track(submitted: object) -> None:
        tracking.set()
        allow_tracking.wait(timeout=5)
        original_track(submitted)  # type: ignore[arg-type]

    channel._runtime._track_submission = paused_track  # type: ignore[method-assign]
    submitted: list[object] = []
    errors: list[BaseException] = []

    async def pending() -> None:
        await asyncio.Event().wait()

    def submit() -> None:
        try:
            submitted.append(channel.run_async(pending()))
        except BaseException as error:
            errors.append(error)

    def close() -> None:
        try:
            channel.sync_close(timeout=5)
        except BaseException as error:
            errors.append(error)

    submitter = Thread(target=submit)
    submitter.start()
    assert tracking.wait(timeout=5)
    closer = Thread(target=close)
    closer.start()
    sleep(0.05)
    assert closer.is_alive()
    allow_tracking.set()
    submitter.join(timeout=5)
    closer.join(timeout=5)

    assert not submitter.is_alive()
    assert not closer.is_alive()
    assert errors == []
    assert len(submitted) == 1
    assert submitted[0].done()  # type: ignore[attr-defined]


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


def test_bg_task_pre_start_cancellation_closes_caller_coroutine() -> None:
    channel = Channel(credentials=NoCredentials())
    loop_entered = Event()
    unblock_loop = Event()

    async def block_sdk_loop() -> None:
        loop_entered.set()
        unblock_loop.wait(timeout=5)

    async def caller_work() -> None:
        await asyncio.sleep(0)

    blocker = channel.run_async(block_sdk_loop())
    assert loop_entered.wait(timeout=5)
    inner = caller_work()
    background = channel.bg_task(inner)
    try:
        assert background.cancel()
        assert inspect.getcoroutinestate(inner) == inspect.CORO_CLOSED
    finally:
        unblock_loop.set()
        blocker.result(timeout=5)
        channel.sync_close(timeout=5)


def test_bg_task_pre_start_cancellation_reaches_foreign_future() -> None:
    foreign_loop, foreign_thread = _start_loop()
    channel = Channel(credentials=NoCredentials())
    loop_entered = Event()
    unblock_loop = Event()

    async def create_future() -> asyncio.Future[None]:
        return asyncio.get_running_loop().create_future()

    async def block_sdk_loop() -> None:
        loop_entered.set()
        unblock_loop.wait(timeout=5)

    source = asyncio.run_coroutine_threadsafe(
        create_future(),
        foreign_loop,
    ).result(timeout=5)
    blocker = channel.run_async(block_sdk_loop())
    assert loop_entered.wait(timeout=5)
    background = channel.bg_task(source)
    try:
        assert background.cancel()

        async def wait_until_cancelled() -> None:
            for _ in range(100):
                if source.cancelled():
                    return
                await asyncio.sleep(0.01)
            raise AssertionError("foreign Future was not cancelled")

        asyncio.run_coroutine_threadsafe(
            wait_until_cancelled(),
            foreign_loop,
        ).result(timeout=5)
    finally:
        unblock_loop.set()
        blocker.result(timeout=5)
        channel.sync_close(timeout=5)
        _stop_loop(foreign_loop, foreign_thread)


def test_bg_task_pre_start_disposal_consumes_foreign_future_exception() -> None:
    foreign_loop, foreign_thread = _start_loop()
    channel = Channel(credentials=NoCredentials())
    loop_entered = Event()
    unblock_loop = Event()
    loop_errors: list[dict[str, object]] = []
    foreign_loop.call_soon_threadsafe(
        foreign_loop.set_exception_handler,
        lambda loop, context: loop_errors.append(context),
    )

    async def create_failed_future() -> asyncio.Future[None]:
        future = asyncio.get_running_loop().create_future()
        future.set_exception(ValueError("boom"))
        return future

    async def block_sdk_loop() -> None:
        loop_entered.set()
        unblock_loop.wait(timeout=5)

    source = asyncio.run_coroutine_threadsafe(
        create_failed_future(),
        foreign_loop,
    ).result(timeout=5)
    blocker = channel.run_async(block_sdk_loop())
    assert loop_entered.wait(timeout=5)
    background = channel.bg_task(source)
    try:
        assert background.cancel()
        asyncio.run_coroutine_threadsafe(
            asyncio.sleep(0),
            foreign_loop,
        ).result(timeout=5)
        assert source.done()
        assert not source.cancelled()
        assert source._log_traceback is False
        assert loop_errors == []
    finally:
        unblock_loop.set()
        blocker.result(timeout=5)
        channel.sync_close(timeout=5)
        _stop_loop(foreign_loop, foreign_thread)


def test_bg_task_active_cancellation_does_not_force_close_awaitable() -> None:
    channel = Channel(credentials=NoCredentials())
    started = Event()

    class ActiveAwaitable:
        def __init__(self) -> None:
            self.close_calls = 0

        def __await__(self):
            async def run() -> None:
                started.set()
                await asyncio.Event().wait()

            return run().__await__()

        def close(self) -> None:
            self.close_calls += 1

    inner = ActiveAwaitable()
    background = channel.bg_task(inner)
    try:
        assert started.wait(timeout=5)
        assert background.cancel()
        with pytest.raises(ConcurrentCancelledError):
            background.result(timeout=5)
        assert inner.close_calls == 0
    finally:
        channel.sync_close(timeout=5)


def test_runtime_pre_start_cancellation_reaches_cross_loop_handle() -> None:
    source_channel = Channel(credentials=NoCredentials())
    target_channel = Channel(credentials=NoCredentials())
    source_started = Event()
    source_finalized = Event()
    target_entered = Event()
    unblock_target = Event()

    async def source_work() -> None:
        source_started.set()
        try:
            await asyncio.Event().wait()
        finally:
            source_finalized.set()

    async def block_target_loop() -> None:
        target_entered.set()
        unblock_target.wait(timeout=5)

    inner = source_channel.run_async(source_work())
    assert source_started.wait(timeout=5)
    blocker = target_channel.run_async(block_target_loop())
    assert target_entered.wait(timeout=5)
    outer = target_channel.run_async(inner)
    try:
        assert outer.cancel()
        assert inner.cancelled()
    finally:
        unblock_target.set()
        blocker.result(timeout=5)
        target_channel.sync_close(timeout=5)
        source_channel.sync_close(timeout=5)
    assert source_finalized.wait(timeout=5)


def test_context_submission_binding_isolated_for_sdks_sharing_loop() -> None:
    """Nested and concurrent SDK tasks keep runtime-specific ContextVars."""

    loop, thread = _start_loop()
    first = Channel(credentials=NoCredentials(), event_loop=loop)
    second = Channel(credentials=NoCredentials(), event_loop=loop)

    async def inspect_second() -> bool:
        own = second._runtime.protect_current_submission()
        foreign = first._runtime.protect_current_submission()
        await asyncio.sleep(0)
        return (
            own is not None
            and foreign is None
            and second._runtime.protect_current_submission() is own
        )

    async def inspect_first_with_nested_second() -> bool:
        own = first._runtime.protect_current_submission()
        foreign = second._runtime.protect_current_submission()
        nested = second.run_async(inspect_second())
        nested_ok = await nested
        return (
            own is not None
            and foreign is None
            and nested_ok
            and first._runtime.protect_current_submission() is own
        )

    try:
        first_check = first.run_async(inspect_first_with_nested_second())
        second_check = second.run_async(inspect_second())
        assert first_check.result(timeout=5)
        assert second_check.result(timeout=5)
    finally:
        first.sync_close(timeout=5)
        second.sync_close(timeout=5)
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
    finalizer_steps: list[int] = []

    async def pending() -> None:
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            for step in range(3):
                await asyncio.sleep(0)
                finalizer_steps.append(step)
            finalized.set()

    submitted = channel.run_async(pending())
    try:
        assert started.wait(timeout=5)
        channel.sync_close(timeout=5)
        assert submitted.cancelled()
        assert finalized.wait(timeout=5)
        assert finalizer_steps == [0, 1, 2]
        assert loop.is_running()
    finally:
        _stop_loop(loop, thread)


def test_close_does_not_recancel_a_task_already_in_its_finalizer() -> None:
    loop, thread = _start_loop()
    channel = Channel(credentials=NoCredentials(), event_loop=loop)
    started = Event()
    finalizer_started = Event()
    finalized = Event()

    async def pending() -> None:
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            finalizer_started.set()
            await asyncio.sleep(0.05)
            finalized.set()

    submitted = channel.run_async(pending())
    try:
        assert started.wait(timeout=5)
        assert submitted.cancel()
        assert finalizer_started.wait(timeout=5)
        channel.sync_close(timeout=5)
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


def test_internal_close_does_not_recancel_an_externally_cancelled_finalizer() -> None:
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
    finalizer_started = Event()
    finalized = Event()

    async def close_then_finalize() -> None:
        try:
            await channel.close()
        finally:
            finalizer_started.set()
            await asyncio.sleep(0.05)
            finalized.set()

    submitted = channel.run_async(close_then_finalize())
    try:
        assert graceful.started.wait(timeout=5)
        assert submitted.cancel()
        assert finalizer_started.wait(timeout=5)
        graceful.release.set()
        channel._runtime._shutdown_complete.result(timeout=5)
        assert finalized.wait(timeout=5)
    finally:
        graceful.release.set()
        channel._runtime.shutdown_async().result(timeout=5)


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


def test_low_level_awaiter_cancel_publishes_terminal_status() -> None:
    """Task cancellation must publish status even if the SDK call never starts."""

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
    )(GetDiskRequest(id="cancel-await-before-start"))

    async def cancel_and_read_status() -> None:
        task = asyncio.ensure_future(call)
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        release_loop.set()
        code = await asyncio.wait_for(call.code(), timeout=5)
        assert code == grpc.StatusCode.CANCELLED
        assert "cancel" in (await asyncio.wait_for(call.details(), timeout=5)).lower()

    try:
        asyncio.run(cancel_and_read_status())
    finally:
        release_loop.set()
        channel.sync_close(timeout=5)


def test_low_level_active_cancel_skips_blocking_terminal_capture() -> None:
    """Cancellation must not be swallowed by best-effort status capture."""

    native_started = Event()
    terminal_capture_started = Event()
    transport_closed = Event()

    class BlockingCall:
        def __await__(self):
            async def result() -> Disk:
                native_started.set()
                await asyncio.Event().wait()
                return Disk()

            return result().__await__()

        async def _terminal(self) -> object:
            terminal_capture_started.set()
            await asyncio.Event().wait()
            return None

        initial_metadata = _terminal
        trailing_metadata = _terminal
        code = _terminal
        details = _terminal

    class BlockingTransport:
        def unary_unary(self, *args: object, **kwargs: object):
            def invoke(*call_args: object, **call_kwargs: object) -> BlockingCall:
                return BlockingCall()

            return invoke

        def get_state(self) -> grpc.ChannelConnectivity:
            return grpc.ChannelConnectivity.READY

        async def close(self, grace: float | None = None) -> None:
            transport_closed.set()

    class BlockingChannel(Channel):
        def create_address_channel(self, addr: str) -> AddressChannel:
            return AddressChannel(BlockingTransport(), addr)  # type: ignore[arg-type]

    channel = BlockingChannel(credentials=NoCredentials())
    call = channel.unary_unary(
        "/nebius.compute.v1.DiskService/Get",
        lambda request: request.SerializeToString(),
        Disk.FromString,
    )(GetDiskRequest(id="cancel-active"))
    try:
        assert native_started.wait(timeout=5)
        assert call.cancel()
        assert transport_closed.wait(timeout=5)
        assert not terminal_capture_started.is_set()
    finally:
        channel.sync_close(timeout=5)


def test_request_inputs_are_snapshotted_at_first_submission() -> None:
    """External mutation after submission must not race SDK-loop processing."""

    channel = Channel(credentials=NoCredentials())
    loop_blocked = Event()
    release_loop = Event()

    async def block_loop() -> None:
        loop_blocked.set()
        release_loop.wait(timeout=5)

    channel.run_async(block_loop())
    assert loop_blocked.wait(timeout=5)
    source = GetDiskRequest(id="before")
    options = {"scope": "before"}
    request: Request[GetDiskRequest, tuple[str, str, str | None]] = Request(
        channel,
        "nebius.compute.v1.DiskService",
        "Get",
        source,
        Disk,
        metadata=(("x-test", "before"),),
        auth_options=options,
    )
    mutable_metadata = request.input_metadata()

    async def capture() -> tuple[str, str, str | None]:
        return (
            request._input.id,
            request._auth_options["scope"],
            request._input_metadata.get_one("x-test"),
        )

    request._request_with_authorization_loop = capture  # type: ignore[method-assign]

    async def submit_then_mutate() -> tuple[str, str, str | None]:
        pending = asyncio.ensure_future(request)
        await asyncio.sleep(0)
        source.id = "after"
        options["scope"] = "after"
        mutable_metadata["x-test"] = "after"
        post_submit_metadata = request.input_metadata()
        post_submit_metadata["x-test"] = "also-after"
        release_loop.set()
        return await pending

    try:
        assert asyncio.run(submit_then_mutate()) == ("before", "before", "before")
    finally:
        release_loop.set()
        channel.sync_close(timeout=5)


def test_custom_copy_from_payload_retains_pass_through_compatibility() -> None:
    """Unknown serializable payloads are not treated as protobuf messages."""

    class CustomPayload:
        def __init__(self, value: str) -> None:
            self.value = value

        def CopyFrom(self, other: object) -> None:  # noqa: N802
            raise AssertionError("custom CopyFrom must not be used")

        def SerializeToString(self) -> bytes:  # noqa: N802
            return self.value.encode()

    channel = Channel(credentials=NoCredentials())
    payload = CustomPayload("stable")
    request: Request[CustomPayload, bool] = Request(
        channel,
        "custom.Service",
        "Call",
        payload,
        Disk,
    )

    async def capture() -> bool:
        return request._input is payload

    request._request_with_authorization_loop = capture  # type: ignore[method-assign]
    try:
        assert asyncio.run(request._await_result())
    finally:
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


def test_close_keeps_owned_loop_running_until_executor_drains() -> None:
    """An executor worker can finish one SDK-loop round trip during close."""

    channel = Channel(credentials=NoCredentials())
    executor = channel._runtime._executor
    assert executor is not None
    original_shutdown = executor.shutdown
    draining = Event()
    worker_started = Event()
    worker_finished = Event()

    def observed_shutdown(
        wait: bool = True,
        *,
        cancel_futures: bool = False,
    ) -> None:
        draining.set()
        original_shutdown(wait=wait, cancel_futures=cancel_futures)

    executor.shutdown = observed_shutdown  # type: ignore[method-assign]

    def worker() -> None:
        worker_started.set()
        assert draining.wait(timeout=5)
        asyncio.run_coroutine_threadsafe(
            asyncio.sleep(0),
            channel._event_loop,
        ).result(timeout=5)
        worker_finished.set()

    async def internal_work() -> None:
        await asyncio.get_running_loop().run_in_executor(None, worker)

    channel.run_async(internal_work())
    assert worker_started.wait(timeout=5)

    channel.sync_close(timeout=5)

    assert worker_finished.wait(timeout=5)


def test_sync_sdk_calls_fail_fast_from_owned_executor_worker() -> None:
    """A worker cannot block on work that may need the same executor."""

    channel = Channel(credentials=NoCredentials(), executor_max_workers=1)
    errors: list[BaseException] = []

    def worker() -> None:
        try:
            channel.run_sync(asyncio.to_thread(lambda: 42), timeout=5)
        except BaseException as error:
            errors.append(error)
        try:
            channel.sync_close(timeout=5)
        except BaseException as error:
            errors.append(error)
        try:
            asyncio.run(channel.close())
        except BaseException as error:
            errors.append(error)

    async def internal_work() -> None:
        await asyncio.get_running_loop().run_in_executor(None, worker)

    try:
        channel.run_sync(internal_work(), timeout=5)
        assert len(errors) == 3
        assert all(isinstance(error, LoopError) for error in errors)
        assert all("executor worker" in str(error) for error in errors)
    finally:
        channel.sync_close(timeout=5)


def test_cross_loop_handles_fail_fast_from_owned_executor_worker() -> None:
    """A worker cannot wait on a handle whose work may need that worker."""

    channel = Channel(credentials=NoCredentials(), executor_max_workers=1)
    errors: list[BaseException] = []

    async def wait_for_handle(handle: object) -> None:
        await handle  # type: ignore[misc]

    def worker() -> None:
        result_handle = channel.run_async(asyncio.to_thread(lambda: 1))
        exception_handle = channel.run_async(asyncio.to_thread(lambda: 2))
        await_handle = channel.run_async(asyncio.to_thread(lambda: 3))
        for wait in (
            lambda: result_handle.result(timeout=5),
            lambda: exception_handle.exception(timeout=5),
            lambda: asyncio.run(wait_for_handle(await_handle)),
        ):
            try:
                wait()
            except BaseException as error:
                errors.append(error)

    async def internal_work() -> None:
        await asyncio.get_running_loop().run_in_executor(None, worker)

    try:
        channel.run_sync(internal_work(), timeout=5)
        assert len(errors) == 3
        assert all(isinstance(error, RuntimeError) for error in errors)
        assert all("executor worker" in str(error) for error in errors)
    finally:
        channel.sync_close(timeout=5)


def test_submission_cannot_await_its_own_cross_loop_handle() -> None:
    """Self-await fails like native Task self-await instead of deadlocking."""

    channel = Channel(credentials=NoCredentials())
    holder: Future[object] = Future()

    async def await_self() -> None:
        handle = await asyncio.wrap_future(holder)
        await handle  # type: ignore[misc]

    handle = channel.run_async(await_self())
    holder.set_result(handle)
    try:
        with pytest.raises(RuntimeError, match="own submission"):
            handle.result(timeout=5)
    finally:
        channel.sync_close(timeout=5)


def test_borrowed_loop_sync_close_from_external_async_loop_is_rejected() -> None:
    """Sync close cannot block a loop that borrowed SDK work may need."""

    sdk_loop, sdk_thread = _start_loop()
    channel = Channel(credentials=NoCredentials(), event_loop=sdk_loop)

    async def close_from_external_loop() -> None:
        with pytest.raises(LoopError, match="await close"):
            channel.sync_close(timeout=5)

    try:
        asyncio.run(close_from_external_loop())
        assert sdk_loop.is_running()
    finally:
        channel.sync_close(timeout=5)
        _stop_loop(sdk_loop, sdk_thread)


def test_sync_resolver_dispatch_from_external_async_loop_is_rejected() -> None:
    """A synchronous resolver cannot block an event loop it may depend on."""

    async def run() -> None:
        channel = Channel(credentials=NoCredentials())
        try:
            with pytest.raises(LoopError, match="async context"):
                channel.get_addr_from_service_name("example.Service")
        finally:
            await channel.close()

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
