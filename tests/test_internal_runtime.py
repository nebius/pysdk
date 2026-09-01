from __future__ import annotations

import asyncio
import gc
import inspect
import os
import signal
from concurrent.futures import CancelledError as ConcurrentCancelledError
from concurrent.futures import Future
from contextvars import ContextVar
from pathlib import Path
from threading import Barrier, Event, Lock, Thread, current_thread
from threading import enumerate as enumerate_threads
from time import monotonic, sleep
from typing import Any
from weakref import ref

import grpc
import nebius.aio._runtime as runtime_module
import nebius.aio.channel as channel_module
import pytest
from nebius.aio._runtime import (
    AsyncRuntime,
    CrossLoopAwaitable,
    DaemonThreadPoolExecutor,
)
from nebius.aio._task_context import dispose_unstarted_awaitable
from nebius.aio.authorization.authorization import Authenticator, Provider
from nebius.aio.base import AddressChannel
from nebius.aio.channel import (
    Channel,
    ChannelClosedError,
    LoopError,
    NoCredentials,
    SDKError,
)
from nebius.aio.cli_config import Config
from nebius.aio.constant_channel import Constant
from nebius.aio.operation import Operation
from nebius.aio.request import Request
from nebius.aio.route import Route
from nebius.aio.stream import StreamRequest
from nebius.aio.token.exchangeable import Bearer as ExchangeableBearer
from nebius.aio.token.token import Bearer as TokenBearer
from nebius.aio.token.token import Receiver as TokenReceiver
from nebius.aio.token.token import Token
from nebius.api.nebius.compute.v1 import (
    Disk,
    DiskServiceClient,
    GetDiskRequest,
    UpdateDiskRequest,
)
from nebius.api.nebius.iam.v1 import ExchangeTokenRequest
from nebius.base.metadata import Metadata
from nebius.base.service_account.service_account import TokenRequester
from nebius.sdk import SDK


def _start_loop() -> tuple[asyncio.AbstractEventLoop, Thread]:
    ready: Future[asyncio.AbstractEventLoop] = Future()

    def run() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.call_soon(ready.set_result, loop)
        loop.run_forever()
        loop.close()

    thread = Thread(target=run, daemon=True)
    thread.start()
    return ready.result(timeout=5), thread


def _stop_loop(loop: asyncio.AbstractEventLoop, thread: Thread) -> None:
    loop.call_soon_threadsafe(loop.stop)
    thread.join(timeout=5)
    assert not thread.is_alive()


@pytest.mark.skipif(
    not hasattr(asyncio, "eager_task_factory"),
    reason="asyncio eager tasks require Python 3.12 or newer",
)
def test_borrowed_loop_eager_task_factory_does_not_deadlock_submission() -> None:
    """A caller-owned eager task factory may run SDK work during creation."""
    loop, thread = _start_loop()
    configured: Future[None] = Future()

    def configure() -> None:
        loop.set_task_factory(getattr(asyncio, "eager_task_factory"))
        configured.set_result(None)

    loop.call_soon_threadsafe(configure)
    configured.result(timeout=5)
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials(), event_loop=loop)
    try:
        assert channel.run_sync(asyncio.sleep(0, result=42), timeout=5) == 42
    finally:
        try:
            channel.sync_close(timeout=5)
        finally:
            _stop_loop(loop, thread)


def test_owned_runtime_threads_are_daemons_and_stop_on_close() -> None:
    channel = Channel(
        user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials(), executor_max_workers=3
    )
    workers_ready = Barrier(4)

    async def start_workers() -> None:
        loop = asyncio.get_running_loop()
        await asyncio.gather(*(loop.run_in_executor(None, workers_ready.wait) for _ in range(3)))

    submitted = channel.run_async(start_workers())
    workers_ready.wait(timeout=5)
    runtime_threads = [
        thread
        for thread in enumerate_threads()
        if thread.name == "nebius-sdk-loop" or thread.name.startswith("nebius-sdk-worker_")
    ]

    assert len([t for t in runtime_threads if "worker" in t.name]) == 3
    assert all(thread.daemon for thread in runtime_threads)
    submitted.result(timeout=5)

    channel.sync_close(timeout=5)

    assert all(not thread.is_alive() for thread in runtime_threads)


def test_sdk_sets_owned_loop_exception_handler_before_return() -> None:
    """An owned runtime publishes readiness after installing its handler."""
    reported: Future[tuple[asyncio.AbstractEventLoop, dict[str, object]]] = Future()

    def handler(
        loop: asyncio.AbstractEventLoop,
        context: dict[str, Any],
    ) -> None:
        """Capture one owned-loop diagnostic."""
        if not reported.done():
            reported.set_result((loop, context))

    sdk = SDK(
        user_agent_prefix="nebius-python-sdk-tests/1.0",
        credentials=NoCredentials(),
        loop_exception_handler=handler,
    )
    try:

        async def report() -> None:
            """Publish a diagnostic through the configured loop handler."""
            loop = asyncio.get_running_loop()
            assert getattr(loop.get_exception_handler(), "handler", None) is handler
            loop.call_exception_handler({"message": "SDK diagnostic"})

        sdk.run_sync(report(), timeout=5)
        loop, context = reported.result(timeout=5)
        assert loop is sdk._event_loop
        assert context == {"message": "SDK diagnostic"}
    finally:
        sdk.sync_close(timeout=5)


@pytest.mark.parametrize("supplied_loop", [False, True])
def test_sdk_reports_awaitable_returned_by_sync_exception_handler(
    supplied_loop: bool,
) -> None:
    """A synchronous wrapper cannot leak its returned coroutine."""
    handler_body_ran = Event()
    reported: list[dict[str, Any]] = []
    both_reported = Event()

    async def hidden_async_handler() -> None:
        """Represent work hidden behind a synchronous wrapper."""
        handler_body_ran.set()

    def handler(
        _: asyncio.AbstractEventLoop,
        __: dict[str, Any],
    ) -> Any:
        """Return an unsupported awaitable from a synchronous function."""
        return hidden_async_handler()

    loop: asyncio.AbstractEventLoop | None = None
    thread: Thread | None = None
    if supplied_loop:
        loop, thread = _start_loop()
    sdk = SDK(
        user_agent_prefix="nebius-python-sdk-tests/1.0",
        credentials=NoCredentials(),
        event_loop=loop,
        loop_exception_handler=handler,
    )
    try:

        async def report() -> None:
            """Capture the validation diagnostic from the loop thread."""
            running = asyncio.get_running_loop()

            def capture(context: dict[str, Any]) -> None:
                """Store the default-handler diagnostic."""
                reported.append(context)
                if len(reported) == 2:
                    both_reported.set()

            running.default_exception_handler = capture  # type: ignore[method-assign]
            running.call_exception_handler({"message": "SDK diagnostic"})

        sdk.run_sync(report(), timeout=5)
        assert both_reported.wait(timeout=5)
        assert reported[0] == {"message": "SDK diagnostic"}
        context = reported[1]
        assert context["message"] == ("The SDK loop_exception_handler callable returned a value.")
        assert isinstance(context["exception"], TypeError)
        assert str(context["exception"]) == ("The loop_exception_handler callable must return None.")
        assert not handler_body_ran.is_set()
    finally:
        try:
            sdk.sync_close(timeout=5)
        finally:
            if loop is not None and thread is not None:
                _stop_loop(loop, thread)


@pytest.mark.parametrize("supplied_loop", [False, True])
@pytest.mark.parametrize("returned_kind", ["future", "task"])
def test_sdk_does_not_cancel_shared_awaitable_returned_by_exception_handler(
    supplied_loop: bool,
    returned_kind: str,
) -> None:
    """A contract violation does not transfer ownership of shared work."""
    returned: list[asyncio.Future[Any]] = []
    reported: list[dict[str, Any]] = []
    both_reported = Event()

    def handler(
        _: asyncio.AbstractEventLoop,
        __: dict[str, Any],
    ) -> Any:
        """Return loop work that remains owned by the application."""
        return returned[0]

    loop: asyncio.AbstractEventLoop | None = None
    thread: Thread | None = None
    if supplied_loop:
        loop, thread = _start_loop()
    sdk = SDK(
        user_agent_prefix="nebius-python-sdk-tests/1.0",
        credentials=NoCredentials(),
        event_loop=loop,
        loop_exception_handler=handler,
    )
    try:

        async def report() -> None:
            """Return shared work and verify that validation leaves it intact."""
            running = asyncio.get_running_loop()
            if returned_kind == "future":
                shared: asyncio.Future[Any] = running.create_future()
            else:
                shared = running.create_task(asyncio.sleep(3600))
            returned.append(shared)

            def capture(context: dict[str, Any]) -> None:
                """Store the default-handler diagnostic."""
                reported.append(context)
                if len(reported) == 2:
                    both_reported.set()

            running.default_exception_handler = capture  # type: ignore[method-assign]
            running.call_exception_handler({"message": "SDK diagnostic"})
            await asyncio.sleep(0)
            assert not shared.done()
            shared.cancel()
            if isinstance(shared, asyncio.Task):
                with pytest.raises(asyncio.CancelledError):
                    await shared

        sdk.run_sync(report(), timeout=5)
        assert both_reported.wait(timeout=5)
        assert reported[0] == {"message": "SDK diagnostic"}
        context = reported[1]
        assert context["message"] == ("The SDK loop_exception_handler callable returned a value.")
        assert isinstance(context["exception"], TypeError)
    finally:
        try:
            sdk.sync_close(timeout=5)
        finally:
            if loop is not None and thread is not None:
                _stop_loop(loop, thread)


def test_sdk_does_not_close_suspended_coroutine_returned_by_exception_handler() -> None:
    """A handler does not transfer ownership of a suspended coroutine."""
    returned: list[Any] = []
    finalized = Event()
    both_reported = Event()
    reported: list[dict[str, Any]] = []

    class SuspendOnce:
        """Suspend a native coroutine without creating other loop work."""

        def __await__(self) -> Any:
            """Yield control until the test explicitly closes the coroutine."""
            yield None

    async def suspended() -> None:
        """Record when the suspended coroutine is explicitly closed."""
        try:
            await SuspendOnce()
        finally:
            finalized.set()

    def handler(
        _: asyncio.AbstractEventLoop,
        __: dict[str, Any],
    ) -> Any:
        """Return application-owned suspended work."""
        return returned[0]

    sdk = SDK(
        user_agent_prefix="nebius-python-sdk-tests/1.0",
        credentials=NoCredentials(),
        loop_exception_handler=handler,
    )
    try:

        async def report() -> None:
            """Verify handler validation leaves suspended work unchanged."""
            running = asyncio.get_running_loop()
            coroutine = suspended()
            coroutine.send(None)
            returned.append(coroutine)

            def capture(context: dict[str, Any]) -> None:
                """Store both default-handler diagnostics."""
                reported.append(context)
                if len(reported) == 2:
                    both_reported.set()

            running.default_exception_handler = capture  # type: ignore[method-assign]
            running.call_exception_handler({"message": "SDK diagnostic"})
            assert inspect.getcoroutinestate(coroutine) == inspect.CORO_SUSPENDED
            assert not finalized.is_set()
            coroutine.close()
            assert finalized.is_set()

        sdk.run_sync(report(), timeout=5)
        assert both_reported.wait(timeout=5)
        assert reported[0] == {"message": "SDK diagnostic"}
        assert reported[1]["message"] == ("The SDK loop_exception_handler callable returned a value.")
    finally:
        sdk.sync_close(timeout=5)


def test_sdk_rejects_async_loop_exception_handler_before_start() -> None:
    """An asynchronous handler cannot create an unawaited coroutine."""

    async def handler(
        _: asyncio.AbstractEventLoop,
        __: dict[str, Any],
    ) -> None:
        """Represent an unsupported asynchronous exception handler."""

    before = set(enumerate_threads())
    with pytest.raises(
        TypeError,
        match="loop_exception_handler value must be a synchronous callable",
    ):
        SDK(
            user_agent_prefix="nebius-python-sdk-tests/1.0",
            credentials=NoCredentials(),
            loop_exception_handler=handler,  # type: ignore[arg-type]
        )

    created_runtime_threads = [
        thread for thread in set(enumerate_threads()) - before if thread.name.startswith("nebius-sdk-")
    ]
    assert created_runtime_threads == []


def test_sdk_rejects_async_generator_exception_handler_before_start() -> None:
    """An async-generator handler cannot silently discard diagnostics."""

    async def handler(
        _: asyncio.AbstractEventLoop,
        context: dict[str, Any],
    ) -> Any:
        """Represent an unsupported async-generator exception handler."""
        yield context

    before = set(enumerate_threads())
    with pytest.raises(
        TypeError,
        match="loop_exception_handler value must be a synchronous callable",
    ):
        SDK(
            user_agent_prefix="nebius-python-sdk-tests/1.0",
            credentials=NoCredentials(),
            loop_exception_handler=handler,  # type: ignore[arg-type]
        )

    created_runtime_threads = [
        thread for thread in set(enumerate_threads()) - before if thread.name.startswith("nebius-sdk-")
    ]
    assert created_runtime_threads == []


def test_sdk_rejects_noncallable_loop_exception_handler_before_start() -> None:
    """A non-callable handler is rejected before owned threads start."""
    before = set(enumerate_threads())
    with pytest.raises(
        TypeError,
        match="loop_exception_handler value must be callable",
    ):
        SDK(
            user_agent_prefix="nebius-python-sdk-tests/1.0",
            credentials=NoCredentials(),
            loop_exception_handler=object(),  # type: ignore[arg-type]
        )

    created_runtime_threads = [
        thread for thread in set(enumerate_threads()) - before if thread.name.startswith("nebius-sdk-")
    ]
    assert created_runtime_threads == []


def test_sdk_rejects_async_callable_handler_before_supplied_loop_setup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An invalid callable object is rejected before runtime construction."""

    class AsyncHandler:
        """Represent an object with an unsupported asynchronous call method."""

        async def __call__(
            self,
            _: asyncio.AbstractEventLoop,
            __: dict[str, Any],
        ) -> None:
            """Handle one loop diagnostic asynchronously."""

    def unexpected_runtime(*_: Any, **__: Any) -> AsyncRuntime:
        """Fail if validation reaches runtime construction."""
        raise AssertionError("Runtime construction started before validation.")

    loop, thread = _start_loop()
    monkeypatch.setattr(channel_module, "AsyncRuntime", unexpected_runtime)
    try:
        with pytest.raises(
            TypeError,
            match="loop_exception_handler value must be a synchronous callable",
        ):
            SDK(
                user_agent_prefix="nebius-python-sdk-tests/1.0",
                credentials=NoCredentials(),
                event_loop=loop,
                loop_exception_handler=AsyncHandler(),  # type: ignore[arg-type]
            )
    finally:
        _stop_loop(loop, thread)


def test_owned_handler_setter_failure_stops_runtime_threads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Owned-loop startup cleans all resources after handler setter failure."""

    def handler(
        _: asyncio.AbstractEventLoop,
        __: dict[str, Any],
    ) -> None:
        """Represent the handler rejected during owned-loop startup."""

    def fail_setter(_: Any, __: Any) -> None:
        """Reject the handler during owned-loop setup."""
        raise RuntimeError("The test event loop rejected the exception handler.")

    monkeypatch.setattr(asyncio.BaseEventLoop, "set_exception_handler", fail_setter)
    before = set(enumerate_threads())
    with pytest.raises(RuntimeError, match="rejected the exception handler"):
        SDK(
            user_agent_prefix="nebius-python-sdk-tests/1.0",
            credentials=NoCredentials(),
            loop_exception_handler=handler,
        )

    leaked = [
        thread
        for thread in set(enumerate_threads()) - before
        if thread.name.startswith("nebius-sdk-") and thread.is_alive()
    ]
    assert leaked == []


def test_sdk_sets_supplied_loop_exception_handler_on_owner_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A supplied loop retains the explicitly installed handler after close."""
    loop, thread = _start_loop()
    handler_threads: list[int | None] = []
    setter_threads: list[int | None] = []

    def previous_handler(
        _: asyncio.AbstractEventLoop,
        __: dict[str, Any],
    ) -> None:
        """Represent the handler that the SDK replaces."""

    configured: Future[None] = Future()

    def configure_previous() -> None:
        """Install the previous handler on the supplied loop thread."""
        loop.set_exception_handler(previous_handler)
        configured.set_result(None)

    loop.call_soon_threadsafe(configure_previous)
    configured.result(timeout=5)
    original_set_exception_handler = loop.set_exception_handler

    def observed_set_exception_handler(handler: Any) -> None:
        """Record the thread that installs the SDK handler."""
        setter_threads.append(current_thread().ident)
        original_set_exception_handler(handler)

    monkeypatch.setattr(loop, "set_exception_handler", observed_set_exception_handler)

    def handler(
        _: asyncio.AbstractEventLoop,
        __: dict[str, Any],
    ) -> None:
        """Record the thread that receives a supplied-loop diagnostic."""
        handler_threads.append(current_thread().ident)

    sdk = SDK(
        user_agent_prefix="nebius-python-sdk-tests/1.0",
        credentials=NoCredentials(),
        event_loop=loop,
        loop_exception_handler=handler,
    )
    try:

        async def report() -> None:
            """Report a diagnostic through the supplied-loop handler."""
            running = asyncio.get_running_loop()
            running.call_exception_handler({"message": "SDK diagnostic"})

        sdk.run_sync(report(), timeout=5)
        assert setter_threads
        assert set(setter_threads) == {thread.ident}
        assert handler_threads == [thread.ident]
    finally:
        sdk.sync_close(timeout=5)

    try:
        retained: Future[bool] = Future()

        def inspect_handler() -> None:
            """Inspect the retained handler on the supplied loop thread."""
            loop.call_exception_handler({"message": "retained SDK diagnostic"})
            retained.set_result(True)

        loop.call_soon_threadsafe(inspect_handler)
        assert retained.result(timeout=5)
        assert handler_threads == [thread.ident, thread.ident]
    finally:
        _stop_loop(loop, thread)


def test_sdks_sharing_loop_keep_latest_exception_handler_after_close() -> None:
    """Closing shared-loop SDKs does not restore an older handler."""
    loop, thread = _start_loop()
    retained_handler = Event()

    def first_handler(
        _: asyncio.AbstractEventLoop,
        __: dict[str, Any],
    ) -> None:
        """Represent the first SDK's loop handler."""
        raise AssertionError("The loop invoked the replaced SDK handler.")

    def second_handler(
        _: asyncio.AbstractEventLoop,
        __: dict[str, Any],
    ) -> None:
        """Represent the later SDK's loop handler."""
        retained_handler.set()

    first = SDK(
        user_agent_prefix="nebius-python-sdk-tests/1.0",
        credentials=NoCredentials(),
        event_loop=loop,
        loop_exception_handler=first_handler,
    )
    second = SDK(
        user_agent_prefix="nebius-python-sdk-tests/1.0",
        credentials=NoCredentials(),
        event_loop=loop,
        loop_exception_handler=second_handler,
    )
    try:
        first.sync_close(timeout=5)
        second.sync_close(timeout=5)
        retained: Future[bool] = Future()

        def inspect_handler() -> None:
            """Check the loop-wide last-assignment-wins contract."""
            loop.call_exception_handler({"message": "retained SDK diagnostic"})
            installed = loop.get_exception_handler()
            retained.set_result(getattr(installed, "_state", (None, object()))[1] is None)

        loop.call_soon_threadsafe(inspect_handler)
        assert retained.result(timeout=5)
        assert retained_handler.is_set()
    finally:
        first.sync_close(timeout=5)
        second.sync_close(timeout=5)
        _stop_loop(loop, thread)


def test_failed_supplied_loop_constructor_does_not_replace_handler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed constructor preserves the handler and finishes async cleanup."""
    loop, thread = _start_loop()
    shutdowns: list[CrossLoopAwaitable[None]] = []
    shutdown_started = Event()
    original_shutdown_async = AsyncRuntime.shutdown_async

    def observed_shutdown_async(
        runtime: AsyncRuntime,
    ) -> CrossLoopAwaitable[None]:
        """Record borrowed-runtime cleanup started by constructor rollback."""
        shutdown = original_shutdown_async(runtime)
        shutdowns.append(shutdown)
        shutdown_started.set()
        return shutdown

    monkeypatch.setattr(AsyncRuntime, "shutdown_async", observed_shutdown_async)

    def previous_handler(
        _: asyncio.AbstractEventLoop,
        __: dict[str, Any],
    ) -> None:
        """Represent the caller's existing loop handler."""

    def replacement_handler(
        _: asyncio.AbstractEventLoop,
        __: dict[str, Any],
    ) -> None:
        """Represent the handler requested by the failed constructor."""

    configured: Future[None] = Future()

    def configure_previous() -> None:
        """Install the caller's handler on its loop thread."""
        loop.set_exception_handler(previous_handler)
        configured.set_result(None)

    loop.call_soon_threadsafe(configure_previous)
    configured.result(timeout=5)

    try:
        with pytest.raises(SDKError, match="Parent id is empty"):
            SDK(
                user_agent_prefix="nebius-python-sdk-tests/1.0",
                credentials=NoCredentials(),
                event_loop=loop,
                loop_exception_handler=replacement_handler,
                parent_id="",
            )

        assert shutdown_started.wait(timeout=5)
        assert len(shutdowns) == 1
        shutdowns[0].result(timeout=5)

        retained: Future[bool] = Future()

        def inspect_handler() -> None:
            """Check the retained handler on the supplied loop thread."""
            retained.set_result(loop.get_exception_handler() is previous_handler)

        loop.call_soon_threadsafe(inspect_handler)
        assert retained.result(timeout=5)
    finally:
        _stop_loop(loop, thread)


def test_interrupted_supplied_loop_handler_installation_is_cancelled(
    monkeypatch,
) -> None:
    """An interrupted wait cannot install its queued handler later."""
    loop, thread = _start_loop()
    runtime = AsyncRuntime(loop, 2)
    loop_blocked = Event()
    release_loop = Event()

    def previous_handler(
        _: asyncio.AbstractEventLoop,
        __: dict[str, Any],
    ) -> None:
        """Represent the caller's existing loop handler."""

    def replacement_handler(
        _: asyncio.AbstractEventLoop,
        __: dict[str, Any],
    ) -> None:
        """Represent the handler from the interrupted installation."""

    def block_loop() -> None:
        """Install the previous handler and block later callbacks."""
        loop.set_exception_handler(previous_handler)
        loop_blocked.set()
        release_loop.wait(timeout=5)

    class InterruptedFuture(Future[None]):
        """Interrupt the thread that waits for handler installation."""

        def result(self, timeout: float | None = None) -> None:
            """Raise the simulated external interruption."""
            raise KeyboardInterrupt

    loop.call_soon_threadsafe(block_loop)
    assert loop_blocked.wait(timeout=5)
    monkeypatch.setattr(runtime_module, "Future", InterruptedFuture)

    try:
        with pytest.raises(KeyboardInterrupt):
            runtime.set_borrowed_loop_exception_handler(replacement_handler)
    finally:
        release_loop.set()
        monkeypatch.setattr(runtime_module, "Future", Future)

    retained: Future[bool] = Future()

    def inspect_handler() -> None:
        """Check the handler after the cancelled callback can run."""
        retained.set_result(loop.get_exception_handler() is previous_handler)

    loop.call_soon_threadsafe(inspect_handler)
    try:
        assert retained.result(timeout=5)
    finally:
        try:
            runtime.shutdown()
        finally:
            _stop_loop(loop, thread)


def test_supplied_loop_handler_setter_timeout_error_is_preserved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A setter's TimeoutError is not mistaken for a polling timeout."""
    loop, thread = _start_loop()
    runtime = AsyncRuntime(loop, 2)

    def handler(
        _: asyncio.AbstractEventLoop,
        __: dict[str, Any],
    ) -> None:
        """Represent the handler rejected by the loop setter."""

    def fail_setter(_: Any) -> None:
        """Raise the application error that installation must preserve."""
        raise TimeoutError("The loop handler setter failed.")

    monkeypatch.setattr(loop, "set_exception_handler", fail_setter)
    try:
        with pytest.raises(TimeoutError, match="loop handler setter failed"):
            runtime.set_borrowed_loop_exception_handler(handler)
    finally:
        try:
            runtime.shutdown()
        finally:
            _stop_loop(loop, thread)


def test_supplied_loop_handler_installation_has_a_time_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A blocked supplied loop cannot hang handler installation forever."""
    loop, thread = _start_loop()
    runtime = AsyncRuntime(loop, 2)
    loop_blocked = Event()
    release_loop = Event()

    def previous_handler(
        _: asyncio.AbstractEventLoop,
        __: dict[str, Any],
    ) -> None:
        """Represent the handler installed before the blocked callback."""

    def replacement_handler(
        _: asyncio.AbstractEventLoop,
        __: dict[str, Any],
    ) -> None:
        """Represent the handler that must not be installed late."""

    configured: Future[None] = Future()

    def configure_and_block() -> None:
        """Install the previous handler and block the loop thread."""
        loop.set_exception_handler(previous_handler)
        configured.set_result(None)
        loop_blocked.set()
        release_loop.wait(timeout=5)

    loop.call_soon_threadsafe(configure_and_block)
    configured.result(timeout=5)
    assert loop_blocked.wait(timeout=5)
    monkeypatch.setattr(
        runtime_module,
        "_BORROWED_LOOP_HANDLER_INSTALL_TIMEOUT_SECONDS",
        0.05,
    )

    started = monotonic()
    try:
        with pytest.raises(
            RuntimeError,
            match="did not set the SDK exception handler before the time limit",
        ):
            runtime.set_borrowed_loop_exception_handler(replacement_handler)
        assert monotonic() - started < 1
    finally:
        release_loop.set()

    retained: Future[bool] = Future()

    def inspect_handler() -> None:
        """Check that the timed-out assignment stayed cancelled."""
        retained.set_result(loop.get_exception_handler() is previous_handler)

    loop.call_soon_threadsafe(inspect_handler)
    try:
        assert retained.result(timeout=5)
    finally:
        try:
            runtime.shutdown()
        finally:
            _stop_loop(loop, thread)


def test_failed_handler_installation_closes_registered_bearer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Constructor rollback closes resources registered before its last step."""
    loop, thread = _start_loop()
    close_loops: list[asyncio.AbstractEventLoop] = []
    closed = Event()
    runtimes: list[AsyncRuntime] = []
    original_runtime = AsyncRuntime

    def observed_runtime(*args: Any, **kwargs: Any) -> AsyncRuntime:
        """Record the runtime that partial-channel cleanup must stop."""
        runtime = original_runtime(*args, **kwargs)
        runtimes.append(runtime)
        return runtime

    class Bearer(TokenBearer):
        """Record cleanup of a credential registered during construction."""

        def receiver(self) -> TokenReceiver:
            """Reject token use, which this construction test does not need."""
            raise AssertionError("The test bearer receiver was requested.")

        async def close(self, grace: float | None = None) -> None:
            """Record the loop that closes the partial credential."""
            close_loops.append(asyncio.get_running_loop())
            closed.set()

    def handler(
        _: asyncio.AbstractEventLoop,
        __: dict[str, Any],
    ) -> None:
        """Represent the handler rejected after bearer registration."""

    original_set_exception_handler = loop.set_exception_handler

    def fail_sdk_handler(candidate: Any) -> None:
        """Reject only the SDK forwarding handler."""
        if getattr(candidate, "handler", None) is handler:
            raise RuntimeError("The test loop rejected the SDK exception handler.")
        original_set_exception_handler(candidate)

    monkeypatch.setattr(loop, "set_exception_handler", fail_sdk_handler)
    monkeypatch.setattr(channel_module, "AsyncRuntime", observed_runtime)
    try:
        with pytest.raises(RuntimeError, match="rejected the SDK exception handler"):
            SDK(
                user_agent_prefix="nebius-python-sdk-tests/1.0",
                credentials=Bearer(),
                event_loop=loop,
                loop_exception_handler=handler,
            )
        assert closed.wait(timeout=5)
        assert close_loops == [loop]
        assert len(runtimes) == 1
        runtimes[0]._shutdown_complete.result(timeout=5)
    finally:
        _stop_loop(loop, thread)


def test_failed_constructor_starts_shutdown_before_borrowed_cleanup_finishes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A stopped supplied loop cannot strand failed-constructor shutdown."""
    loop, thread = _start_loop()
    runtimes: list[AsyncRuntime] = []
    original_runtime = AsyncRuntime

    def observed_runtime(*args: Any, **kwargs: Any) -> AsyncRuntime:
        """Record the runtime whose loop stops during rollback."""
        runtime = original_runtime(*args, **kwargs)
        runtimes.append(runtime)
        return runtime

    def handler(
        _: asyncio.AbstractEventLoop,
        __: dict[str, Any],
    ) -> None:
        """Represent the handler rejected by the supplied loop."""

    original_set_exception_handler = loop.set_exception_handler

    def fail_sdk_handler(candidate: Any) -> None:
        """Reject only the SDK forwarding handler."""
        if getattr(candidate, "handler", None) is handler:
            raise RuntimeError("The test loop rejected the SDK exception handler.")
        original_set_exception_handler(candidate)

    pending_close: Future[None] = Future()

    def stop_before_cleanup(
        _channel: Channel,
        _grace: float | None,
    ) -> CrossLoopAwaitable[None]:
        """Stop the borrowed loop and return cleanup that cannot complete."""
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=5)
        assert not thread.is_alive()
        return CrossLoopAwaitable(pending_close, loop)

    monkeypatch.setattr(loop, "set_exception_handler", fail_sdk_handler)
    monkeypatch.setattr(channel_module, "AsyncRuntime", observed_runtime)
    monkeypatch.setattr(Channel, "_get_close_handle", stop_before_cleanup)

    with pytest.raises(RuntimeError, match="rejected the SDK exception handler"):
        SDK(
            user_agent_prefix="nebius-python-sdk-tests/1.0",
            credentials=NoCredentials(),
            event_loop=loop,
            loop_exception_handler=handler,
        )

    assert len(runtimes) == 1
    runtimes[0]._shutdown_complete.result(timeout=5)


def test_interrupted_handler_installation_restores_claimed_assignment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Interruption after callback entry restores the prior loop handler."""
    loop, thread = _start_loop()
    runtime = AsyncRuntime(loop, 2)
    setter_entered = Event()
    release_setter = Event()
    restoration_finished = Event()

    def previous_handler(
        _: asyncio.AbstractEventLoop,
        __: dict[str, Any],
    ) -> None:
        """Represent the caller's existing loop handler."""

    def replacement_handler(
        _: asyncio.AbstractEventLoop,
        __: dict[str, Any],
    ) -> None:
        """Represent the interrupted handler assignment."""

    configured: Future[None] = Future()

    def configure_previous() -> None:
        """Install the prior handler on its owner thread."""
        loop.set_exception_handler(previous_handler)
        configured.set_result(None)

    loop.call_soon_threadsafe(configure_previous)
    configured.result(timeout=5)
    original_set_exception_handler = loop.set_exception_handler

    def controlled_set_exception_handler(handler: Any) -> None:
        """Pause the replacement after its future claims callback execution."""
        if getattr(handler, "handler", None) is replacement_handler:
            setter_entered.set()
            assert release_setter.wait(timeout=5)
        original_set_exception_handler(handler)
        if handler is previous_handler:
            restoration_finished.set()

    class InterruptedAfterClaimFuture(Future[Any]):
        """Interrupt only the first wait after the callback claims execution."""

        _first_result = True

        def result(self, timeout: float | None = None) -> Any:
            """Raise once after the loop callback enters the handler setter."""
            if self._first_result:
                self._first_result = False
                assert setter_entered.wait(timeout=5)
                raise KeyboardInterrupt
            return super().result(timeout=timeout)

    monkeypatch.setattr(loop, "set_exception_handler", controlled_set_exception_handler)
    monkeypatch.setattr(runtime_module, "Future", InterruptedAfterClaimFuture)
    with pytest.raises(KeyboardInterrupt):
        runtime.set_borrowed_loop_exception_handler(replacement_handler)
    release_setter.set()
    assert restoration_finished.wait(timeout=5)
    monkeypatch.setattr(runtime_module, "Future", Future)

    retained: Future[bool] = Future()

    def inspect_handler() -> None:
        """Check the guarded restoration after the interrupted assignment."""
        retained.set_result(loop.get_exception_handler() is previous_handler)

    loop.call_soon_threadsafe(inspect_handler)
    try:
        assert retained.result(timeout=5)
    finally:
        try:
            runtime.shutdown()
        finally:
            _stop_loop(loop, thread)


def test_interruption_during_handler_commit_keeps_accepted_assignment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A late interruption cannot erase the handler accepted by the loop."""
    loop, thread = _start_loop()
    runtime = AsyncRuntime(loop, 2)
    replacement_called = Event()

    def previous_handler(
        _: asyncio.AbstractEventLoop,
        __: dict[str, Any],
    ) -> None:
        """Represent the handler installed before the accepted assignment."""

    def replacement_handler(
        _: asyncio.AbstractEventLoop,
        __: dict[str, Any],
    ) -> None:
        """Record use of the assignment accepted before interruption."""
        replacement_called.set()

    configured: Future[None] = Future()

    def configure_previous() -> None:
        """Install the predecessor on the loop-owner thread."""
        loop.set_exception_handler(previous_handler)
        configured.set_result(None)

    loop.call_soon_threadsafe(configure_previous)
    configured.result(timeout=5)
    original_commit = runtime_module._StagedLoopExceptionHandler.commit

    def interrupt_after_commit(
        installed_handler: runtime_module._StagedLoopExceptionHandler,
    ) -> None:
        """Interrupt after the assignment releases its predecessor."""
        original_commit(installed_handler)
        raise KeyboardInterrupt

    monkeypatch.setattr(
        runtime_module._StagedLoopExceptionHandler,
        "commit",
        interrupt_after_commit,
    )
    try:
        with pytest.raises(KeyboardInterrupt):
            runtime.set_borrowed_loop_exception_handler(replacement_handler)

        inspected: Future[bool] = Future()

        def inspect_handler() -> None:
            """Invoke and identify the handler retained after interruption."""
            installed = loop.get_exception_handler()
            inspected.set_result(getattr(installed, "handler", None) is replacement_handler)
            loop.call_exception_handler({"message": "SDK diagnostic"})

        loop.call_soon_threadsafe(inspect_handler)
        assert inspected.result(timeout=5)
        assert replacement_called.wait(timeout=5)
    finally:
        try:
            runtime.shutdown()
        finally:
            _stop_loop(loop, thread)


def test_interrupted_sdk_constructor_does_not_wait_for_borrowed_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Constructor rollback does not wait for an unresponsive borrowed loop."""
    loop, thread = _start_loop()
    runtime = AsyncRuntime(loop, 2)
    loop_blocked = Event()
    release_loop = Event()
    constructor_finished = Event()
    constructor_errors: list[BaseException] = []
    shutdowns: list[CrossLoopAwaitable[None]] = []
    shutdown_started = Event()
    original_shutdown_async = runtime.shutdown_async

    def replacement_handler(
        _: asyncio.AbstractEventLoop,
        __: dict[str, Any],
    ) -> None:
        """Represent the handler from interrupted SDK construction."""

    def block_loop() -> None:
        """Prevent queued construction callbacks from running."""
        loop_blocked.set()
        release_loop.wait(timeout=5)

    def existing_runtime(*_: Any, **__: Any) -> AsyncRuntime:
        """Return the prepared runtime used by the constructor."""
        return runtime

    def interrupt_install(*_: Any, **__: Any) -> None:
        """Interrupt construction before it can install the handler."""
        raise KeyboardInterrupt

    def observed_shutdown_async() -> CrossLoopAwaitable[None]:
        """Record cleanup that the failed constructor starts."""
        shutdown = original_shutdown_async()
        shutdowns.append(shutdown)
        shutdown_started.set()
        return shutdown

    def construct() -> None:
        """Run the interrupted constructor on an observable caller thread."""
        try:
            SDK(
                user_agent_prefix="nebius-python-sdk-tests/1.0",
                credentials=NoCredentials(),
                event_loop=loop,
                loop_exception_handler=replacement_handler,
            )
        except KeyboardInterrupt:
            pass
        except BaseException as error:
            constructor_errors.append(error)
        else:
            constructor_errors.append(AssertionError("The test constructor did not stop."))
        finally:
            constructor_finished.set()

    loop.call_soon_threadsafe(block_loop)
    assert loop_blocked.wait(timeout=5)
    monkeypatch.setattr(channel_module, "AsyncRuntime", existing_runtime)
    monkeypatch.setattr(
        runtime,
        "set_borrowed_loop_exception_handler",
        interrupt_install,
    )
    monkeypatch.setattr(runtime, "shutdown_async", observed_shutdown_async)
    constructor = Thread(target=construct, daemon=True)
    constructor.start()
    try:
        assert constructor_finished.wait(timeout=0.5)
        assert constructor_errors == []
    finally:
        release_loop.set()
        constructor.join(timeout=5)
    assert not constructor.is_alive()
    try:
        assert shutdown_started.wait(timeout=5)
        assert len(shutdowns) == 1
        shutdowns[0].result(timeout=5)
    finally:
        _stop_loop(loop, thread)


def test_stopped_supplied_loop_cannot_install_queued_handler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A cancelled assignment stays cancelled when its loop restarts."""
    ready: Future[asyncio.AbstractEventLoop] = Future()
    first_run_stopped = Event()
    restart = Event()

    def run_reusable_loop() -> None:
        """Run one event loop twice so queued callbacks survive a stop."""
        reusable_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(reusable_loop)
        ready.set_result(reusable_loop)
        reusable_loop.run_forever()
        first_run_stopped.set()
        assert restart.wait(timeout=5)
        reusable_loop.run_forever()
        reusable_loop.close()

    thread = Thread(target=run_reusable_loop, daemon=True)
    thread.start()
    loop = ready.result(timeout=5)
    runtime = AsyncRuntime(loop, 2)
    blocker_entered = Event()
    release_blocker = Event()
    assignment_queued = Event()

    def previous_handler(
        _: asyncio.AbstractEventLoop,
        __: dict[str, Any],
    ) -> None:
        """Represent the caller's existing loop handler."""

    def replacement_handler(
        _: asyncio.AbstractEventLoop,
        __: dict[str, Any],
    ) -> None:
        """Represent the handler queued immediately before loop stop."""

    def block_then_stop() -> None:
        """Stop after the setter queues work outside this ready snapshot."""
        loop.set_exception_handler(previous_handler)
        blocker_entered.set()
        assert release_blocker.wait(timeout=5)
        loop.stop()

    original_call_soon_threadsafe = loop.call_soon_threadsafe

    def observe_assignment(callback: Any, *args: Any) -> Any:
        """Release the stopping callback after assignment enters the queue."""
        handle = original_call_soon_threadsafe(callback, *args)
        if getattr(callback, "__name__", "") == "configure":
            assignment_queued.set()
            release_blocker.set()
        return handle

    loop.call_soon_threadsafe(block_then_stop)
    assert blocker_entered.wait(timeout=5)
    monkeypatch.setattr(loop, "call_soon_threadsafe", observe_assignment)
    with pytest.raises(
        RuntimeError,
        match="supplied event loop stopped before the SDK could set",
    ):
        runtime.set_borrowed_loop_exception_handler(replacement_handler)
    assert assignment_queued.is_set()
    assert first_run_stopped.wait(timeout=5)
    monkeypatch.setattr(loop, "call_soon_threadsafe", original_call_soon_threadsafe)
    restart.set()

    retained: Future[bool] = Future()

    def inspect_handler() -> None:
        """Check that the callback retained cancellation across restart."""
        retained.set_result(loop.get_exception_handler() is previous_handler)

    loop.call_soon_threadsafe(inspect_handler)
    try:
        assert retained.result(timeout=5)
    finally:
        try:
            runtime.shutdown()
        finally:
            _stop_loop(loop, thread)


def test_sdk_sets_supplied_loop_exception_handler_from_that_loop() -> None:
    """Handler installation does not block construction on the supplied loop."""
    loop, thread = _start_loop()
    constructed: Future[SDK] = Future()
    handled = Event()

    def handler(
        _: asyncio.AbstractEventLoop,
        __: dict[str, Any],
    ) -> None:
        """Handle diagnostics from the supplied loop."""
        handled.set()

    def construct() -> None:
        """Construct the SDK on the supplied loop's thread."""
        try:
            sdk = SDK(
                user_agent_prefix="nebius-python-sdk-tests/1.0",
                credentials=NoCredentials(),
                event_loop=loop,
                loop_exception_handler=handler,
            )
            loop.call_exception_handler({"message": "SDK diagnostic"})
        except BaseException as error:
            constructed.set_exception(error)
        else:
            constructed.set_result(sdk)

    loop.call_soon_threadsafe(construct)
    sdk = constructed.result(timeout=5)
    try:
        assert sdk._event_loop is loop
        assert handled.is_set()
    finally:
        try:
            sdk.sync_close(timeout=5)
        finally:
            _stop_loop(loop, thread)


def test_owned_runtime_starts_executor_workers_lazily() -> None:
    """An unused SDK owns a pool but does not consume worker threads."""
    before = set(enumerate_threads())
    channel = Channel(
        user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials(), executor_max_workers=3
    )
    try:
        created_workers = [
            thread for thread in set(enumerate_threads()) - before if thread.name.startswith("nebius-sdk-worker_")
        ]
        assert created_workers == []
    finally:
        channel.sync_close(timeout=5)


@pytest.mark.asyncio()
async def test_default_sdks_run_on_independent_internal_loops_in_parallel() -> None:
    """Default SDK runtimes do not share loop threads or task context."""
    first = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    second = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    both_running = Barrier(2)

    async def identify() -> tuple[int, int]:
        both_running.wait(timeout=5)
        return id(asyncio.get_running_loop()), current_thread().ident or 0

    try:
        identities = await asyncio.gather(
            first.run_async(identify()),
            second.run_async(identify()),
        )
        assert len({loop_id for loop_id, _ in identities}) == 2
        assert len({thread_id for _, thread_id in identities}) == 2
    finally:
        await asyncio.gather(first.close(), second.close())


def test_runtime_startup_failure_is_reported_and_workers_stop(monkeypatch) -> None:
    """An exception in loop-thread setup must not strand the constructor."""
    original = asyncio.BaseEventLoop.set_default_executor

    def fail_setup(
        loop: asyncio.BaseEventLoop,
        executor: object,
    ) -> None:
        raise RuntimeError("The test runtime setup failed.")

    monkeypatch.setattr(asyncio.BaseEventLoop, "set_default_executor", fail_setup)
    before = set(enumerate_threads())
    with pytest.raises(RuntimeError, match="runtime setup failed"):
        AsyncRuntime(None, 2)
    monkeypatch.setattr(asyncio.BaseEventLoop, "set_default_executor", original)

    leaked = [
        thread
        for thread in set(enumerate_threads()) - before
        if thread.name.startswith("nebius-sdk-") and thread.is_alive()
    ]
    assert leaked == []


def test_executor_lazy_start_failure_stops_started_workers(monkeypatch) -> None:
    """A failed lazy worker start must not leak an earlier worker."""
    original_start = Thread.start
    worker_starts = 0

    def fail_second_worker(thread: Thread) -> None:
        nonlocal worker_starts
        if thread.name.startswith("nebius-test-worker_"):
            worker_starts += 1
            if worker_starts == 2:
                raise RuntimeError("The test worker did not start.")
        original_start(thread)

    monkeypatch.setattr(Thread, "start", fail_second_worker)
    before = set(enumerate_threads())
    executor = DaemonThreadPoolExecutor(3, "nebius-test-worker")
    first_started = Event()
    release_first = Event()

    def block_first_worker() -> int:
        first_started.set()
        release_first.wait(timeout=5)
        return 1

    try:
        first = executor.submit(block_first_worker)
        assert first_started.wait(timeout=5)
        with pytest.raises(RuntimeError, match="worker did not start"):
            executor.submit(lambda: 2)
        release_first.set()
        assert first.result(timeout=5) == 1
    finally:
        release_first.set()
        executor.shutdown(wait=True, cancel_futures=True)

    leaked = [
        thread
        for thread in set(enumerate_threads()) - before
        if thread.name.startswith("nebius-test-worker_") and thread.is_alive()
    ]
    assert leaked == []


def test_executor_reuses_idle_worker_for_sequential_submissions() -> None:
    """Completed sequential work does not grow the daemon worker pool."""
    executor = DaemonThreadPoolExecutor(20, "nebius-test-worker-idle")
    try:
        for value in range(100):
            assert executor.submit(lambda item=value: item).result(timeout=5) == value
        assert len(executor._threads) == 1
    finally:
        executor.shutdown(wait=True, cancel_futures=True)


def test_executor_survives_base_exception_from_completion_callback() -> None:
    """One hostile Future callback cannot remove bounded pool capacity."""
    executor = DaemonThreadPoolExecutor(1, "nebius-test-worker-callback")
    work_started = Event()
    release_work = Event()
    callback_ran = Event()

    def first_work() -> int:
        work_started.set()
        release_work.wait(timeout=5)
        return 1

    def fail_callback(_: Future[int]) -> None:
        callback_ran.set()
        raise SystemExit("The test callback failed.")

    try:
        first = executor.submit(first_work)
        assert work_started.wait(timeout=5)
        first.add_done_callback(fail_callback)
        release_work.set()
        assert first.result(timeout=5) == 1
        assert callback_ran.wait(timeout=5)
        assert executor.submit(lambda: 2).result(timeout=5) == 2
        assert len(executor._threads) == 1
    finally:
        release_work.set()
        executor.shutdown(wait=True, cancel_futures=True)


def test_executor_registers_worker_before_it_can_consume_queued_work() -> None:
    """Every started worker is recognizable before it executes SDK work."""
    executor = DaemonThreadPoolExecutor(2, "nebius-test-worker-race")
    first_worker_started = Event()
    release_first_worker = Event()
    original_worker = executor._worker

    def controlled_worker() -> None:
        if current_thread().name.endswith("_0"):
            first_worker_started.set()
            release_first_worker.wait(timeout=5)
        original_worker()

    executor._worker = controlled_worker  # type: ignore[method-assign]
    try:
        first = executor.submit(lambda: executor.owns_thread(current_thread()))
        assert first_worker_started.wait(timeout=5)
        second = executor.submit(lambda: executor.owns_thread(current_thread()))
        assert first.result(timeout=5) is True
        release_first_worker.set()
        assert second.result(timeout=5) is True
    finally:
        release_first_worker.set()
        executor.shutdown(wait=True, cancel_futures=True)


def test_executor_construction_failure_closes_new_event_loop(monkeypatch) -> None:
    """Runtime construction must close a loop if executor creation fails."""
    created: list[asyncio.AbstractEventLoop] = []
    new_event_loop = asyncio.new_event_loop

    def capture_loop() -> asyncio.AbstractEventLoop:
        loop = new_event_loop()
        created.append(loop)
        return loop

    def fail_executor(*args: object, **kwargs: object) -> object:
        raise RuntimeError("The test executor construction failed.")

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
            raise RuntimeError("The test event loop did not start.")
        original_start(thread)

    monkeypatch.setattr(Thread, "start", fail_loop_thread)
    before = set(enumerate_threads())
    with pytest.raises(RuntimeError, match="event loop did not start"):
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
        Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials(), parent_id="")
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
        Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials(), parent_id="")

    assert called.is_set()


def test_channel_constructor_base_exception_stops_its_runtime() -> None:
    """Constructor interruption eagerly rolls back an acquired runtime."""

    class ConstructorAbort(BaseException):
        pass

    class ConfigReader:
        def endpoint(self) -> str:
            raise ConstructorAbort

    before = set(enumerate_threads())
    with pytest.raises(ConstructorAbort):
        Channel(
            user_agent_prefix="nebius-python-sdk-tests/1.0",
            credentials=NoCredentials(),
            config_reader=ConfigReader(),  # type: ignore[arg-type]
        )
    leaked = [
        thread
        for thread in set(enumerate_threads()) - before
        if thread.name.startswith("nebius-sdk-") and thread.is_alive()
    ]
    assert leaked == []


@pytest.mark.asyncio()
async def test_failed_channel_constructor_does_not_block_borrowed_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Borrowed-loop rollback schedules cleanup without waiting on itself."""
    shutdowns = []
    shutdown_started = Event()
    original_shutdown_async = AsyncRuntime.shutdown_async

    def observed_shutdown_async(self: AsyncRuntime):
        shutdown = original_shutdown_async(self)
        shutdowns.append(shutdown)
        shutdown_started.set()
        return shutdown

    monkeypatch.setattr(AsyncRuntime, "shutdown_async", observed_shutdown_async)

    with pytest.raises(Exception, match="Parent id is empty"):
        Channel(
            user_agent_prefix="nebius-python-sdk-tests/1.0",
            credentials=NoCredentials(),
            event_loop=asyncio.get_running_loop(),
            parent_id="",
        )

    async def wait_for_shutdown_start() -> None:
        """Yield until partial-channel resource cleanup starts shutdown."""
        while not shutdown_started.is_set():
            await asyncio.sleep(0)

    await asyncio.wait_for(wait_for_shutdown_start(), timeout=1)
    assert len(shutdowns) == 1
    await asyncio.wait_for(shutdowns[0], timeout=1)
    await asyncio.sleep(0)


def test_shutdown_async_reports_async_generator_cleanup_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Graceful cleanup failures survive best-effort runtime teardown."""
    runtime = AsyncRuntime(None, 2)
    runtime_threads = [runtime._loop_thread]

    async def fail_shutdown_asyncgens() -> None:
        raise RuntimeError("The asynchronous generator did not shut down.")

    monkeypatch.setattr(
        runtime.event_loop,
        "shutdown_asyncgens",
        fail_shutdown_asyncgens,
    )

    with pytest.raises(RuntimeError, match="generator did not shut down"):
        runtime.shutdown_async().result(timeout=5)
    assert all(thread is None or not thread.is_alive() for thread in runtime_threads)


def test_shutdown_async_reports_executor_cleanup_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An executor shutdown failure is reported after fallback cleanup."""
    runtime = AsyncRuntime(None, 2)
    executor = runtime._executor
    assert executor is not None
    original_shutdown = executor.shutdown
    calls = 0

    def fail_once(
        wait: bool = True,
        *,
        cancel_futures: bool = False,
    ) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("The test executor did not shut down.")
        original_shutdown(wait=wait, cancel_futures=cancel_futures)

    monkeypatch.setattr(executor, "shutdown", fail_once)

    with pytest.raises(RuntimeError, match="executor did not shut down"):
        runtime.shutdown_async().result(timeout=5)
    assert calls >= 2


def test_owned_runtime_shutdown_completes_after_loop_was_stopped() -> None:
    """A previously stopped owned loop must not strand shutdown waiters."""
    runtime = AsyncRuntime(None, 2)
    loop_thread = runtime._loop_thread
    assert loop_thread is not None
    runtime.event_loop.call_soon_threadsafe(runtime.event_loop.stop)
    loop_thread.join(timeout=5)
    assert not loop_thread.is_alive()
    assert runtime.event_loop.is_closed()

    runtime.shutdown_async().result(timeout=5)
    runtime.shutdown_async().result(timeout=5)


def test_owned_runtime_shutdown_handles_loop_stop_race(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Loop closure during stop scheduling must still finish all resources."""
    runtime = AsyncRuntime(None, 2)
    loop_thread = runtime._loop_thread
    assert loop_thread is not None
    original_call = runtime.event_loop.call_soon_threadsafe

    def stop_then_report_closed(
        callback: object,
        *args: object,
    ) -> None:
        original_call(callback, *args)  # type: ignore[arg-type]
        loop_thread.join(timeout=5)
        assert not loop_thread.is_alive()
        raise RuntimeError("The event loop is closed.")

    monkeypatch.setattr(
        runtime.event_loop,
        "call_soon_threadsafe",
        stop_then_report_closed,
    )

    runtime.shutdown()
    runtime._shutdown_complete.result(timeout=5)


def test_owned_runtime_shutdown_reports_finalizer_start_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Failure to start an off-loop finalizer must not hang shutdown."""
    runtime = AsyncRuntime(None, 2)
    original_start = Thread.start
    shutdown_called = Event()

    def fail_shutdown_finalizer(thread: Thread) -> None:
        if thread.name == "nebius-sdk-shutdown":
            raise RuntimeError("The shutdown finalizer did not start.")
        original_start(thread)

    monkeypatch.setattr(Thread, "start", fail_shutdown_finalizer)

    async def shutdown_on_sdk_loop() -> None:
        runtime.shutdown()
        shutdown_called.set()

    asyncio.run_coroutine_threadsafe(
        shutdown_on_sdk_loop(),
        runtime.event_loop,
    )
    assert shutdown_called.wait(timeout=5)
    with pytest.raises(RuntimeError, match="shutdown finalizer did not start"):
        runtime._shutdown_complete.result(timeout=5)
    loop_thread = runtime._loop_thread
    assert loop_thread is not None
    loop_thread.join(timeout=5)
    assert not loop_thread.is_alive()


def test_finalizer_start_failure_still_stops_owned_executor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed finalizer start still closes executor admission and workers."""
    runtime = AsyncRuntime(None, 1)
    worker_started = Event()
    release_worker = Event()
    queued_ran = Event()

    def block_worker() -> None:
        worker_started.set()
        release_worker.wait(timeout=5)

    async def start_executor_work() -> None:
        loop = asyncio.get_running_loop()
        loop.run_in_executor(None, block_worker)
        loop.run_in_executor(None, queued_ran.set)

    asyncio.run_coroutine_threadsafe(
        start_executor_work(),
        runtime.event_loop,
    ).result(timeout=5)
    assert worker_started.wait(timeout=5)
    executor = runtime._executor
    assert executor is not None
    workers = list(executor._threads)
    original_start = Thread.start

    def fail_shutdown_finalizer(thread: Thread) -> None:
        if thread.name == "nebius-sdk-shutdown":
            raise RuntimeError("The shutdown finalizer did not start.")
        original_start(thread)

    monkeypatch.setattr(Thread, "start", fail_shutdown_finalizer)

    async def shutdown_on_sdk_loop() -> None:
        runtime.shutdown()

    asyncio.run_coroutine_threadsafe(
        shutdown_on_sdk_loop(),
        runtime.event_loop,
    )
    try:
        with pytest.raises(RuntimeError, match="shutdown finalizer did not start"):
            runtime._shutdown_complete.result(timeout=5)
        with pytest.raises(RuntimeError, match="cannot schedule new work"):
            executor.submit(queued_ran.set)
    finally:
        release_worker.set()
        for worker in workers:
            worker.join(timeout=5)

    assert all(not worker.is_alive() for worker in workers)
    assert not queued_ran.is_set()


def test_owned_runtime_recovers_unexecuted_shutdown_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An accepted prepare callback cannot strand owned-loop shutdown."""
    runtime = AsyncRuntime(None, 2)
    stop_callback_entered = Event()
    release_stop_callback = Event()
    preparation_started = Event()
    original_prepare = runtime._prepare_shutdown

    async def observe_preparation() -> None:
        preparation_started.set()
        await original_prepare()

    monkeypatch.setattr(
        runtime,
        "_prepare_shutdown",
        observe_preparation,
    )

    def stop_before_next_ready_snapshot() -> None:
        runtime.event_loop.stop()
        stop_callback_entered.set()
        release_stop_callback.wait(timeout=5)

    runtime.event_loop.call_soon_threadsafe(stop_before_next_ready_snapshot)
    assert stop_callback_entered.wait(timeout=5)
    shutdown = runtime.shutdown_async()
    release_stop_callback.set()

    shutdown.result(timeout=5)
    assert not preparation_started.is_set()
    loop_thread = runtime._loop_thread
    assert loop_thread is not None
    loop_thread.join(timeout=5)
    assert not loop_thread.is_alive()


def test_cancelled_shutdown_waiter_does_not_poison_shared_completion() -> None:
    """One cancelled shutdown handle cannot cancel later shutdown waiters."""
    runtime = AsyncRuntime(None, 2)
    loop_blocked = Event()
    release_loop = Event()

    def block_loop() -> None:
        loop_blocked.set()
        release_loop.wait(timeout=5)

    runtime.event_loop.call_soon_threadsafe(block_loop)
    assert loop_blocked.wait(timeout=5)
    first = runtime.shutdown_async()
    second = runtime.shutdown_async()
    assert first.cancel()
    try:
        release_loop.set()
        second.result(timeout=5)
    finally:
        release_loop.set()
    assert first.cancelled()
    assert not runtime._shutdown_complete.cancelled()
    runtime.shutdown_async().result(timeout=5)


@pytest.mark.skipif(not hasattr(os, "fork"), reason="requires os.fork")
def test_runtime_rejects_use_after_fork_without_hanging(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A child must create its own SDK instead of using inherited threads."""
    from nebius.aio.channel import _CrossLoopUnaryUnaryCall

    async def invoke_without_transport(self: _CrossLoopUnaryUnaryCall) -> Disk:
        """Keep the wrapper pending without opening a native transport."""
        await asyncio.Event().wait()
        raise AssertionError("The pending call unexpectedly resumed.")

    monkeypatch.setattr(
        _CrossLoopUnaryUnaryCall,
        "_invoke",
        invoke_without_transport,
    )
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    submitted = channel.run_async(asyncio.Event().wait())
    request = Request(
        channel,
        "nebius.compute.v1.DiskService",
        "Get",
        GetDiskRequest(id="forked"),
        Disk,
    )
    low_level_call = channel.unary_unary(
        "/nebius.compute.v1.DiskService/Get",
        lambda value: value.SerializeToString(),
        Disk.FromString,
    )(GetDiskRequest(id="forked-low-level"))
    assert isinstance(low_level_call, _CrossLoopUnaryUnaryCall)
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
    low_level_call._terminal_lock.acquire()
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
            channel.get_state()
        except RuntimeError as error:
            outcomes.append(str(error))
        else:
            outcomes.append("channel state: no error")
        try:
            asyncio.run(channel.channel_ready())
        except RuntimeError as error:
            outcomes.append(str(error))
        else:
            outcomes.append("channel ready: no error")
        serializer_calls: list[object] = []

        def serialize_inherited_request(value: object) -> bytes:
            """Record serializer work that occurs before fork rejection."""
            serializer_calls.append(value)
            return b"serialized"

        try:
            channel.unary_unary(
                "/nebius.compute.v1.DiskService/Get",
                serialize_inherited_request,
                Disk.FromString,
            )(object())
        except RuntimeError as error:
            outcomes.append(str(error))
        else:
            outcomes.append("low-level construction: no error")
        outcomes.append(f"inherited serializer calls: {len(serializer_calls)}")
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
            low_level_call.cancel()
        except RuntimeError as error:
            outcomes.append(str(error))
        else:
            outcomes.append("low-level cancel: no error")
        try:
            low_level_call.debug_error_string()
        except RuntimeError as error:
            outcomes.append(str(error))
        else:
            outcomes.append("low-level debug: no error")
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
    low_level_call._terminal_lock.release()
    request._future_lock.release()
    submitted._future._condition.release()
    channel._channel_pool_lock.release()
    os.close(write_fd)
    try:
        outcome = os.read(read_fd, 4096).decode()
        waited, status = os.waitpid(child, 0)
        assert waited == child
        assert os.waitstatus_to_exitcode(status) == 0
        assert outcome.count("SDK channel after a fork") >= 4
        assert "inherited serializer calls: 0" in outcome
        assert "SDK awaitable after a fork" in outcome
        assert "SDK request after a fork" in outcome
        assert outcome.count("SDK awaitable after a fork") >= 3
        assert "SDK stream after a fork" in outcome
        assert "SDK operation after a fork" in outcome
    finally:
        os.close(read_fd)
        channel.sync_close(timeout=5)


def test_cross_loop_callback_runs_on_registration_loop() -> None:
    """Public completion callbacks retain Task-like loop affinity."""
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())

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


def test_cancelled_shielded_wait_observes_late_wrapper_exception() -> None:
    """An abandoned loop-local wrapper cannot emit an unobserved error."""

    async def run() -> None:
        loop = asyncio.get_running_loop()
        reported: list[dict[str, object]] = []
        previous_handler = loop.get_exception_handler()
        loop.set_exception_handler(lambda _loop, context: reported.append(context))
        source: Future[int] = Future()
        handle = CrossLoopAwaitable(source, loop)
        waiter = asyncio.create_task(handle._wait_shielded())
        try:
            await asyncio.sleep(0)
            waiter.cancel()
            with pytest.raises(asyncio.CancelledError):
                await waiter
            source.set_exception(RuntimeError("The foreign work failed late."))
            await asyncio.sleep(0)
            gc.collect()
            await asyncio.sleep(0)
            assert isinstance(handle.exception(), RuntimeError)
            assert reported == []
        finally:
            loop.set_exception_handler(previous_handler)

    asyncio.run(run())


def test_cancelled_shielded_wait_does_not_retain_caller_loop() -> None:
    """A pending shared submission cannot retain an abandoned caller loop."""
    source: Future[int] = Future()
    owner_loop = asyncio.new_event_loop()
    handle = CrossLoopAwaitable(source, owner_loop)
    caller_loop_ref: list[ref[asyncio.AbstractEventLoop]] = []

    def abandon_wait() -> None:
        caller_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(caller_loop)

        async def cancel_waiter() -> None:
            waiter = asyncio.create_task(handle._wait_shielded())
            await asyncio.sleep(0)
            waiter.cancel()
            with pytest.raises(asyncio.CancelledError):
                await waiter

        caller_loop.run_until_complete(cancel_waiter())
        caller_loop_ref.append(ref(caller_loop))
        caller_loop.close()
        asyncio.set_event_loop(None)

    thread = Thread(target=abandon_wait)
    thread.start()
    thread.join(timeout=5)
    assert not thread.is_alive()
    gc.collect()
    assert caller_loop_ref[0]() is None
    source.set_result(1)
    owner_loop.close()


@pytest.mark.asyncio()
async def test_cancelled_shielded_waits_do_not_accumulate_callbacks() -> None:
    """Cancelled waiters leave one bounded concurrent completion callback."""
    source: Future[int] = Future()
    handle = CrossLoopAwaitable(source, asyncio.get_running_loop())
    callback_count = len(source._done_callbacks)
    for _ in range(100):
        waiter = asyncio.create_task(handle._wait_shielded())
        await asyncio.sleep(0)
        waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiter
        assert handle._waiters == {}
        assert len(source._done_callbacks) == callback_count
    source.set_result(42)
    assert await handle == 42


@pytest.mark.asyncio()
async def test_cancelled_low_level_accessor_does_not_cancel_native_accessor() -> None:
    """Public accessor cancellation does not mutate shared native capture."""
    from nebius.aio.channel import _CrossLoopUnaryUnaryCall

    accessor_started = asyncio.Event()
    accessor_release = asyncio.Event()
    accessor_finished = asyncio.Event()
    accessor_cancelled = False

    class NativeCall:
        async def code(self) -> grpc.StatusCode:
            nonlocal accessor_cancelled
            accessor_started.set()
            try:
                await accessor_release.wait()
            except asyncio.CancelledError:
                accessor_cancelled = True
                raise
            finally:
                accessor_finished.set()
            return grpc.StatusCode.OK

    call = object.__new__(_CrossLoopUnaryUnaryCall)
    call._terminal_lock = Lock()
    call._terminal = {}
    call._call_ready = asyncio.Event()
    call._call_ready.set()
    call._call = NativeCall()
    pending = asyncio.create_task(call._call_result("code"))
    await accessor_started.wait()
    pending.cancel()
    with pytest.raises(asyncio.CancelledError):
        await pending
    assert not accessor_cancelled
    accessor_release.set()
    await accessor_finished.wait()
    assert not accessor_cancelled


def test_completed_callback_releases_registration_context() -> None:
    """A retained completed handle must not retain callback ContextVars."""

    class Payload:
        pass

    payload_var: ContextVar[Payload | None] = ContextVar(
        "callback_payload",
        default=None,
    )
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())

    async def register():
        submitted = channel.run_async(asyncio.sleep(0, result=42))
        callback_done = asyncio.Event()
        payload = Payload()
        payload_ref = ref(payload)
        token = payload_var.set(payload)
        try:
            submitted.add_done_callback(lambda _: callback_done.set())
        finally:
            payload_var.reset(token)
        del payload
        assert await submitted == 42
        await asyncio.wait_for(callback_done.wait(), timeout=5)
        return submitted, payload_ref

    try:
        retained_handle, payload_ref = asyncio.run(register())
        gc.collect()
        assert retained_handle.done()
        assert payload_ref() is None
    finally:
        channel.sync_close(timeout=5)


def test_completed_callback_rejects_closed_sdk_loop() -> None:
    """Registration fails promptly when no callback loop can run."""
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    submitted = channel.run_async(asyncio.sleep(0, result=42))
    assert submitted.result(timeout=5) == 42
    channel.sync_close(timeout=5)
    with pytest.raises(RuntimeError, match="callback event loop is not running"):
        submitted.add_done_callback(lambda _: None)


def test_runtime_tracks_submission_before_task_can_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Runtime tracking is visible before submitted work can call close."""
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    tracking_entered = Event()
    release_tracking = Event()
    task_started = Event()
    submitted: Future[CrossLoopAwaitable[int]] = Future()
    original_track = channel._runtime._track_submission

    def delayed_track(handle: CrossLoopAwaitable[object]) -> None:
        """Hold tracking so the test can inspect task-start ordering."""
        tracking_entered.set()
        assert release_tracking.wait(timeout=5)
        original_track(handle)

    monkeypatch.setattr(channel._runtime, "_track_submission", delayed_track)

    async def work() -> int:
        """Report task entry and return a value."""
        task_started.set()
        return 42

    def submit() -> None:
        """Submit work while the tracking hook is blocked."""
        try:
            submitted.set_result(channel.run_async(work()))
        except BaseException as error:
            submitted.set_exception(error)

    thread = Thread(target=submit)
    try:
        thread.start()
        assert tracking_entered.wait(timeout=5)
        assert not task_started.wait(timeout=0.05)
        release_tracking.set()
        thread.join(timeout=5)
        assert not thread.is_alive()
        assert submitted.result(timeout=5).result(timeout=5) == 42
    finally:
        release_tracking.set()
        if thread.is_alive():
            thread.join(timeout=5)
        channel.sync_close(timeout=5)


def test_pending_cross_loop_result_does_not_block_async_loop() -> None:
    """A synchronous pending-result read in async code fails promptly."""
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    release = Event()

    async def pending() -> int:
        """Wait until the test permits the submission to finish."""
        while not release.is_set():
            await asyncio.sleep(0)
        return 42

    submitted = channel.run_async(pending())

    async def inspect() -> None:
        """Verify that synchronous inspection cannot block this loop."""
        with pytest.raises(RuntimeError, match="Await the work instead"):
            submitted.result()
        with pytest.raises(RuntimeError, match="Await the work instead"):
            submitted.exception()

    try:
        asyncio.run(inspect())
    finally:
        release.set()
        assert submitted.result(timeout=5) == 42
        channel.sync_close(timeout=5)


@pytest.mark.asyncio()
@pytest.mark.parametrize("work_kind", ("request", "operation", "stream"))
async def test_dispatch_gate_waiter_is_drained_after_cancellation(
    work_kind: str,
) -> None:
    """Cancellation does not leave a dispatch-start waiter on the caller loop."""
    from nebius.api.nebius.common.v1 import Operation as OperationMessage

    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    loop_blocked = Event()
    release_loop = Event()

    async def block_sdk_loop() -> None:
        """Block SDK-loop dispatch until the cancellation check finishes."""
        loop_blocked.set()
        release_loop.wait(timeout=5)

    blocker = channel.run_async(block_sdk_loop())
    assert await asyncio.to_thread(loop_blocked.wait, 5)
    baseline = asyncio.all_tasks()
    if work_kind == "request":
        request: Request[GetDiskRequest, Disk] = Request(
            channel,
            "nebius.compute.v1.DiskService",
            "Get",
            GetDiskRequest(id="cancel-dispatch-waiter"),
            Disk,
            timeout=1,
        )
        pending = asyncio.create_task(request._await_result())
    elif work_kind == "operation":
        operation = Operation(
            ".nebius.common.v1.OperationService.Get",
            channel,
            OperationMessage(id="cancel-dispatch-waiter"),
        )
        pending = asyncio.create_task(operation.update(timeout=1))
    else:
        stream = StreamRequest(
            channel=channel,
            route=Route("acme.Service", "Watch"),
            request=GetDiskRequest(id="cancel-dispatch-waiter"),
            result_class=Disk,
            client_streaming=False,
            server_streaming=True,
            timeout=1,
        )
        pending = asyncio.create_task(stream._on_sdk_loop(asyncio.sleep(0)))

    try:
        await asyncio.sleep(0)
        pending.cancel()
        with pytest.raises(asyncio.CancelledError):
            await pending
        await asyncio.sleep(0)
        leaked = [
            task for task in asyncio.all_tasks() - baseline if not task.done() and task is not asyncio.current_task()
        ]
        assert leaked == []
    finally:
        release_loop.set()
        await asyncio.to_thread(blocker.result, 5)
        await channel.close()


def test_stopped_borrowed_loop_rejects_submission_promptly() -> None:
    """The caller must keep a supplied loop running until SDK close."""
    loop, thread = _start_loop()
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials(), event_loop=loop)
    _stop_loop(loop, thread)

    with pytest.raises(RuntimeError, match="event loop is not running"):
        channel.run_async(asyncio.sleep(0))
    channel._runtime.shutdown()


def test_borrowed_loop_stop_after_shutdown_dispatch_completes() -> None:
    """An accepted but stranded close callback cannot hang shutdown."""
    loop, thread = _start_loop()
    runtime = AsyncRuntime(loop, 2)
    runtime._start_shutdown_preparation_on_loop = loop.stop  # type: ignore[method-assign]
    shutting_down = runtime.shutdown_async()
    thread.join(timeout=5)
    assert not thread.is_alive()
    shutting_down.result(timeout=5)
    runtime.shutdown_async().result(timeout=5)


def test_repeated_shutdown_does_not_block_borrowed_owner_loop() -> None:
    """Owner-loop re-entry cannot wait on its pending shutdown completion."""
    loop, thread = _start_loop()
    runtime = AsyncRuntime(loop, 2)
    returned = Event()
    with runtime._shutdown_lock:
        # Model the interval after another shutdown caller publishes admission
        # but before that caller publishes its terminal result.
        runtime._shutdown = True

    def repeat_shutdown() -> None:
        """Repeat shutdown from the borrowed owner loop."""
        runtime.shutdown()
        returned.set()

    loop.call_soon_threadsafe(repeat_shutdown)
    try:
        assert returned.wait(timeout=1)
    finally:
        runtime._complete_shutdown()
        _stop_loop(loop, thread)


def test_borrowed_shutdown_reports_rejected_preparation_task() -> None:
    """A rejecting custom task factory cannot strand shutdown completion."""
    loop, thread = _start_loop()
    runtime = AsyncRuntime(loop, 2)
    factory_installed = Event()

    def reject_task(loop: object, coroutine: object, **kwargs: object) -> None:
        """Reject creation of the runtime shutdown task."""
        raise RuntimeError("The test rejected the shutdown task.")

    def install_factory() -> None:
        """Install the rejecting factory on the borrowed loop."""
        loop.set_task_factory(reject_task)  # type: ignore[arg-type]
        factory_installed.set()

    loop.call_soon_threadsafe(install_factory)
    assert factory_installed.wait(timeout=5)
    try:
        with pytest.raises(RuntimeError, match="The test rejected the shutdown task"):
            runtime.shutdown_async().result(timeout=5)
        with pytest.raises(RuntimeError, match="The test rejected the shutdown task"):
            runtime.shutdown_async().result(timeout=5)
        assert loop.is_running()
    finally:
        _stop_loop(loop, thread)


def test_close_has_no_nested_cleanup_task_creation_boundary() -> None:
    """Close cleanup cannot be stranded by a second task-factory rejection."""
    loop, thread = _start_loop()
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials(), event_loop=loop)
    resource_closed = Event()

    class Resource:
        """Record cleanup that must bypass the rejecting task factory."""

        async def close(self, grace: float | None = None) -> None:
            """Record resource cleanup on the supplied loop."""
            assert asyncio.get_running_loop() is loop
            resource_closed.set()

    channel._gracefuls.add(Resource())  # type: ignore[arg-type]
    factory_installed = Event()

    def reject_while_cleanup_pending(loop, coroutine, **kwargs):
        """Reject a nested task while channel cleanup is pending."""
        completion = channel._close_completion
        if completion is not None and not completion.done():
            raise RuntimeError("The test rejected the nested cleanup task.")
        return asyncio.Task(coroutine, loop=loop, **kwargs)

    def install_factory() -> None:
        """Install the conditional task factory on the borrowed loop."""
        loop.set_task_factory(reject_while_cleanup_pending)
        factory_installed.set()

    loop.call_soon_threadsafe(install_factory)
    assert factory_installed.wait(timeout=5)
    try:
        channel.sync_close(timeout=5)
        assert channel._close_completion is not None
        assert channel._close_completion.done()
        assert channel._close_completion.result(timeout=0) is None
        assert resource_closed.is_set()
    finally:
        _stop_loop(loop, thread)


def test_borrowed_shutdown_watcher_start_failure_falls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Watcher resource failure cannot leave borrowed shutdown pending."""
    loop, thread = _start_loop()
    runtime = AsyncRuntime(loop, 2)

    def reject_thread_start(self: Thread) -> None:
        """Reject creation of the borrowed-loop watcher thread."""
        raise RuntimeError("The test rejected the watcher thread start.")

    monkeypatch.setattr(runtime_module.Thread, "start", reject_thread_start)
    try:
        runtime.shutdown_async().result(timeout=5)
        runtime.shutdown_async().result(timeout=5)
        assert loop.is_running()
    finally:
        _stop_loop(loop, thread)


def test_cross_loop_awaitable_can_be_shared_by_external_loops() -> None:
    """Two external loops can await one SDK submission handle."""
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    started = Event()
    release = Event()

    async def work() -> int:
        """Return the SDK loop identity after both waiters start."""
        started.set()
        while not release.is_set():
            await asyncio.sleep(0)
        return id(asyncio.get_running_loop())

    submitted = channel.run_async(work())
    loop_a, thread_a = _start_loop()
    loop_b, thread_b = _start_loop()

    async def wait_for_result() -> int:
        """Await the shared result from an external loop."""
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


@pytest.mark.asyncio()
async def test_rejected_sync_wait_preserves_running_cross_loop_handle() -> None:
    """An invalid blocking wait cannot cancel independently scheduled work."""
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    started = Event()
    release = Event()

    async def work() -> int:
        started.set()
        while not release.is_set():
            await asyncio.sleep(0)
        return 42

    submitted = channel.run_async(work())
    assert await asyncio.to_thread(started.wait, 5)
    fresh = asyncio.sleep(0)
    try:
        with pytest.raises(LoopError, match="asynchronous context"):
            channel.run_sync(submitted)
        assert not submitted.cancelled()
        with pytest.raises(LoopError, match="asynchronous context"):
            channel.run_sync(fresh)
        assert inspect.getcoroutinestate(fresh) is inspect.CORO_CLOSED
        release.set()
        assert await submitted == 42
    finally:
        release.set()
        await channel.close()


def test_rejected_executor_sync_wait_preserves_running_handle() -> None:
    """An executor-worker rejection also leaves shared work untouched."""
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    started = Event()
    release = Event()
    errors: list[BaseException] = []

    async def work() -> int:
        started.set()
        while not release.is_set():
            await asyncio.sleep(0)
        return 42

    submitted = channel.run_async(work())
    assert started.wait(timeout=5)

    def reject_wait() -> None:
        try:
            channel.run_sync(submitted)
        except BaseException as error:
            errors.append(error)

    async def invoke_worker() -> None:
        await asyncio.get_running_loop().run_in_executor(None, reject_wait)

    try:
        channel.run_sync(invoke_worker(), timeout=5)
        assert len(errors) == 1
        assert isinstance(errors[0], LoopError)
        assert "executor worker" in str(errors[0])
        assert not submitted.cancelled()
        release.set()
        assert submitted.result(timeout=5) == 42
    finally:
        release.set()
        channel.sync_close(timeout=5)


def test_sdk_executor_rejects_synchronous_wait_on_another_sdk() -> None:
    """A worker cannot form a finite-pool wait cycle with another SDK."""
    first = Channel(
        user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials(), executor_max_workers=1
    )
    second = Channel(
        user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials(), executor_max_workers=1
    )

    def call_second() -> None:
        second.run_sync(asyncio.sleep(0))

    async def invoke_first_worker() -> None:
        await asyncio.get_running_loop().run_in_executor(None, call_second)

    pending = second.run_async(asyncio.Event().wait())

    def wait_for_second_handle() -> None:
        pending.result()

    async def invoke_handle_wait() -> None:
        await asyncio.get_running_loop().run_in_executor(None, wait_for_second_handle)

    try:
        submitted = first.run_async(invoke_first_worker())
        with pytest.raises(LoopError, match="SDK.*executor worker"):
            submitted.result(timeout=5)
        submitted = first.run_async(invoke_handle_wait())
        with pytest.raises(RuntimeError, match="SDK executor worker"):
            submitted.result(timeout=5)
    finally:
        pending.cancel()
        first.sync_close(timeout=5)
        second.sync_close(timeout=5)


def test_run_sync_is_safe_from_many_threads() -> None:
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
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


def test_completed_submission_handle_does_not_retain_input_awaitable() -> None:
    """A reusable result handle must not keep completed caller work alive."""
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())

    class Work:
        def __await__(self):
            async def result() -> int:
                return 42

            return result().__await__()

    work = Work()
    work_ref = ref(work)
    submitted = channel.run_async(work)  # type: ignore[arg-type]
    del work
    try:
        assert submitted.result(timeout=5) == 42
        gc.collect()
        assert work_ref() is None
        assert submitted.result() == 42
    finally:
        channel.sync_close(timeout=5)


def test_submit_and_close_race_leaves_no_untracked_work() -> None:
    """Close waits until an accepted submission is registered for draining."""
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
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
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())

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


def test_pending_future_from_stopped_loop_fails_bridge_promptly() -> None:
    """A stopped owner loop cannot deliver a pending future's completion."""
    foreign_loop = asyncio.new_event_loop()
    source = foreign_loop.create_future()
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    try:
        bridged = channel.run_async(source)
        with pytest.raises(
            RuntimeError,
            match="event loop that owns the foreign Future is not running",
        ):
            bridged.result(timeout=5)
    finally:
        channel.sync_close(timeout=5)
        foreign_loop.close()


def test_completed_foreign_future_from_stopped_loop_fails_without_inspection() -> None:
    """A stopped owner prevents even terminal foreign-Future inspection."""
    foreign_loop = asyncio.new_event_loop()
    source = foreign_loop.create_future()
    source.set_result(42)
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    try:
        with pytest.raises(
            RuntimeError,
            match="event loop that owns the foreign Future is not running",
        ):
            channel.run_async(source).result(timeout=5)
    finally:
        channel.sync_close(timeout=5)
        foreign_loop.close()


def test_foreign_future_is_inspected_only_on_its_owner_loop() -> None:
    """Bridge setup, completion, and result reads preserve Future affinity."""
    loop, thread = _start_loop()
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())

    class StrictFuture(asyncio.Future[int]):
        def _check_owner(self) -> None:
            assert asyncio.get_running_loop() is self.get_loop()

        def done(self) -> bool:
            self._check_owner()
            return super().done()

        def cancelled(self) -> bool:
            self._check_owner()
            return super().cancelled()

        def exception(self) -> BaseException | None:
            self._check_owner()
            return super().exception()

        def result(self) -> int:
            self._check_owner()
            return super().result()

    async def create_future() -> StrictFuture:
        return StrictFuture()

    source = asyncio.run_coroutine_threadsafe(create_future(), loop).result(timeout=5)
    bridged = channel.run_async(source)
    try:
        loop.call_soon_threadsafe(source.set_result, 42)
        assert bridged.result(timeout=5) == 42
    finally:
        channel.sync_close(timeout=5)
        _stop_loop(loop, thread)


def test_cancelled_bridge_observes_completed_foreign_future_exception() -> None:
    """Bridge cancellation consumes a source error before releasing the source."""
    loop, thread = _start_loop()
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    owner_blocked = Event()
    release_owner = Event()
    exception_observed = Event()

    class StrictFuture(asyncio.Future[int]):
        def exception(self) -> BaseException | None:
            assert asyncio.get_running_loop() is self.get_loop()
            exception_observed.set()
            return super().exception()

    async def create_failed_future() -> StrictFuture:
        source = StrictFuture()
        source.set_exception(RuntimeError("The foreign operation failed."))
        return source

    def block_owner() -> None:
        owner_blocked.set()
        release_owner.wait(timeout=5)

    source = asyncio.run_coroutine_threadsafe(
        create_failed_future(),
        loop,
    ).result(timeout=5)
    loop.call_soon_threadsafe(block_owner)
    assert owner_blocked.wait(timeout=5)
    bridged = channel.run_async(source)
    try:
        assert bridged.cancel()
        release_owner.set()
        assert exception_observed.wait(timeout=5)
        assert not source._log_traceback
    finally:
        release_owner.set()
        channel.sync_close(timeout=5)
        _stop_loop(loop, thread)


def test_foreign_future_disposal_decides_on_owner_loop_after_completion() -> None:
    """Disposal observes a racing terminal exception on the Future's loop."""
    loop, thread = _start_loop()
    callback_started = Event()
    allow_completion = Event()
    exception_observed = Event()

    class StrictFuture(asyncio.Future[int]):
        def _check_owner(self) -> None:
            assert asyncio.get_running_loop() is self.get_loop()

        def done(self) -> bool:
            self._check_owner()
            return super().done()

        def cancelled(self) -> bool:
            self._check_owner()
            return super().cancelled()

        def exception(self) -> BaseException | None:
            self._check_owner()
            exception_observed.set()
            return super().exception()

        def cancel(self, msg: object = None) -> bool:
            self._check_owner()
            return super().cancel(msg)

    async def create_future() -> StrictFuture:
        return StrictFuture()

    source = asyncio.run_coroutine_threadsafe(create_future(), loop).result(timeout=5)

    def complete_before_disposal_callback() -> None:
        callback_started.set()
        assert allow_completion.wait(timeout=5)
        source.set_exception(RuntimeError("The work finished before disposal."))

    loop.call_soon_threadsafe(complete_before_disposal_callback)
    assert callback_started.wait(timeout=5)
    try:
        assert dispose_unstarted_awaitable(source)
        allow_completion.set()
        assert exception_observed.wait(timeout=5)
    finally:
        allow_completion.set()
        _stop_loop(loop, thread)


def test_unstarted_custom_awaitable_is_not_closed_on_unknown_thread() -> None:
    """Opaque awaitables need an explicit thread-safe disposal hook."""

    class Awaitable:
        def __init__(self) -> None:
            self.close_calls = 0

        def __await__(self):
            async def result() -> None:
                return None

            return result().__await__()

        def close(self) -> None:
            self.close_calls += 1

    awaitable = Awaitable()
    assert not dispose_unstarted_awaitable(awaitable)
    assert awaitable.close_calls == 0


def test_bg_task_bridges_foreign_loop_future() -> None:
    loop, thread = _start_loop()
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())

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
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
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


def test_bg_task_start_failure_disposes_caller_awaitable() -> None:
    """Accepted background work is disposed if task creation later fails."""
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    rejection = RuntimeError("The test rejected the background task.")
    disposed = Event()

    class Awaitable:
        def __await__(self):
            return asyncio.sleep(0).__await__()

        def _cancel_unstarted_threadsafe(self) -> bool:
            disposed.set()
            return True

    def reject_once(loop, coroutine, **kwargs):
        loop.set_task_factory(None)
        raise rejection

    async def install() -> None:
        asyncio.get_running_loop().set_task_factory(reject_once)

    channel.run_async(install()).result(timeout=5)
    try:
        submitted = channel.bg_task(Awaitable())
        with pytest.raises(RuntimeError) as raised:
            submitted.result(timeout=5)
        assert raised.value is rejection
        assert disposed.wait(timeout=5)
    finally:
        channel.sync_close(timeout=5)


def test_bg_task_pre_start_cancellation_reaches_foreign_future() -> None:
    foreign_loop, foreign_thread = _start_loop()
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
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
            raise AssertionError("The SDK did not cancel the foreign Future.")

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
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    loop_entered = Event()
    unblock_loop = Event()
    loop_errors: list[dict[str, object]] = []
    foreign_loop.call_soon_threadsafe(
        foreign_loop.set_exception_handler,
        lambda loop, context: loop_errors.append(context),
    )

    async def create_failed_future() -> asyncio.Future[None]:
        future = asyncio.get_running_loop().create_future()
        future.set_exception(ValueError("The test future failed."))
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
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
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
    source_channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    target_channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
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


def test_runtime_rejects_resubmitting_current_handle() -> None:
    """A child wrapper cannot hide a pending self-await cycle."""
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    holder: Future[CrossLoopAwaitable[int]] = Future()

    async def parent() -> int:
        own_handle = await asyncio.wrap_future(holder)
        with pytest.raises(RuntimeError, match="submit its own SDK submission handle"):
            channel.run_async(own_handle)
        return 42

    submitted = channel.run_async(parent())
    holder.set_result(submitted)
    try:
        assert submitted.result(timeout=5) == 42
    finally:
        channel.sync_close(timeout=5)


def test_submission_failure_runs_threadsafe_disposal_hook_outside_locks(
    monkeypatch,
) -> None:
    """A thread-safe disposal hook may re-enter channel state on rejection."""
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    original_submit = channel._event_loop.call_soon_threadsafe
    closed: list[grpc.ChannelConnectivity] = []

    class ReentrantAwaitable:
        def __await__(self):
            async def result() -> None:
                return None

            return result().__await__()

        def _cancel_unstarted_threadsafe(self) -> bool:
            closed.append(channel.get_state())
            return True

    def reject_dispatch(*args, **kwargs):
        raise RuntimeError("The test dispatch failed.")

    monkeypatch.setattr(
        channel._event_loop,
        "call_soon_threadsafe",
        reject_dispatch,
    )
    try:
        with pytest.raises(RuntimeError, match="test dispatch failed"):
            channel.run_async(ReentrantAwaitable())  # type: ignore[arg-type]
        assert closed == [grpc.ChannelConnectivity.READY]
    finally:
        monkeypatch.setattr(
            channel._event_loop,
            "call_soon_threadsafe",
            original_submit,
        )
        channel.sync_close(timeout=5)


def test_context_submission_binding_isolated_for_sdks_sharing_loop() -> None:
    """Nested and concurrent SDK tasks keep runtime-specific ContextVars."""
    loop, thread = _start_loop()
    first = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials(), event_loop=loop)
    second = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials(), event_loop=loop)

    async def inspect_second() -> bool:
        own = second._runtime.protect_current_submission()
        foreign = first._runtime.protect_current_submission()
        await asyncio.sleep(0)
        return own is not None and foreign is None and second._runtime.protect_current_submission() is own

    async def inspect_first_with_nested_second() -> bool:
        own = first._runtime.protect_current_submission()
        foreign = second._runtime.protect_current_submission()
        nested = second.run_async(inspect_second())
        nested_ok = await nested
        return own is not None and foreign is None and nested_ok and first._runtime.protect_current_submission() is own

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
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())

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


def test_borrowed_runtime_shutdown_drains_tracked_task_finalizer() -> None:
    """Shutdown completion follows asynchronous finalization on a borrowed loop."""
    loop, thread = _start_loop()
    runtime = AsyncRuntime(loop, 2)
    started = Event()
    finalizing = Event()
    finalized = Event()

    async def work() -> None:
        try:
            started.set()
            await asyncio.Event().wait()
        finally:
            finalizing.set()
            await asyncio.sleep(0.05)
            finalized.set()

    runtime.submit(work())
    assert started.wait(timeout=5)
    try:
        runtime.shutdown_async().result(timeout=5)
        assert finalizing.is_set()
        assert finalized.is_set()
        assert loop.is_running()
    finally:
        runtime.shutdown_async().result(timeout=5)
        _stop_loop(loop, thread)


@pytest.mark.parametrize("asynchronous", [False, True])
def test_channel_close_preserves_cleanup_and_shutdown_failures(
    monkeypatch,
    asynchronous: bool,
) -> None:
    """A runtime-shutdown error is chained behind the primary close error."""
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    close_error = RuntimeError("The channel cleanup failed.")
    shutdown_error = RuntimeError("The runtime shutdown failed.")
    close_future: Future[None] = Future()
    close_future.set_exception(close_error)
    shutdown_future: Future[None] = Future()
    shutdown_future.set_exception(shutdown_error)
    close_handle = CrossLoopAwaitable(close_future, channel._event_loop)
    shutdown_handle = CrossLoopAwaitable(shutdown_future, channel._event_loop)
    original_get_close_handle = channel._get_close_handle
    original_shutdown_async = channel._runtime.shutdown_async
    monkeypatch.setattr(channel, "_get_close_handle", lambda grace: close_handle)
    monkeypatch.setattr(channel._runtime, "shutdown_async", lambda: shutdown_handle)
    try:
        with pytest.raises(RuntimeError, match="channel cleanup failed") as raised:
            if asynchronous:
                asyncio.run(channel.close())
            else:
                channel.sync_close(timeout=5)
        assert raised.value is close_error
        assert raised.value.__cause__ is shutdown_error
    finally:
        monkeypatch.setattr(channel, "_get_close_handle", original_get_close_handle)
        monkeypatch.setattr(
            channel._runtime,
            "shutdown_async",
            original_shutdown_async,
        )
        channel.sync_close(timeout=5)


@pytest.mark.parametrize("timeout_phase", ["cleanup", "shutdown"])
def test_sync_close_preserves_terminal_timeout_error_identity(
    monkeypatch: pytest.MonkeyPatch,
    timeout_phase: str,
) -> None:
    """Completed cleanup timeouts are not mistaken for wait expiration."""
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    terminal_error = TimeoutError(f"The {timeout_phase} phase failed because its time limit expired.")
    close_future: Future[None] = Future()
    shutdown_future: Future[None] = Future()
    if timeout_phase == "cleanup":
        close_future.set_exception(terminal_error)
        shutdown_future.set_result(None)
    else:
        close_future.set_result(None)
        shutdown_future.set_exception(terminal_error)
    close_handle = CrossLoopAwaitable(close_future, channel._event_loop)
    shutdown_handle = CrossLoopAwaitable(shutdown_future, channel._event_loop)
    original_get_close_handle = channel._get_close_handle
    original_shutdown_async = channel._runtime.shutdown_async
    monkeypatch.setattr(channel, "_get_close_handle", lambda grace: close_handle)
    monkeypatch.setattr(channel._runtime, "shutdown_async", lambda: shutdown_handle)
    try:
        with pytest.raises(TimeoutError) as raised:
            channel.sync_close(timeout=5)
        assert raised.value is terminal_error
    finally:
        monkeypatch.setattr(channel, "_get_close_handle", original_get_close_handle)
        monkeypatch.setattr(
            channel._runtime,
            "shutdown_async",
            original_shutdown_async,
        )
        channel.sync_close(timeout=5)


def test_supplied_loop_is_not_stopped_or_reconfigured() -> None:
    loop, thread = _start_loop()
    original_executor = getattr(loop, "_default_executor", None)
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials(), event_loop=loop)
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
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=configured_provider)
    try:
        provider = channel.get_authorization_provider()
        assert provider is configured_provider
        provider = channel._get_runtime_authorization_provider()
        assert provider is not None
        authenticator = provider.authenticator()
        asyncio.run(authenticator.authenticate(Metadata()))

        async def retry() -> bool:
            return authenticator.can_retry(RuntimeError("The test request failed."))

        assert channel.run_sync(retry(), timeout=5) is False
        assert calls == [id(channel._event_loop)] * 3
    finally:
        channel.sync_close(timeout=5)


def test_synchronous_wait_preserves_request_one_shot_contract() -> None:
    """A synchronous wait consumes the same one-shot claim as ``await``."""
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    request: Request[GetDiskRequest, Disk] = Request(
        channel,
        "nebius.compute.v1.DiskService",
        "Get",
        GetDiskRequest(id="one-shot-sync-wait"),
        Disk,
    )
    rpc_count = 0

    async def result() -> Disk:
        nonlocal rpc_count
        rpc_count += 1
        return Disk()

    request._request_with_authorization_loop = result  # type: ignore[method-assign]
    try:
        assert isinstance(request.wait(), Disk)
        with pytest.raises(RuntimeError, match="cannot await the same request"):
            request.wait()

        async def await_again() -> None:
            await request

        with pytest.raises(RuntimeError, match="cannot await the same request"):
            asyncio.run(await_again())
        assert rpc_count == 1
    finally:
        channel.sync_close(timeout=5)


def test_request_wait_for_ready_default_and_native_option() -> None:
    """The public readiness option is initialized and reaches gRPC."""
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    observed: list[bool | None] = []

    class NativeChannel:
        def unary_unary(self, *args: object, **kwargs: object):
            def invoke(
                request: object,
                *,
                wait_for_ready: bool | None,
                **call_kwargs: object,
            ) -> object:
                observed.append(wait_for_ready)
                return object()

            return invoke

    override = object.__new__(AddressChannel)
    override.channel = NativeChannel()  # type: ignore[assignment]
    request: Request[GetDiskRequest, Disk] = Request(
        channel,
        "nebius.compute.v1.DiskService",
        "Get",
        GetDiskRequest(id="wait-for-ready"),
        Disk,
        grpc_channel_override=override,
    )

    async def send() -> None:
        assert request.wait_for_ready is True
        request.wait_for_ready = False
        request._send(timeout=1)

    try:
        channel.run_sync(send(), timeout=5)
        assert observed == [False]
    finally:
        channel.sync_close(timeout=5)


def test_legacy_request_wait_binds_task_to_channel_sync_loop() -> None:
    """A legacy sync runner creates the request task on its private loop."""
    policy_loop = asyncio.new_event_loop()
    private_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(policy_loop)

    class LegacyChannel:
        def get_authorization_provider(self) -> None:
            return None

        def run_sync(self, awaitable, timeout=None):
            return private_loop.run_until_complete(awaitable)

    request: Request[GetDiskRequest, Disk] = Request(
        LegacyChannel(),  # type: ignore[arg-type]
        "nebius.compute.v1.DiskService",
        "Get",
        GetDiskRequest(id="legacy-private-loop"),
        Disk,
    )
    expected = Disk()

    async def result() -> Disk:
        return expected

    request._request_with_authorization_loop = result  # type: ignore[method-assign]
    try:
        assert request.wait() is expected
        assert isinstance(request._future, asyncio.Future)
        assert request._future.get_loop() is private_loop
    finally:
        asyncio.set_event_loop(None)
        policy_loop.close()
        private_loop.close()


@pytest.mark.asyncio()
async def test_request_releases_override_when_authenticator_setup_fails() -> None:
    """Pre-leased request transports are released before native setup."""
    released: list[tuple[object | None, bool]] = []

    class FailingProvider:
        def authenticator(self) -> object:
            raise RuntimeError("The authenticator setup failed.")

    class LegacyChannel:
        def get_authorization_provider(self) -> FailingProvider:
            return FailingProvider()

        def return_channel(self, address: object | None) -> None:
            released.append((address, False))

    override = object.__new__(AddressChannel)
    request: Request[GetDiskRequest, Disk] = Request(
        LegacyChannel(),  # type: ignore[arg-type]
        "nebius.compute.v1.DiskService",
        "Get",
        GetDiskRequest(id="auth-setup-failure"),
        Disk,
        grpc_channel_override=override,
    )

    with pytest.raises(RuntimeError, match="authenticator setup failed"):
        await request
    assert released == [(override, False)]


@pytest.mark.asyncio()
async def test_request_releases_override_when_authentication_is_cancelled() -> None:
    """Cancellation during authentication releases a pre-leased transport."""
    entered = asyncio.Event()
    release_completed = asyncio.Event()
    released: list[tuple[object | None, bool]] = []

    class BlockingAuthenticator:
        async def authenticate(self, *args: object) -> None:
            entered.set()
            await asyncio.Event().wait()

    class Provider:
        def authenticator(self) -> BlockingAuthenticator:
            return BlockingAuthenticator()

    class LegacyChannel:
        def get_authorization_provider(self) -> Provider:
            return Provider()

        def return_channel(self, address: object | None) -> None:
            released.append((address, False))
            release_completed.set()

    override = object.__new__(AddressChannel)
    request: Request[GetDiskRequest, Disk] = Request(
        LegacyChannel(),  # type: ignore[arg-type]
        "nebius.compute.v1.DiskService",
        "Get",
        GetDiskRequest(id="cancel-authentication"),
        Disk,
        grpc_channel_override=override,
    )
    waiter = asyncio.create_task(request._await_result())
    await entered.wait()
    waiter.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiter
    await asyncio.wait_for(release_completed.wait(), timeout=1)
    assert released == [(override, False)]


@pytest.mark.parametrize(
    ("timeout", "auth_timeout", "authorization_enabled"),
    ((0.01, 5, False), (5, 0.01, True), (0.01, None, False)),
    ids=("request-timeout", "authorization-timeout", "unlimited-auth"),
)
def test_synchronous_request_timeout_cancels_before_delayed_start(
    timeout: float,
    auth_timeout: float | None,
    authorization_enabled: bool,
) -> None:
    """A direct cross-loop wait timeout cannot leave the RPC queued."""
    from nebius.aio.service_error import RequestError as ServiceRequestError

    loop_blocked = Event()
    release_loop = Event()
    rpc_started = Event()
    from nebius.aio.token.static import Bearer as StaticBearer

    credentials = StaticBearer("token") if authorization_enabled else NoCredentials()
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=credentials)

    async def block_sdk_loop() -> None:
        loop_blocked.set()
        release_loop.wait(timeout=5)

    blocker = channel.run_async(block_sdk_loop())
    assert loop_blocked.wait(timeout=5)
    request: Request[GetDiskRequest, Disk] = Request(
        channel,
        "nebius.compute.v1.DiskService",
        "Get",
        GetDiskRequest(id="sync-timeout-before-start"),
        Disk,
        timeout=timeout,
        auth_timeout=auth_timeout,
    )
    request._send = lambda timeout: rpc_started.set()  # type: ignore[method-assign]
    try:
        started = monotonic()
        with pytest.raises(ServiceRequestError) as raised:
            request.wait()
        assert raised.value.status.code is grpc.StatusCode.DEADLINE_EXCEEDED
        assert monotonic() - started < 0.5
        release_loop.set()
        blocker.result(timeout=5)
        sleep(0.05)
        assert not rpc_started.is_set()
        assert request.cancelled()
    finally:
        release_loop.set()
        channel.sync_close(timeout=5)


def test_synchronous_request_wait_uses_remaining_submission_deadline() -> None:
    """A previously submitted request does not receive a fresh sync budget."""
    from nebius.aio.service_error import RequestError as ServiceRequestError

    loop_blocked = Event()
    release_loop = Event()
    rpc_started = Event()
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())

    async def block_sdk_loop() -> None:
        loop_blocked.set()
        release_loop.wait(timeout=5)

    blocker = channel.run_async(block_sdk_loop())
    assert loop_blocked.wait(timeout=5)
    request: Request[GetDiskRequest, Disk] = Request(
        channel,
        "nebius.compute.v1.DiskService",
        "Get",
        GetDiskRequest(id="sync-remaining-deadline"),
        Disk,
        timeout=0.2,
        auth_timeout=5,
    )
    request._send = lambda timeout: rpc_started.set()  # type: ignore[method-assign]
    request._ensure_submitted()
    sleep(0.15)
    started = monotonic()
    try:
        with pytest.raises(ServiceRequestError):
            request.wait()
        assert monotonic() - started < 0.32
        release_loop.set()
        blocker.result(timeout=5)
        assert not rpc_started.wait(timeout=0.05)
    finally:
        release_loop.set()
        channel.sync_close(timeout=5)


@pytest.mark.parametrize("disable_explicitly", (False, True))
def test_synchronous_unlimited_request_ignores_inapplicable_auth_timeout(
    disable_explicitly: bool,
) -> None:
    """An irrelevant auth budget cannot cap an unlimited blocking wait."""
    from nebius.aio.authorization.options import OPTION_TYPE, Types

    class ProbeChannel:
        def _has_authorization_provider(self) -> bool:
            return disable_explicitly

    request: Request[GetDiskRequest, Disk] = Request(
        ProbeChannel(),  # type: ignore[arg-type]
        "nebius.compute.v1.DiskService",
        "Get",
        GetDiskRequest(id="sync-unlimited-auth-budget"),
        Disk,
        timeout=None,
        auth_timeout=0.01,
        auth_options={OPTION_TYPE: Types.DISABLE} if disable_explicitly else None,
    )
    assert request._sync_wait_timeout() is None
    with request._future_lock:
        request._future = object()  # type: ignore[assignment]
        request._submission_deadline = None
    assert request._sync_wait_timeout() is None


@pytest.mark.asyncio()
@pytest.mark.parametrize(
    ("timeout", "auth_timeout", "authorization_enabled"),
    ((0.05, 5, False), (5, 0.05, True), (0.05, 5, True)),
    ids=("request-timeout", "authorization-timeout", "authorized-dispatch"),
)
async def test_async_request_timeout_includes_sdk_loop_queueing(
    timeout: float,
    auth_timeout: float,
    authorization_enabled: bool,
) -> None:
    """An async deadline expires even while the SDK loop cannot dispatch."""
    loop_blocked = Event()
    release_loop = Event()
    rpc_started = Event()
    from nebius.aio.token.static import Bearer as StaticBearer

    credentials = StaticBearer("token") if authorization_enabled else NoCredentials()
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=credentials)

    async def block_sdk_loop() -> None:
        loop_blocked.set()
        release_loop.wait(timeout=5)

    blocker = channel.run_async(block_sdk_loop())
    assert await asyncio.to_thread(loop_blocked.wait, 5)
    request: Request[GetDiskRequest, Disk] = Request(
        channel,
        "nebius.compute.v1.DiskService",
        "Get",
        GetDiskRequest(id="async-timeout-before-start"),
        Disk,
        timeout=timeout,
        auth_timeout=auth_timeout,
    )
    request._send = lambda timeout: rpc_started.set()  # type: ignore[method-assign]
    started = monotonic()
    try:
        with pytest.raises(TimeoutError, match="request timed out"):
            await request
        assert monotonic() - started < 0.5
        release_loop.set()
        await blocker
        await asyncio.sleep(0.05)
        assert not rpc_started.is_set()
        assert request.cancelled()
    finally:
        release_loop.set()
        await channel.close()


@pytest.mark.asyncio()
@pytest.mark.parametrize("disable_explicitly", (False, True))
async def test_async_request_auth_timeout_only_applies_when_authorizing(
    disable_explicitly: bool,
) -> None:
    """An auth-only budget cannot shorten an unauthenticated request."""
    from nebius.aio.authorization.options import OPTION_TYPE, Types
    from nebius.aio.token.static import Bearer as StaticBearer

    loop_blocked = Event()
    release_loop = Event()
    credentials = StaticBearer("token") if disable_explicitly else NoCredentials()
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=credentials)

    async def block_sdk_loop() -> None:
        loop_blocked.set()
        release_loop.wait(timeout=5)

    blocker = channel.run_async(block_sdk_loop())
    assert await asyncio.to_thread(loop_blocked.wait, 5)
    request: Request[GetDiskRequest, Disk] = Request(
        channel,
        "nebius.compute.v1.DiskService",
        "Get",
        GetDiskRequest(id="auth-timeout-not-request-timeout"),
        Disk,
        timeout=1,
        auth_timeout=0.02,
        auth_options={OPTION_TYPE: Types.DISABLE} if disable_explicitly else None,
    )
    pending = asyncio.create_task(request._await_result())
    try:
        await asyncio.sleep(0.08)
        assert not pending.done()
        pending.cancel()
        with pytest.raises(asyncio.CancelledError):
            await pending
    finally:
        release_loop.set()
        await blocker
        await channel.close()


@pytest.mark.asyncio()
async def test_request_timeout_excludes_slow_authentication() -> None:
    """Authentication consumes auth budget but not request-only budget."""

    class SlowAuthenticator(Authenticator):
        async def authenticate(
            self,
            metadata: Metadata,
            timeout: float | None = None,
            options: dict[str, str] | None = None,
        ) -> None:
            await asyncio.sleep(0.08)

        def can_retry(
            self,
            err: Exception,
            options: dict[str, str] | None = None,
        ) -> bool:
            return False

    class SlowProvider(Provider):
        def authenticator(self) -> Authenticator:
            return SlowAuthenticator()

    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=SlowProvider())
    request: Request[GetDiskRequest, Disk] = Request(
        channel,
        "nebius.compute.v1.DiskService",
        "Get",
        GetDiskRequest(id="independent-auth-clock"),
        Disk,
        timeout=0.05,
        auth_timeout=0.5,
    )
    remaining: list[float] = []

    async def observe_request_budget(
        outer_deadline: float | None = None,
        *,
        defer_unauthenticated_release: bool = False,
    ) -> Disk:
        assert outer_deadline is not None
        assert request._request_deadline is not None
        remaining.append(request._request_deadline - monotonic())
        return Disk()

    request._retry_loop = observe_request_budget  # type: ignore[method-assign]
    try:
        assert isinstance(await request, Disk)
        assert remaining and 0 < remaining[0] <= 0.05
    finally:
        await channel.close()


@pytest.mark.asyncio()
async def test_legacy_request_does_not_guess_provider_before_authentication() -> None:
    """A legacy provider discovered in-loop does not activate the request clock."""

    class SlowAuthenticator:
        async def authenticate(
            self,
            metadata: Metadata,
            timeout: float | None = None,
            options: dict[str, str] | None = None,
        ) -> None:
            await asyncio.sleep(0.08)

        def can_retry(
            self,
            err: Exception,
            options: dict[str, str] | None = None,
        ) -> bool:
            return False

    class SlowProvider:
        def authenticator(self) -> SlowAuthenticator:
            return SlowAuthenticator()

    class LegacyChannel:
        def parent_id(self) -> None:
            return None

        def get_authorization_provider(self) -> SlowProvider:
            return SlowProvider()

    channel = Constant(
        "nebius.compute.v1.DiskService.Get",
        LegacyChannel(),  # type: ignore[arg-type]
    )
    request: Request[GetDiskRequest, Disk] = Request(
        channel,
        "nebius.compute.v1.DiskService",
        "Get",
        GetDiskRequest(id="legacy-independent-auth-clock"),
        Disk,
        timeout=0.02,
        auth_timeout=0.5,
    )

    async def finish_after_authentication(
        outer_deadline: float | None = None,
        *,
        defer_unauthenticated_release: bool = False,
    ) -> Disk:
        return Disk()

    request._retry_loop = finish_after_authentication  # type: ignore[method-assign]
    assert isinstance(await request, Disk)


@pytest.mark.parametrize("provider_state", (True, False, None))
def test_constant_preserves_authorization_provider_probe_state(
    provider_state: bool | None,
) -> None:
    """Constant forwards definite and unknown provider capability states."""

    class Source:
        def parent_id(self) -> None:
            return None

        def _has_authorization_provider(self) -> bool | None:
            return provider_state

    channel = Constant(
        "nebius.compute.v1.DiskService.Get",
        Source(),  # type: ignore[arg-type]
    )
    assert channel._has_authorization_provider() is provider_state


@pytest.mark.asyncio()
async def test_token_timeout_includes_sdk_loop_queueing() -> None:
    """A token deadline expires without starting a late receiver fetch."""
    loop_blocked = Event()
    release_loop = Event()
    fetch_started = Event()

    class Receiver(TokenReceiver):
        async def _fetch(self, timeout=None, options=None):
            fetch_started.set()
            return Token("late-token")

        def can_retry(self, err, options=None):
            return False

    class Bearer(TokenBearer):
        def receiver(self):
            return Receiver()

    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=Bearer())

    async def block_sdk_loop() -> None:
        loop_blocked.set()
        release_loop.wait(timeout=5)

    blocker = channel.run_async(block_sdk_loop())
    assert await asyncio.to_thread(loop_blocked.wait, 5)
    try:
        with pytest.raises(TimeoutError, match="token fetch timed out"):
            await channel.get_token(0.05)
        release_loop.set()
        await blocker
        await asyncio.sleep(0.05)
        assert not fetch_started.is_set()
    finally:
        release_loop.set()
        await channel.close()


@pytest.mark.asyncio()
async def test_token_options_are_snapshotted_before_sdk_loop_dispatch() -> None:
    """Caller mutation cannot change token options already submitted."""
    loop_blocked = Event()
    release_loop = Event()
    received: list[dict[str, str] | None] = []

    class Receiver(TokenReceiver):
        async def _fetch(self, timeout=None, options=None):
            received.append(options)
            return Token("snapshot-token")

        def can_retry(self, err, options=None):
            return False

    class Bearer(TokenBearer):
        def receiver(self):
            return Receiver()

    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=Bearer())

    async def block_sdk_loop() -> None:
        loop_blocked.set()
        release_loop.wait(timeout=5)

    blocker = channel.run_async(block_sdk_loop())
    assert await asyncio.to_thread(loop_blocked.wait, 5)
    options = {"scope": "before"}
    token_task = asyncio.create_task(channel.get_token(5, options))
    await asyncio.sleep(0)
    options["scope"] = "after"
    try:
        release_loop.set()
        token = await token_task
        await blocker
        assert token.token == "snapshot-token"
        assert received == [{"scope": "before"}]
    finally:
        release_loop.set()
        await channel.close()


def test_sync_token_options_are_snapshotted_before_run_sync() -> None:
    """A sync token call fixes mutable options on the caller thread."""
    run_sync_entered = Event()
    release_run_sync = Event()
    received: list[dict[str, str] | None] = []
    errors: list[BaseException] = []
    results: list[Token] = []

    class Receiver(TokenReceiver):
        async def _fetch(self, timeout=None, options=None):
            received.append(options)
            return Token("sync-snapshot-token")

        def can_retry(self, err, options=None):
            return False

    class Bearer(TokenBearer):
        def receiver(self):
            return Receiver()

    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=Bearer())
    original_run_sync = channel.run_sync

    def pause_run_sync(awaitable, timeout=None):
        run_sync_entered.set()
        release_run_sync.wait(timeout=5)
        return original_run_sync(awaitable, timeout)

    channel.run_sync = pause_run_sync  # type: ignore[method-assign]
    options = {"scope": "before"}

    def fetch() -> None:
        try:
            results.append(channel.get_token_sync(5, options))
        except BaseException as error:
            errors.append(error)

    thread = Thread(target=fetch)
    thread.start()
    assert run_sync_entered.wait(timeout=5)
    options["scope"] = "after"
    release_run_sync.set()
    thread.join(timeout=5)
    try:
        assert not thread.is_alive()
        assert errors == []
        assert [token.token for token in results] == ["sync-snapshot-token"]
        assert received == [{"scope": "before"}]
    finally:
        release_run_sync.set()
        channel.run_sync = original_run_sync  # type: ignore[method-assign]
        channel.sync_close(timeout=5)


def test_sync_token_deadline_starts_before_run_sync_dispatch() -> None:
    """A sync token timeout cannot become work time after delayed dispatch."""
    from time import sleep

    fetch_started = Event()

    class Receiver(TokenReceiver):
        """Record an unexpected token receiver call."""

        async def _fetch(self, timeout=None, options=None):
            """Return a token only if the SDK incorrectly starts the fetch."""
            fetch_started.set()
            return Token("late-sync-token")

        def can_retry(self, err, options=None):
            """Disable retries for this deadline test."""
            return False

    class Bearer(TokenBearer):
        """Create the observable receiver."""

        def receiver(self):
            """Return a receiver that records fetch calls."""
            return Receiver()

    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=Bearer())
    original_run_sync = channel.run_sync

    def delay_run_sync(awaitable, timeout=None):
        """Delay SDK dispatch without consuming its cleanup allowance."""
        sleep(0.05)
        return original_run_sync(awaitable, timeout)

    channel.run_sync = delay_run_sync  # type: ignore[method-assign]
    try:
        with pytest.raises(TimeoutError, match="token fetch timed out"):
            channel.get_token_sync(0.02)
        assert not fetch_started.is_set()
    finally:
        channel.run_sync = original_run_sync  # type: ignore[method-assign]
        channel.sync_close(timeout=5)


@pytest.mark.asyncio()
async def test_token_fetch_preserves_receiver_timeout_error() -> None:
    """A receiver's own TimeoutError is not rewritten as dispatch expiry."""
    application_error = TimeoutError("The token receiver timed out.")

    class Receiver(TokenReceiver):
        async def _fetch(self, timeout=None, options=None):
            raise application_error

        def can_retry(self, err, options=None):
            return False

    class Bearer(TokenBearer):
        def receiver(self):
            return Receiver()

    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=Bearer())
    try:
        with pytest.raises(TimeoutError, match="token receiver timed out") as raised:
            await channel.get_token(5)
        assert raised.value is application_error
    finally:
        await channel.close()


@pytest.mark.asyncio()
async def test_authentication_retry_reopens_request_cancellation() -> None:
    """A retried UNAUTHENTICATED call must not stay terminal."""
    from nebius.aio.service_error import RequestError as ServiceRequestError
    from nebius.aio.service_error import RequestStatusExtended

    class RetryAuthenticator(Authenticator):
        async def authenticate(
            self,
            metadata: Metadata,
            timeout: float | None = None,
            options: dict[str, str] | None = None,
        ) -> None:
            return None

        def can_retry(
            self,
            err: Exception,
            options: dict[str, str] | None = None,
        ) -> bool:
            return True

    class RetryProvider(Provider):
        def authenticator(self) -> Authenticator:
            return RetryAuthenticator()

    class LegacyChannel:
        def get_authorization_provider(self) -> Provider:
            return RetryProvider()

    request: Request[GetDiskRequest, Disk] = Request(
        LegacyChannel(),  # type: ignore[arg-type]
        "nebius.compute.v1.DiskService",
        "Get",
        GetDiskRequest(id="auth-retry-cancel"),
        Disk,
    )
    retry_count = 0
    second_attempt = asyncio.Event()

    async def retry_loop(
        *,
        outer_deadline: float | None = None,
        defer_unauthenticated_release: bool = False,
    ) -> Disk:
        nonlocal retry_count
        retry_count += 1
        if retry_count == 1:
            with request._future_lock:
                request._native_terminal = True
            raise ServiceRequestError(
                RequestStatusExtended(
                    code=grpc.StatusCode.UNAUTHENTICATED,
                    message="The credential expired.",
                    details=[],
                    service_errors=[],
                    request_id="",
                    trace_id="",
                ),
            )
        second_attempt.set()
        await asyncio.Event().wait()
        raise AssertionError("The canceled authentication retry returned.")

    request._retry_loop = retry_loop  # type: ignore[method-assign]
    pending = asyncio.create_task(request._request_with_authorization_loop())
    with request._future_lock:
        request._future = pending
    attempt_waiter = asyncio.create_task(second_attempt.wait())
    done, _ = await asyncio.wait(
        (pending, attempt_waiter),
        timeout=5,
        return_when=asyncio.FIRST_COMPLETED,
    )
    if pending in done:
        await pending
    assert attempt_waiter in done

    assert request.cancel()
    with pytest.raises(asyncio.CancelledError):
        await pending
    assert retry_count == 2


@pytest.mark.asyncio()
@pytest.mark.parametrize("use_override", [False, True])
async def test_authentication_retry_transport_ownership(use_override: bool) -> None:
    """An auth retry reacquires a lease but retains an explicit override."""
    from nebius.aio.service_error import RequestError as ServiceRequestError
    from nebius.aio.service_error import RequestStatusExtended

    class RetryAuthenticator(Authenticator):
        async def authenticate(
            self,
            metadata: Metadata,
            timeout: float | None = None,
            options: dict[str, str] | None = None,
        ) -> None:
            return None

        def can_retry(
            self,
            err: Exception,
            options: dict[str, str] | None = None,
        ) -> bool:
            return True

    class RetryProvider(Provider):
        def authenticator(self) -> Authenticator:
            return RetryAuthenticator()

    first = AddressChannel(object(), "first")  # type: ignore[arg-type]
    second = AddressChannel(object(), "second")  # type: ignore[arg-type]

    class LeaseChannel:
        def __init__(self) -> None:
            self.leased: list[AddressChannel] = []
            self.released: list[tuple[AddressChannel | None, bool]] = []

        def get_authorization_provider(self) -> Provider:
            return RetryProvider()

        def get_channel_by_method(self, method: str) -> AddressChannel:
            channel = (first, second)[len(self.leased)]
            self.leased.append(channel)
            return channel

        def release_channel(
            self,
            channel: AddressChannel | None,
            *,
            discard: bool = False,
        ) -> None:
            self.released.append((channel, discard))

    channel = LeaseChannel()
    request: Request[GetDiskRequest, Disk] = Request(
        channel,  # type: ignore[arg-type]
        "nebius.compute.v1.DiskService",
        "Get",
        GetDiskRequest(id="auth-retry-lease"),
        Disk,
        grpc_channel_override=first if use_override else None,
        retries=0,
    )
    attempt = 0

    class AttemptCall:
        def __init__(self, error: BaseException | None) -> None:
            self.error = error

        def __await__(self):
            async def result() -> Disk:
                if self.error is not None:
                    raise self.error
                return Disk()

            return result().__await__()

        async def code(self) -> grpc.StatusCode:
            return grpc.StatusCode.OK

        async def details(self) -> str:
            return ""

        async def initial_metadata(self) -> tuple[()]:
            return ()

        async def trailing_metadata(self) -> tuple[()]:
            return ()

    authentication_error = ServiceRequestError(
        RequestStatusExtended(
            code=grpc.StatusCode.UNAUTHENTICATED,
            message="The credential expired.",
            details=[],
            service_errors=[],
            request_id="",
            trace_id="",
        ),
    )

    def send(timeout: float | None) -> None:
        nonlocal attempt
        if request._grpc_channel is None:
            request._grpc_channel = channel.get_channel_by_method("test")
        attempt += 1
        request._call = AttemptCall(authentication_error if attempt == 1 else None)  # type: ignore[assignment]

    request._send = send  # type: ignore[method-assign]

    result = await request._request_with_authorization_loop()

    assert isinstance(result, Disk)
    if use_override:
        assert channel.leased == []
        assert channel.released == [(first, False)]
    else:
        assert channel.leased == [first, second]
        assert channel.released == [(first, False), (second, False)]
    assert request._grpc_channel is None


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

    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials="token", metrics=Metrics())
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
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials(), event_loop=loop)

    async def attempt() -> None:
        with pytest.raises(LoopError, match="Await close"):
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

    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    graceful = BlockingGraceful()
    channel._gracefuls.add(graceful)
    runtime_threads = [
        channel._runtime._loop_thread,
        *channel._runtime._executor._threads,
    ]

    with pytest.raises(TimeoutError, match="did not shut down"):
        channel.sync_close(timeout=0.05)
    assert graceful.started.wait(timeout=5)
    graceful.release.set()

    deadline = monotonic() + 5
    while any(thread is not None and thread.is_alive() for thread in runtime_threads):
        assert monotonic() < deadline
        sleep(0.01)


def test_close_rejects_submissions_before_queued_cleanup_starts() -> None:
    """The first close call publishes rejection before SDK-loop dispatch."""
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    loop_blocked = Event()
    release_loop = Event()

    async def block_loop() -> None:
        loop_blocked.set()
        release_loop.wait(timeout=5)

    channel.run_async(block_loop())
    assert loop_blocked.wait(timeout=5)
    try:
        with pytest.raises(TimeoutError, match="did not shut down"):
            channel.sync_close(timeout=0.05)
        rejected = asyncio.sleep(0)
        with pytest.raises(ChannelClosedError, match="closed"):
            channel.run_async(rejected)
    finally:
        release_loop.set()
        channel._runtime._shutdown_complete.result(timeout=5)


@pytest.mark.asyncio()
async def test_rejected_request_submission_discards_explicit_override() -> None:
    """A scheduler rejection cannot strand a request-owned transport lease."""
    rejection = ChannelClosedError("The test channel rejected the submission.")
    override = object.__new__(AddressChannel)
    released: list[tuple[object | None, bool]] = []

    class RejectingChannel:
        def get_authorization_provider(self) -> None:
            return None

        def run_async(self, awaitable: object) -> None:
            raise rejection

        def release_channel(
            self,
            address: object | None,
            *,
            discard: bool = False,
        ) -> None:
            released.append((address, discard))

    request: Request[GetDiskRequest, Disk] = Request(
        RejectingChannel(),  # type: ignore[arg-type]
        "nebius.compute.v1.DiskService",
        "Get",
        GetDiskRequest(id="rejected-submission"),
        Disk,
        grpc_channel_override=override,
    )
    with pytest.raises(ChannelClosedError) as raised:
        await request
    assert raised.value is rejection
    assert released == [(override, True)]


def test_raw_inherited_protected_task_is_discarded_when_done() -> None:
    """Borrowed-loop context inheritance cannot retain a completed raw task."""
    runtime = AsyncRuntime(None, 2)

    async def parent() -> asyncio.Task[None]:
        async def child() -> None:
            assert runtime.protect_current_submission() is not None

        raw_child = asyncio.create_task(child())
        await raw_child
        await asyncio.sleep(0)
        return raw_child

    try:
        raw_child = runtime.submit(parent()).result(timeout=5)
        assert raw_child not in runtime._protected_tasks
    finally:
        runtime.shutdown()


def test_failed_first_close_submission_still_finalizes_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed cleanup dispatch is cached and followed by runtime shutdown."""
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    original_submit = channel._runtime.submit

    def reject_close(awaitable, *, track=True):
        if not track:
            close = getattr(awaitable, "close", None)
            if callable(close):
                close()
            raise RuntimeError("The close dispatch failed.")
        return original_submit(awaitable, track=track)

    monkeypatch.setattr(channel._runtime, "submit", reject_close)
    with pytest.raises(RuntimeError, match="close dispatch failed"):
        channel.sync_close(timeout=5)
    assert channel._closed
    assert channel._runtime._shutdown_complete.done()

    with pytest.raises(RuntimeError, match="close dispatch failed"):
        channel.sync_close(timeout=5)


def test_sync_close_timeout_covers_blocked_executor_shutdown() -> None:
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
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
        with pytest.raises(TimeoutError, match="did not shut down"):
            channel.sync_close(timeout=0.05)
    finally:
        release_worker.set()
        channel._runtime._shutdown_complete.result(timeout=5)


def test_supplied_loop_close_cancels_and_drains_submissions() -> None:
    loop, thread = _start_loop()
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials(), event_loop=loop)
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


def test_close_cancels_nested_submission_finalizer_once() -> None:
    """Parent cancellation cannot recancel a child's async finalizer."""
    loop, thread = _start_loop()
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials(), event_loop=loop)
    child_started = Event()
    child_finalized = Event()
    finalizer_steps: list[int] = []

    async def child() -> None:
        child_started.set()
        try:
            await asyncio.Event().wait()
        finally:
            for step in range(3):
                await asyncio.sleep(0)
                finalizer_steps.append(step)
            child_finalized.set()

    async def parent() -> None:
        await channel.run_async(child())

    parent_submission = channel.run_async(parent())
    try:
        assert child_started.wait(timeout=5)
        channel.sync_close(timeout=5)
        assert parent_submission.cancelled()
        assert child_finalized.wait(timeout=5)
        assert finalizer_steps == [0, 1, 2]
        assert loop.is_running()
    finally:
        _stop_loop(loop, thread)


def test_close_does_not_recancel_a_task_already_in_its_finalizer() -> None:
    loop, thread = _start_loop()
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials(), event_loop=loop)
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


def test_internal_close_caller_completes_before_runtime_stops(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    callback_ran = Event()
    original_cancel_returning = channel._runtime._cancel_returning_task

    def observe_cancel_returning(task: asyncio.Task[object]) -> None:
        """Record the next-turn callback before applying its normal check."""
        callback_ran.set()
        original_cancel_returning(task)

    monkeypatch.setattr(
        channel._runtime,
        "_cancel_returning_task",
        observe_cancel_returning,
    )

    async def close_from_internal_loop() -> int:
        await channel.close()
        assert not callback_ran.is_set()
        return 42

    assert channel.run_async(close_from_internal_loop()).result(timeout=5) == 42
    assert callback_ran.wait(timeout=5)


def test_internal_close_stops_continuation_on_its_next_await(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    close_returned = Event()
    callback_ran = Event()
    finalized = Event()
    original_cancel_returning = channel._runtime._cancel_returning_task

    def observe_cancel_returning(task: asyncio.Task[object]) -> None:
        """Prove the callback runs only after close returns to its caller."""
        assert close_returned.is_set()
        callback_ran.set()
        original_cancel_returning(task)

    monkeypatch.setattr(
        channel._runtime,
        "_cancel_returning_task",
        observe_cancel_returning,
    )

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
    assert callback_ran.wait(timeout=5)
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

    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
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


def test_repeated_failed_internal_close_still_starts_shutdown() -> None:
    """A completed close failure cannot retain a protected internal caller."""
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    close_error = RuntimeError("The cached channel cleanup failed.")
    close_future: Future[None] = Future()
    close_future.set_exception(close_error)
    channel._close_completion = close_future
    channel._close_handle = CrossLoopAwaitable(close_future, channel._event_loop)
    channel._closed = True
    caught = Event()

    async def repeat_close() -> None:
        try:
            await channel.close()
        except RuntimeError as error:
            assert error is close_error
            caught.set()
        await asyncio.Event().wait()

    submitted = channel._runtime.submit(repeat_close())
    try:
        with pytest.raises(ConcurrentCancelledError):
            submitted.result(timeout=5)
        assert caught.is_set()
        channel._runtime._shutdown_complete.result(timeout=5)
    finally:
        channel._runtime.shutdown_async().result(timeout=5)


def test_raw_child_close_does_not_receive_second_cancellation() -> None:
    """Shutdown preserves a cancelling inherited child's async finalizer."""
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    child_ready: Future[asyncio.Task[None]] = Future()
    finalizer_started = Event()
    finalized = Event()
    recancelled = Event()

    async def child() -> None:
        try:
            await asyncio.Event().wait()
        finally:
            finalizer_started.set()
            try:
                await channel.close()
                await asyncio.sleep(0.05)
                finalized.set()
            except asyncio.CancelledError:
                recancelled.set()
                raise

    async def parent() -> None:
        child_task = asyncio.create_task(child())
        child_ready.set_result(child_task)
        await asyncio.Event().wait()

    parent_submission = channel.run_async(parent())
    child_task = child_ready.result(timeout=5)
    channel._event_loop.call_soon_threadsafe(child_task.cancel)
    try:
        assert finalizer_started.wait(timeout=5)
        channel._runtime._shutdown_complete.result(timeout=5)
        assert finalized.wait(timeout=5)
        assert not recancelled.is_set()
        assert parent_submission.cancelled()
    finally:
        channel._runtime.shutdown_async().result(timeout=5)


def test_raw_child_cancelled_after_close_protection_is_not_recancelled() -> None:
    """Late cancellation is retained without ``Task.cancelling()`` support."""

    class BlockingGraceful:
        def __init__(self) -> None:
            self.started = Event()
            self.release = Event()

        async def close(self, grace: float | None = None) -> None:
            self.started.set()
            while not self.release.is_set():
                await asyncio.sleep(0)

    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    graceful = BlockingGraceful()
    channel._gracefuls.add(graceful)
    child_ready: Future[asyncio.Task[None]] = Future()
    finalizer_started = Event()
    finalized = Event()
    recancelled = Event()

    async def child() -> None:
        try:
            await channel.close()
        finally:
            finalizer_started.set()
            try:
                await asyncio.sleep(0.05)
                finalized.set()
            except asyncio.CancelledError:
                recancelled.set()
                raise

    async def parent() -> None:
        child_task = asyncio.create_task(child())
        child_ready.set_result(child_task)
        await asyncio.Event().wait()

    parent_submission = channel.run_async(parent())
    child_task = child_ready.result(timeout=5)
    try:
        assert graceful.started.wait(timeout=5)
        channel._event_loop.call_soon_threadsafe(child_task.cancel)
        assert finalizer_started.wait(timeout=5)
        graceful.release.set()
        channel._runtime._shutdown_complete.result(timeout=5)
        assert finalized.wait(timeout=5)
        assert not recancelled.is_set()
        assert parent_submission.cancelled()
    finally:
        graceful.release.set()
        channel._runtime.shutdown_async().result(timeout=5)


def test_run_sync_preserves_runtime_error_from_awaitable() -> None:
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())

    async def fail() -> None:
        raise RuntimeError("The test callable failed.")

    try:
        with pytest.raises(RuntimeError, match="test callable failed"):
            channel.run_sync(fail(), timeout=5)
    finally:
        channel.sync_close(timeout=5)


def test_run_sync_preserves_timeout_error_from_completed_awaitable() -> None:
    """An application's TimeoutError is not mistaken for a wait deadline."""
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    application_error = TimeoutError("The application task timed out.")

    async def fail() -> None:
        raise application_error

    try:
        with pytest.raises(TimeoutError, match="application task timed out") as raised:
            channel.run_sync(fail(), timeout=5)
        assert raised.value is application_error
    finally:
        channel.sync_close(timeout=5)


def test_run_sync_translates_expired_wait_and_cancels_work() -> None:
    """A real synchronous wait deadline cancels and drains submitted work."""
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    started = Event()
    finalized = Event()

    async def block() -> None:
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            finalized.set()

    try:
        with pytest.raises(TimeoutError, match="awaitable timed out"):
            channel.run_sync(block(), timeout=0.05)
        assert started.is_set()
        assert finalized.wait(timeout=5)
    finally:
        channel.sync_close(timeout=5)


def test_run_sync_keeps_deadline_classification_during_completion_race() -> None:
    """Completion after a wait expires cannot impersonate an application error."""
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    future: Future[int] = Future()

    class DeadlineRace(CrossLoopAwaitable[int]):
        def _result(self, timeout: float | None = None) -> int:
            future.set_result(42)
            raise runtime_module.FutureTimeoutError

    handle = DeadlineRace(future, channel._event_loop)
    try:
        with pytest.raises(TimeoutError, match="awaitable timed out"):
            channel.run_sync(handle, timeout=0.01)
        assert handle.result() == 42
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
            ],
        ),
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
        user_agent_prefix="nebius-python-sdk-tests/1.0",
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
            raise AssertionError("The test must not create a request.")

    foreign_loop, foreign_thread = _start_loop()
    sdk_channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())

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

    channel = FakeChannel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
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


def test_low_level_task_start_failure_settles_call_and_accessors() -> None:
    """An accepted call whose task is rejected settles every public gate."""
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    rejection = RuntimeError("The SDK rejected the low-level call task.")
    factory_installed = Event()
    release_installer = Event()

    def reject_once(loop, coroutine, **kwargs):
        """Reject the first task that starts after factory installation."""
        loop.set_task_factory(None)
        raise rejection

    async def install() -> None:
        """Install the factory and hold the SDK loop for target submission."""
        asyncio.get_running_loop().set_task_factory(reject_once)
        factory_installed.set()
        release_installer.wait(timeout=5)

    # Let constructor work finish before the one-shot task factory is active.
    channel.run_async(asyncio.sleep(0)).result(timeout=5)
    installer = channel.run_async(install())
    try:
        assert factory_installed.wait(timeout=5)
        call = channel.unary_unary(
            "/nebius.compute.v1.DiskService/Get",
            lambda request: request.SerializeToString(),
            Disk.FromString,
        )(GetDiskRequest(id="rejected-before-call"))
        release_installer.set()
        installer.result(timeout=5)

        async def await_call() -> Disk:
            """Wait for the rejected low-level call."""
            return await call

        with pytest.raises(RuntimeError) as raised:
            asyncio.run(await_call())
        assert raised.value is rejection
        assert call.done()
        with pytest.raises(RuntimeError) as accessor_error:
            asyncio.run(call.initial_metadata())
        assert accessor_error.value is rejection
    finally:
        release_installer.set()
        channel.sync_close(timeout=5)


def test_request_task_start_failure_releases_explicit_override() -> None:
    """An asynchronously rejected request releases its pre-leased transport."""
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    rejection = RuntimeError("The test rejected the request task.")
    released = Event()
    release_calls: list[tuple[object | None, bool]] = []

    class Transport:
        async def close(self, grace: float | None = None) -> None:
            return None

    override = AddressChannel(  # type: ignore[arg-type]
        Transport(),
        "request-start-rejection.example:443",
        channel._event_loop,
    )

    def release(value: object | None, *, discard: bool = False) -> None:
        release_calls.append((value, discard))
        released.set()

    channel._release_channel_soon = release  # type: ignore[method-assign]

    def reject_once(loop, coroutine, **kwargs):
        loop.set_task_factory(None)
        raise rejection

    async def install() -> None:
        asyncio.get_running_loop().set_task_factory(reject_once)

    channel.run_async(install()).result(timeout=5)
    request: Request[GetDiskRequest, Disk] = Request(
        channel,
        "nebius.compute.v1.DiskService",
        "Get",
        GetDiskRequest(id="rejected-before-request"),
        Disk,
        grpc_channel_override=override,
    )
    try:
        with pytest.raises(RuntimeError) as raised:
            asyncio.run(request._await_result())
        assert raised.value is rejection
        assert released.wait(timeout=5)
        assert release_calls == [(override, True)]
    finally:
        channel.sync_close(timeout=5)


def test_request_start_rejection_closes_unleased_override_from_async_loop() -> None:
    """Async pre-start cleanup closes an unleased explicit transport."""
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    rejection = RuntimeError("The test rejected the request task.")
    closed = Event()

    class Transport:
        async def close(self, grace: float | None = None) -> None:
            """Record transport cleanup on the SDK event loop."""
            closed.set()

    override = AddressChannel(  # type: ignore[arg-type]
        Transport(),
        "request-async-cleanup.example:443",
        channel._event_loop,
    )

    def reject_once(loop, coroutine, **kwargs):
        """Reject one request task after the SDK accepts it."""
        loop.set_task_factory(None)
        raise rejection

    async def install() -> None:
        """Install the one-shot task factory on the SDK loop."""
        asyncio.get_running_loop().set_task_factory(reject_once)

    async def run_request() -> None:
        """Submit the request from a separate active event loop."""
        request: Request[GetDiskRequest, Disk] = Request(
            channel,
            "nebius.compute.v1.DiskService",
            "Get",
            GetDiskRequest(id="async-rejected-request"),
            Disk,
            grpc_channel_override=override,
        )
        with pytest.raises(RuntimeError) as raised:
            await request._await_result()
        assert raised.value is rejection

    channel.run_async(install()).result(timeout=5)
    try:
        asyncio.run(run_request())
        assert closed.wait(timeout=5)
        assert override._is_closed_by_sdk()
    finally:
        channel.sync_close(timeout=5)


def test_stream_task_start_failure_releases_explicit_override() -> None:
    """An asynchronously rejected stream operation releases its lease."""
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    rejection = RuntimeError("The test rejected the stream task.")
    released = Event()

    class Transport:
        async def close(self, grace: float | None = None) -> None:
            """Record cleanup of the rejected stream transport."""
            released.set()

    override = AddressChannel(  # type: ignore[arg-type]
        Transport(),
        "stream-start-rejection.example:443",
        channel._event_loop,
    )

    def reject_once(loop, coroutine, **kwargs):
        loop.set_task_factory(None)
        raise rejection

    async def install() -> None:
        asyncio.get_running_loop().set_task_factory(reject_once)

    channel.run_async(install()).result(timeout=5)
    stream = StreamRequest(
        channel=channel,
        route=Route("acme.Service", "Upload"),
        request=None,
        result_class=Disk,
        client_streaming=True,
        server_streaming=False,
        grpc_channel_override=override,
    )
    try:
        with pytest.raises(RuntimeError) as raised:
            asyncio.run(stream.done_writing())
        assert raised.value is rejection
        assert released.wait(timeout=5)
        assert override._is_closed_by_sdk()
    finally:
        channel.sync_close(timeout=5)


def test_later_stream_task_start_failure_keeps_active_transport() -> None:
    """Rejecting one later operation does not release the active stream."""
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    rejection = RuntimeError("The test rejected the later stream task.")
    release_calls: list[tuple[object | None, bool]] = []

    class Call:
        cancelled = False

        async def write(self, request: object) -> None:
            return None

        def cancel(self) -> bool:
            self.cancelled = True
            return True

    call = Call()

    class Transport:
        def stream_unary(self, path, serializer, deserializer):
            return lambda **kwargs: call

        async def close(self, grace: float | None = None) -> None:
            return None

    override = AddressChannel(  # type: ignore[arg-type]
        Transport(),
        "active-stream-start-rejection.example:443",
        channel._event_loop,
    )

    def release(value: object | None, *, discard: bool = False) -> None:
        release_calls.append((value, discard))

    channel.release_channel = release  # type: ignore[method-assign]
    stream = StreamRequest(
        channel=channel,
        route=Route("acme.Service", "Upload"),
        request=None,
        result_class=Disk,
        client_streaming=True,
        server_streaming=False,
        grpc_channel_override=override,
    )

    def reject_once(loop, coroutine, **kwargs):
        loop.set_task_factory(None)
        raise rejection

    async def install() -> None:
        asyncio.get_running_loop().set_task_factory(reject_once)

    try:
        asyncio.run(stream.write(GetDiskRequest(id="first")))
        assert stream._call is call
        channel.run_async(install()).result(timeout=5)
        with pytest.raises(RuntimeError) as raised:
            asyncio.run(stream.write(GetDiskRequest(id="rejected")))
        assert raised.value is rejection
        assert release_calls == []
        assert stream._call is call
        assert not stream._released
        assert not call.cancelled
        asyncio.run(stream.aclose())
        assert release_calls == [(override, True)]
        assert call.cancelled
    finally:
        channel.sync_close(timeout=5)


def test_low_level_prestart_cancel_publishes_terminal_status() -> None:
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
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
    assert call.debug_error_string() == ""
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
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
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
    debug_accessors_created = 0

    class BlockingCall:
        def __init__(self) -> None:
            self.callback = None

        def add_done_callback(self, callback) -> None:
            self.callback = callback

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

        def debug_error_string(self):
            nonlocal debug_accessors_created
            debug_accessors_created += 1

            async def debug_details() -> str:
                return "late diagnostics"

            return debug_details()

    blocking_call: BlockingCall | None = None

    class BlockingTransport:
        def unary_unary(self, *args: object, **kwargs: object):
            def invoke(*call_args: object, **call_kwargs: object) -> BlockingCall:
                nonlocal blocking_call
                blocking_call = BlockingCall()
                return blocking_call

            return invoke

        def get_state(self) -> grpc.ChannelConnectivity:
            return grpc.ChannelConnectivity.READY

        async def close(self, grace: float | None = None) -> None:
            transport_closed.set()

    class BlockingChannel(Channel):
        def create_address_channel(self, addr: str) -> AddressChannel:
            return AddressChannel(BlockingTransport(), addr)  # type: ignore[arg-type]

    channel = BlockingChannel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
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
        channel.sync_close(timeout=5)
        assert blocking_call is not None
        assert blocking_call.callback is not None
        blocking_call.callback(blocking_call)
        assert debug_accessors_created == 0
        assert call._pending_debug_result is None

        async def terminal_status() -> None:
            assert await call.code() == grpc.StatusCode.CANCELLED
            assert "cancel" in (await call.details()).lower()
            assert await call.initial_metadata() is not None
            assert await call.trailing_metadata() is not None

        asyncio.run(terminal_status())
    finally:
        channel.sync_close(timeout=5)


@pytest.mark.parametrize("close_during_wait", [False, True])
def test_low_level_native_completion_wins_before_wrapper_resumes(
    close_during_wait: bool,
) -> None:
    """Native completion wins over direct cancellation and SDK shutdown."""
    native_waiting = Event()
    release_result = Event()
    native_call: CompletedCall | None = None

    class CompletedCall:
        def __init__(self) -> None:
            self.callback = None

        def add_done_callback(self, callback) -> None:
            self.callback = callback

        def publish_completion(self) -> None:
            assert self.callback is not None
            self.callback(self)

        def __await__(self):
            async def result() -> Disk:
                native_waiting.set()
                await asyncio.to_thread(release_result.wait)
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

    class Transport:
        def unary_unary(self, *args: object, **kwargs: object):
            def create(*call_args: object, **call_kwargs: object) -> CompletedCall:
                nonlocal native_call
                native_call = CompletedCall()
                return native_call

            return create

        def get_state(self) -> grpc.ChannelConnectivity:
            return grpc.ChannelConnectivity.READY

        async def close(self, grace: float | None = None) -> None:
            return None

    class TestChannel(Channel):
        def create_address_channel(self, addr: str) -> AddressChannel:
            return AddressChannel(Transport(), addr)  # type: ignore[arg-type]

    channel = TestChannel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    call = channel.unary_unary(
        "/nebius.compute.v1.DiskService/Get",
        lambda value: value.SerializeToString(),
        Disk.FromString,
    )(GetDiskRequest(id="native-complete-before-resume"))
    callback_called = Event()
    callback_values: list[object] = []
    call.add_done_callback(lambda completed: (callback_values.append(completed), callback_called.set()))
    closer: Thread | None = None
    try:
        assert native_waiting.wait(timeout=5)
        assert native_call is not None
        native_call.publish_completion()
        assert call.done()
        assert callback_called.wait(timeout=5)
        assert callback_values == [call]
        if close_during_wait:
            closer = Thread(target=channel.sync_close, kwargs={"timeout": 5})
            closer.start()
            sleep(0.05)
            assert closer.is_alive()
        else:
            assert not call.cancel()
        release_result.set()
        assert isinstance(call._submitted.result(timeout=5), Disk)
        if closer is not None:
            closer.join(timeout=5)
            assert not closer.is_alive()
    finally:
        release_result.set()
        if closer is not None:
            closer.join(timeout=5)
        channel.sync_close(timeout=5)


def test_low_level_sync_terminal_accessor_failure_preserves_success() -> None:
    """A throwing accessor invocation cannot replace the native RPC result."""

    class CompletedCall:
        def __await__(self):
            async def result() -> Disk:
                return Disk()

            return result().__await__()

        def add_done_callback(self, callback) -> None:
            callback(self)

        async def initial_metadata(self) -> tuple[()]:
            return ()

        async def trailing_metadata(self) -> tuple[()]:
            return ()

        async def code(self) -> grpc.StatusCode:
            return grpc.StatusCode.OK

        def details(self) -> str:
            raise RuntimeError("The native status details are not available.")

    class Transport:
        def unary_unary(self, *args: object, **kwargs: object):
            return lambda *call_args, **call_kwargs: CompletedCall()

        def get_state(self) -> grpc.ChannelConnectivity:
            return grpc.ChannelConnectivity.READY

        async def close(self, grace: float | None = None) -> None:
            return None

    class TestChannel(Channel):
        def create_address_channel(self, addr: str) -> AddressChannel:
            return AddressChannel(Transport(), addr)  # type: ignore[arg-type]

    channel = TestChannel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    call = channel.unary_unary(
        "/nebius.compute.v1.DiskService/Get",
        lambda request: request.SerializeToString(),
        Disk.FromString,
    )(GetDiskRequest(id="sync-accessor-failure"))
    try:
        assert isinstance(call._submitted.result(timeout=5), Disk)

        async def read_cached_status() -> None:
            assert await call.code() == grpc.StatusCode.OK
            assert await call.initial_metadata() == ()
            assert await call.trailing_metadata() == ()

        asyncio.run(read_cached_status())
    finally:
        channel.sync_close(timeout=5)


def test_low_level_done_callback_observes_remote_cancellation() -> None:
    """Native done publication includes synchronous cancellation diagnostics."""
    native_waiting = Event()
    release_result = Event()
    callback_called = Event()
    observations: list[tuple[bool, bool, str]] = []

    class RemoteCancelledCall:
        def __init__(self) -> None:
            self.callback = None

        def add_done_callback(self, callback) -> None:
            self.callback = callback

        def publish_completion(self) -> None:
            assert self.callback is not None
            self.callback(self)

        def cancelled(self) -> bool:
            return True

        def debug_error_string(self) -> str:
            return "The remote service canceled the RPC."

        def __await__(self):
            async def result() -> Disk:
                native_waiting.set()
                await asyncio.to_thread(release_result.wait)
                raise grpc.aio.AioRpcError(
                    grpc.StatusCode.CANCELLED,
                    (),
                    (),
                    "The remote service canceled the RPC.",
                    "The remote service canceled the RPC.",
                )

            return result().__await__()

        async def initial_metadata(self) -> tuple[()]:
            return ()

        async def trailing_metadata(self) -> tuple[()]:
            return ()

        async def code(self) -> grpc.StatusCode:
            return grpc.StatusCode.CANCELLED

        async def details(self) -> str:
            return "The remote service canceled the RPC."

    native_call = RemoteCancelledCall()

    class Transport:
        def unary_unary(self, *args: object, **kwargs: object):
            return lambda *call_args, **call_kwargs: native_call

        def get_state(self) -> grpc.ChannelConnectivity:
            return grpc.ChannelConnectivity.READY

        async def close(self, grace: float | None = None) -> None:
            return None

    class TestChannel(Channel):
        def create_address_channel(self, addr: str) -> AddressChannel:
            return AddressChannel(Transport(), addr)  # type: ignore[arg-type]

    channel = TestChannel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    call = channel.unary_unary(
        "/nebius.compute.v1.DiskService/Get",
        lambda value: value.SerializeToString(),
        Disk.FromString,
    )(GetDiskRequest(id="remote-cancel"))
    call.add_done_callback(
        lambda completed: (
            observations.append(
                (
                    completed.done(),
                    completed.cancelled(),
                    completed.debug_error_string(),
                ),
            ),
            callback_called.set(),
        ),
    )
    try:
        assert native_waiting.wait(timeout=5)
        native_call.publish_completion()
        assert callback_called.wait(timeout=5)
        assert len(observations) == 1
        assert observations[0][:2] == (True, True)
        assert observations[0][2] in ("", "The remote service canceled the RPC.")
        assert call.done()
        assert call.cancelled()
        release_result.set()
        with pytest.raises(grpc.aio.AioRpcError):
            call._submitted.result(timeout=5)
        assert call.debug_error_string() == "The remote service canceled the RPC."
    finally:
        release_result.set()
        channel.sync_close(timeout=5)


def test_low_level_terminal_precedes_blocking_fatal_diagnostics() -> None:
    """Optional native diagnostics cannot delay authoritative completion."""
    native_waiting = Event()
    release_result = Event()
    debug_started = Event()
    release_debug = Event()
    publish_errors: list[BaseException] = []

    class DiagnosticFailure(BaseException):
        pass

    class NativeCall:
        def __init__(self) -> None:
            self.callback = None

        def add_done_callback(self, callback) -> None:
            self.callback = callback

        def publish_completion(self) -> None:
            assert self.callback is not None
            self.callback(self)

        def cancelled(self) -> bool:
            raise DiagnosticFailure("The cancellation diagnostic failed.")

        def debug_error_string(self) -> str:
            debug_started.set()
            release_debug.wait(timeout=5)
            raise DiagnosticFailure("The debug diagnostic failed.")

        def __await__(self):
            async def result() -> Disk:
                native_waiting.set()
                await asyncio.to_thread(release_result.wait)
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

    native_call = NativeCall()

    class Transport:
        def unary_unary(self, *args: object, **kwargs: object):
            return lambda *call_args, **call_kwargs: native_call

        def get_state(self) -> grpc.ChannelConnectivity:
            return grpc.ChannelConnectivity.READY

        async def close(self, grace: float | None = None) -> None:
            return None

    class TestChannel(Channel):
        def create_address_channel(self, addr: str) -> AddressChannel:
            return AddressChannel(Transport(), addr)  # type: ignore[arg-type]

    channel = TestChannel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    call = channel.unary_unary(
        "/nebius.compute.v1.DiskService/Get",
        lambda value: value.SerializeToString(),
        Disk.FromString,
    )(GetDiskRequest(id="blocking-fatal-diagnostics"))

    def publish() -> None:
        try:
            native_call.publish_completion()
        except BaseException as error:
            publish_errors.append(error)

    publisher = Thread(target=publish)
    try:
        assert native_waiting.wait(timeout=5)
        publisher.start()
        assert debug_started.wait(timeout=5)
        assert call.done()
        assert call.cancel() is False
        release_debug.set()
        publisher.join(timeout=5)
        assert not publisher.is_alive()
        assert publish_errors == []
        release_result.set()
        assert isinstance(call._submitted.result(timeout=5), Disk)
    finally:
        release_debug.set()
        release_result.set()
        if publisher.ident is not None:
            publisher.join(timeout=5)
        channel.sync_close(timeout=5)


def test_low_level_terminal_capture_bypasses_rejecting_task_factory(caplog) -> None:
    """Task-factory rejection cannot replace a completed native result."""
    caplog.set_level("DEBUG")
    native_result = Disk()

    class NativeCall:
        """Return a result before the SDK starts terminal capture."""

        def __init__(self) -> None:
            """Create a native call without a completion callback."""
            self.callback = None

        def add_done_callback(self, callback) -> None:
            """Store the native completion callback."""
            self.callback = callback

        def __await__(self):
            """Complete the call and reject the next task creation."""

            async def result() -> Disk:
                """Publish completion and return the native response."""
                assert self.callback is not None
                self.callback(self)

                def reject_once(loop, coroutine, **kwargs):
                    """Reject terminal capture and restore the default factory."""
                    loop.set_task_factory(None)
                    raise RuntimeError("The test rejected terminal capture.")

                asyncio.get_running_loop().set_task_factory(reject_once)
                return native_result

            return result().__await__()

        def cancelled(self) -> bool:
            """Report that the native call was not canceled."""
            return False

        def debug_error_string(self) -> str:
            """Return an empty optional diagnostic."""
            return ""

        async def initial_metadata(self) -> tuple[()]:
            """Return empty initial metadata."""
            return ()

        async def trailing_metadata(self) -> tuple[()]:
            """Return empty trailing metadata."""
            return ()

        async def code(self) -> grpc.StatusCode:
            """Return the successful native status."""
            return grpc.StatusCode.OK

        async def details(self) -> str:
            """Return empty native status details."""
            return ""

    native_call = NativeCall()

    class Transport:
        """Create the controlled native call."""

        def unary_unary(self, *args: object, **kwargs: object):
            """Return a callable that provides the controlled call."""
            return lambda *call_args, **call_kwargs: native_call

        def get_state(self) -> grpc.ChannelConnectivity:
            """Report a reusable transport state."""
            return grpc.ChannelConnectivity.READY

        async def close(self, grace: float | None = None) -> None:
            """Close the test transport."""
            return

    class TestChannel(Channel):
        """Create address wrappers for the controlled transport."""

        def create_address_channel(self, addr: str) -> AddressChannel:
            """Create one wrapper owned by the SDK loop."""
            return AddressChannel(Transport(), addr)  # type: ignore[arg-type]

    channel = TestChannel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    call = channel.unary_unary(
        "/nebius.compute.v1.DiskService/Get",
        lambda value: value.SerializeToString(),
        Disk.FromString,
    )(GetDiskRequest(id="terminal-capture-rejection"))
    try:
        response = call._submitted.result(timeout=5)
        assert response is native_result
        assert call.done()
        assert asyncio.run(call.code()) is grpc.StatusCode.OK
        assert "The event-loop task factory rejected terminal capture." in caplog.text
    finally:
        channel.sync_close(timeout=5)


@pytest.mark.asyncio()
async def test_low_level_call_captures_async_debug_error_string() -> None:
    """An intercepted asynchronous debug accessor is awaited exactly once."""
    debug_reads = 0

    class NativeCall:
        def __init__(self) -> None:
            self.callback = None

        def add_done_callback(self, callback) -> None:
            self.callback = callback

        def __await__(self):
            async def result() -> Disk:
                assert self.callback is not None
                self.callback(self)
                return Disk()

            return result().__await__()

        def cancelled(self) -> bool:
            return False

        async def debug_error_string(self) -> str:
            nonlocal debug_reads
            debug_reads += 1
            await asyncio.sleep(0)
            return "async diagnostics"

        async def initial_metadata(self) -> tuple[()]:
            return ()

        async def trailing_metadata(self) -> tuple[()]:
            return ()

        async def code(self) -> grpc.StatusCode:
            return grpc.StatusCode.OK

        async def details(self) -> str:
            return ""

    native_call = NativeCall()

    class Transport:
        def unary_unary(self, *args: object, **kwargs: object):
            return lambda *call_args, **call_kwargs: native_call

        def get_state(self) -> grpc.ChannelConnectivity:
            return grpc.ChannelConnectivity.READY

        async def close(self, grace: float | None = None) -> None:
            return None

    class TestChannel(Channel):
        def create_address_channel(self, addr: str) -> AddressChannel:
            return AddressChannel(Transport(), addr)  # type: ignore[arg-type]

    channel = TestChannel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    call = channel.unary_unary(
        "/nebius.compute.v1.DiskService/Get",
        lambda value: value.SerializeToString(),
        Disk.FromString,
    )(GetDiskRequest(id="async-debug"))
    try:
        assert isinstance(await call, Disk)
        assert call.debug_error_string() == "async diagnostics"
        assert debug_reads == 1
    finally:
        await channel.close()


def test_low_level_cancel_during_resolution_never_opens_transport() -> None:
    """Accepted cancellation discards a resolved address before call creation."""
    resolver_started = Event()
    release_resolver = Event()
    call_factory_used = Event()
    address_released = Event()
    discarded: list[AddressChannel] = []

    class Transport:
        def unary_unary(self, *args: object, **kwargs: object):
            call_factory_used.set()
            raise AssertionError("A canceled unary call must not open a transport.")

    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    address = AddressChannel(Transport(), "test-address")  # type: ignore[arg-type]

    def resolve(method: str) -> AddressChannel:
        resolver_started.set()
        release_resolver.wait(timeout=5)
        return address

    channel.get_channel_by_method = resolve  # type: ignore[method-assign]

    def release(value: AddressChannel, *, discard: bool = False) -> None:
        discarded.append(value)
        address_released.set()

    channel.release_channel = release  # type: ignore[method-assign]
    call = channel.unary_unary(
        "/nebius.compute.v1.DiskService/Get",
        lambda value: value.SerializeToString(),
        Disk.FromString,
    )(GetDiskRequest(id="cancel-during-resolution"))
    try:
        assert resolver_started.wait(timeout=5)
        assert call.cancel()
        release_resolver.set()
        with pytest.raises(ConcurrentCancelledError):
            call._submitted.result(timeout=5)
        assert address_released.wait(timeout=5)
        assert not call_factory_used.is_set()
        assert discarded == [address]
    finally:
        release_resolver.set()
        channel.sync_close(timeout=5)


def test_low_level_accessors_preserve_setup_failure_after_close() -> None:
    """Late accessors retain the call submission's authoritative failure."""
    setup_error = RuntimeError("The route resolution failed.")
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())

    def fail_resolution(method: str) -> AddressChannel:
        raise setup_error

    channel.get_channel_by_method = fail_resolution  # type: ignore[method-assign]
    call = channel.unary_unary(
        "/nebius.compute.v1.DiskService/Get",
        lambda value: value.SerializeToString(),
        Disk.FromString,
    )(GetDiskRequest(id="failed-before-native-call"))

    async def observe(awaitable: object) -> object:
        return await awaitable  # type: ignore[misc]

    with pytest.raises(RuntimeError) as raised:
        asyncio.run(observe(call))
    assert raised.value is setup_error
    channel.sync_close(timeout=5)

    for accessor in (
        call.initial_metadata,
        call.trailing_metadata,
        call.code,
        call.details,
    ):
        with pytest.raises(RuntimeError) as raised:
            asyncio.run(observe(accessor()))
        assert raised.value is setup_error


def test_low_level_reentrant_cancel_discards_unpublished_call() -> None:
    """Cancellation inside call creation cancels the unpublished native call."""
    wrapper_ready = Event()
    native_cancelled_event = Event()
    address_released = Event()
    native_cancelled = 0
    discarded: list[AddressChannel] = []
    wrapper: object | None = None

    class NativeCall:
        def cancel(self) -> bool:
            nonlocal native_cancelled
            native_cancelled += 1
            native_cancelled_event.set()
            return True

    class Transport:
        def unary_unary(self, *args: object, **kwargs: object):
            def create(*call_args: object, **call_kwargs: object) -> NativeCall:
                assert wrapper_ready.wait(timeout=5)
                assert wrapper is not None
                assert wrapper.cancel()  # type: ignore[attr-defined]
                return NativeCall()

            return create

    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    address = AddressChannel(Transport(), "test-address")  # type: ignore[arg-type]
    channel.get_channel_by_method = lambda method: address  # type: ignore[method-assign]

    def release(value: AddressChannel, *, discard: bool = False) -> None:
        discarded.append(value)
        address_released.set()

    channel.release_channel = release  # type: ignore[method-assign]
    wrapper = channel.unary_unary(
        "/nebius.compute.v1.DiskService/Get",
        lambda value: value.SerializeToString(),
        Disk.FromString,
    )(GetDiskRequest(id="reentrant-cancel"))
    wrapper_ready.set()
    try:
        with pytest.raises(ConcurrentCancelledError):
            wrapper._submitted.result(timeout=5)  # type: ignore[attr-defined]
        assert native_cancelled_event.wait(timeout=5)
        assert address_released.wait(timeout=5)
        assert native_cancelled == 1
        assert discarded == [address]
    finally:
        channel.sync_close(timeout=5)


@pytest.mark.parametrize("native_error", [False, True])
@pytest.mark.parametrize("cancel_accessor", [False, True])
def test_low_level_completed_call_rejects_cancel_during_terminal_capture(
    native_error: bool,
    cancel_accessor: bool,
) -> None:
    """Terminal metadata capture must not reopen native cancellation."""
    terminal_capture_started = Event()
    release_terminal_capture = Event()

    class CompletedCall:
        def __await__(self):
            async def result() -> Disk:
                if native_error:
                    raise RuntimeError("The native RPC failed.")
                return Disk()

            return result().__await__()

        async def _terminal(self) -> object:
            terminal_capture_started.set()
            await asyncio.to_thread(release_terminal_capture.wait)
            return None

        initial_metadata = _terminal
        trailing_metadata = _terminal
        code = _terminal
        details = _terminal

    class CompletedTransport:
        def unary_unary(self, *args: object, **kwargs: object):
            def invoke(*call_args: object, **call_kwargs: object) -> CompletedCall:
                return CompletedCall()

            return invoke

        def get_state(self) -> grpc.ChannelConnectivity:
            return grpc.ChannelConnectivity.READY

        async def close(self, grace: float | None = None) -> None:
            return None

    class CompletedChannel(Channel):
        def create_address_channel(self, addr: str) -> AddressChannel:
            return AddressChannel(CompletedTransport(), addr)  # type: ignore[arg-type]

    channel = CompletedChannel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    call = channel.unary_unary(
        "/nebius.compute.v1.DiskService/Get",
        lambda request: request.SerializeToString(),
        Disk.FromString,
    )(GetDiskRequest(id="complete"))
    close_done = Event()
    close_errors: list[BaseException] = []
    accessor_results: list[object] = []
    accessor_errors: list[BaseException] = []
    accessor_ready = Event()
    accessor_loop: list[asyncio.AbstractEventLoop] = []
    accessor_tasks: list[asyncio.Task[object]] = []

    def close_channel() -> None:
        try:
            channel.sync_close(timeout=5)
        except BaseException as error:
            close_errors.append(error)
        finally:
            close_done.set()

    closer: Thread | None = None
    accessor: Thread | None = None
    try:
        assert terminal_capture_started.wait(timeout=5)
        assert call.done()
        assert not call.cancel()

        async def cancel_one_waiter() -> None:
            waiter = asyncio.ensure_future(call)
            await asyncio.sleep(0)
            waiter.cancel()
            with pytest.raises(asyncio.CancelledError):
                await waiter

        asyncio.run(cancel_one_waiter())
        closer = Thread(target=close_channel)
        closer.start()
        assert not close_done.wait(timeout=0.1)

        def read_terminal_code() -> None:
            async def read() -> object:
                accessor_loop.append(asyncio.get_running_loop())
                task = asyncio.current_task()
                assert task is not None
                accessor_tasks.append(task)
                accessor_ready.set()
                return await call.code()

            try:
                accessor_results.append(asyncio.run(read()))
            except BaseException as error:
                accessor_errors.append(error)

        accessor = Thread(target=read_terminal_code)
        accessor.start()
        assert accessor_ready.wait(timeout=5)
        sleep(0.05)
        assert accessor.is_alive()
        if cancel_accessor:
            accessor_loop[0].call_soon_threadsafe(accessor_tasks[0].cancel)
            accessor.join(timeout=5)
            assert not accessor.is_alive()
        release_terminal_capture.set()

        async def await_result() -> None:
            if native_error:
                with pytest.raises(RuntimeError, match="native RPC failed"):
                    await call
            else:
                assert isinstance(await call, Disk)

        asyncio.run(await_result())
        closer.join(timeout=5)
        accessor.join(timeout=5)
        assert not closer.is_alive()
        assert not accessor.is_alive()
        assert close_errors == []
        if cancel_accessor:
            assert len(accessor_errors) == 1
            assert isinstance(accessor_errors[0], asyncio.CancelledError)
            assert accessor_results == []
        else:
            assert accessor_errors == []
            assert accessor_results == [None]
    finally:
        release_terminal_capture.set()
        if closer is not None:
            closer.join(timeout=5)
        if accessor is not None:
            accessor.join(timeout=5)
        if not close_done.is_set():
            channel.sync_close(timeout=5)


def test_generated_request_ignores_stale_attempt_completion_callback() -> None:
    """A delayed old callback cannot suppress current-attempt cancellation."""
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    request: Request[GetDiskRequest, Disk] = Request(
        channel,
        "nebius.compute.v1.DiskService",
        "Get",
        GetDiskRequest(id="stale-attempt-callback"),
        Disk,
    )
    old_call = object()
    current_call = object()
    current_submission: Future[Disk] = Future()
    request._call = current_call  # type: ignore[assignment]
    request._future = current_submission
    try:
        request._mark_native_attempt_terminal(old_call)
        assert not request._native_attempt_terminal
        assert request.cancel()
        assert current_submission.cancelled()
    finally:
        channel.sync_close(timeout=5)


def test_request_completion_bypasses_rejecting_task_factory(caplog) -> None:
    """Task-factory rejection cannot replace a generated request result."""
    caplog.set_level("DEBUG")
    native_result = Disk()

    class CompletedCall:
        """Return a successful response before completion processing."""

        def __init__(self) -> None:
            """Create a native call without a completion callback."""
            self.callback = None

        def add_done_callback(self, callback) -> None:
            """Store the native completion callback."""
            self.callback = callback

        def __await__(self):
            """Complete the call and reject the next task creation."""

            async def result() -> Disk:
                """Publish completion and return the native response."""
                assert self.callback is not None
                self.callback(self)

                def reject_once(loop, coroutine, **kwargs):
                    """Reject request completion and restore the default factory."""
                    loop.set_task_factory(None)
                    raise RuntimeError("The test rejected request completion.")

                asyncio.get_running_loop().set_task_factory(reject_once)
                return native_result

            return result().__await__()

        async def code(self) -> grpc.StatusCode:
            """Return the successful native status."""
            return grpc.StatusCode.OK

        async def details(self) -> str:
            """Return empty native status details."""
            return ""

        async def initial_metadata(self) -> tuple[()]:
            """Return empty initial metadata."""
            return ()

        async def trailing_metadata(self) -> tuple[()]:
            """Return empty trailing metadata."""
            return ()

    completed_call = CompletedCall()
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    request: Request[GetDiskRequest, Disk] = Request(
        channel,
        "nebius.compute.v1.DiskService",
        "Get",
        GetDiskRequest(id="request-completion-rejection"),
        Disk,
    )

    def send(timeout: float | None) -> None:
        """Install the controlled native call on the request."""
        request._call = completed_call  # type: ignore[assignment]
        completed_call.add_done_callback(request._mark_native_attempt_terminal)

    request._send = send  # type: ignore[method-assign]
    try:
        response = request.wait()
        assert response is native_result
        assert request.done()
        assert "The event-loop task factory rejected request completion." in caplog.text
    finally:
        channel.sync_close(timeout=5)


def test_generated_request_rejects_cancel_after_native_success() -> None:
    """Metadata capture cannot replace a successful request with cancellation."""
    terminal_capture_started = Event()
    release_terminal_capture = Event()
    results: list[Disk] = []
    errors: list[BaseException] = []

    class CompletedCall:
        def __await__(self):
            async def result() -> Disk:
                return Disk()

            return result().__await__()

        async def code(self) -> grpc.StatusCode:
            terminal_capture_started.set()
            await asyncio.to_thread(release_terminal_capture.wait)
            return grpc.StatusCode.OK

        async def details(self) -> str:
            return ""

        async def initial_metadata(self) -> tuple[()]:
            return ()

        async def trailing_metadata(self) -> tuple[()]:
            return ()

    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    request: Request[GetDiskRequest, Disk] = Request(
        channel,
        "nebius.compute.v1.DiskService",
        "Get",
        GetDiskRequest(id="late-cancel"),
        Disk,
    )

    def send(timeout: float | None) -> None:
        request._call = CompletedCall()  # type: ignore[assignment]

    request._send = send  # type: ignore[method-assign]

    def wait_for_result() -> None:
        try:
            results.append(asyncio.run(request._await_result()))
        except BaseException as error:
            errors.append(error)

    waiter = Thread(target=wait_for_result)
    waiter.start()
    close_done = Event()
    close_errors: list[BaseException] = []

    def close_channel() -> None:
        try:
            channel.sync_close(timeout=5)
        except BaseException as error:
            close_errors.append(error)
        finally:
            close_done.set()

    closer: Thread | None = None
    try:
        assert terminal_capture_started.wait(timeout=5)
        assert request.done()
        assert not request.cancel()

        async def cancel_one_waiter() -> None:
            pending = asyncio.create_task(request._await_result())
            await asyncio.sleep(0)
            pending.cancel()
            with pytest.raises(asyncio.CancelledError):
                await pending

        asyncio.run(cancel_one_waiter())
        closer = Thread(target=close_channel)
        closer.start()
        assert not close_done.wait(timeout=0.1)
        release_terminal_capture.set()
        waiter.join(timeout=5)
        closer.join(timeout=5)
        assert not waiter.is_alive()
        assert not closer.is_alive()
        assert close_errors == []
        assert errors == []
        assert len(results) == 1
        assert isinstance(results[0], Disk)
    finally:
        release_terminal_capture.set()
        waiter.join(timeout=5)
        if closer is not None:
            closer.join(timeout=5)
        if not close_done.is_set():
            channel.sync_close(timeout=5)


@pytest.mark.parametrize("close_during_wait", [False, True])
def test_generated_native_success_wins_before_wrapper_resumes(
    close_during_wait: bool,
) -> None:
    """A native success survives direct cancellation and SDK shutdown."""
    native_waiting = Event()
    release_result = Event()
    results: list[Disk] = []
    errors: list[BaseException] = []

    class CompletedCall:
        def __init__(self) -> None:
            self.callback = None

        def add_done_callback(self, callback) -> None:
            self.callback = callback

        def publish_completion(self) -> None:
            assert self.callback is not None
            self.callback(self)

        def __await__(self):
            async def result() -> Disk:
                native_waiting.set()
                await asyncio.to_thread(release_result.wait)
                return Disk()

            return result().__await__()

        async def code(self) -> grpc.StatusCode:
            return grpc.StatusCode.OK

        async def details(self) -> str:
            return ""

        async def initial_metadata(self) -> tuple[()]:
            return ()

        async def trailing_metadata(self) -> tuple[()]:
            return ()

    native_call = CompletedCall()

    class Transport:
        def unary_unary(self, *args: object, **kwargs: object):
            def create(*call_args: object, **call_kwargs: object) -> CompletedCall:
                return native_call

            return create

        def get_state(self) -> grpc.ChannelConnectivity:
            return grpc.ChannelConnectivity.READY

        async def close(self, grace: float | None = None) -> None:
            return None

    class TestChannel(Channel):
        def create_address_channel(self, addr: str) -> AddressChannel:
            return AddressChannel(Transport(), addr)  # type: ignore[arg-type]

    channel = TestChannel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    request: Request[GetDiskRequest, Disk] = Request(
        channel,
        "nebius.compute.v1.DiskService",
        "Get",
        GetDiskRequest(id="native-success-before-resume"),
        Disk,
    )

    def wait_for_result() -> None:
        try:
            results.append(request.wait())
        except BaseException as error:
            errors.append(error)

    waiter = Thread(target=wait_for_result)
    waiter.start()
    closer: Thread | None = None
    try:
        assert native_waiting.wait(timeout=5)
        native_call.publish_completion()
        if close_during_wait:
            closer = Thread(target=channel.sync_close, kwargs={"timeout": 5})
            closer.start()
            sleep(0.05)
            assert closer.is_alive()
        else:
            assert request.cancel()
        release_result.set()
        waiter.join(timeout=5)
        if closer is not None:
            closer.join(timeout=5)
            assert not closer.is_alive()
        assert not waiter.is_alive()
        assert errors == []
        assert len(results) == 1
        assert isinstance(results[0], Disk)
        assert not request.cancelled()
    finally:
        release_result.set()
        waiter.join(timeout=5)
        if closer is not None:
            closer.join(timeout=5)
        channel.sync_close(timeout=5)


def test_generated_request_rejects_cancel_after_native_error() -> None:
    """Error translation cannot replace an authoritative RPC failure."""
    translation_started = Event()
    release_translation = Event()
    errors: list[BaseException] = []

    class FailedCall:
        def __await__(self):
            async def result() -> Disk:
                raise grpc.aio.AioRpcError(
                    grpc.StatusCode.INVALID_ARGUMENT,
                    (),
                    (),
                    "The request is invalid.",
                    "The native call returned debug details.",
                )

            return result().__await__()

    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    request: Request[GetDiskRequest, Disk] = Request(
        channel,
        "nebius.compute.v1.DiskService",
        "Get",
        GetDiskRequest(id="late-error-cancel"),
        Disk,
        retries=1,
    )

    def send(timeout: float | None) -> None:
        request._call = FailedCall()  # type: ignore[assignment]

    original_raise = request._raise_request_error

    def translate(error: grpc.aio.AioRpcError) -> None:
        translation_started.set()
        release_translation.wait(timeout=5)
        original_raise(error)

    request._send = send  # type: ignore[method-assign]
    request._raise_request_error = translate  # type: ignore[method-assign]

    def wait_for_result() -> None:
        try:
            asyncio.run(request._await_result())
        except BaseException as error:
            errors.append(error)

    waiter = Thread(target=wait_for_result)
    waiter.start()
    try:
        assert translation_started.wait(timeout=5)
        assert not request.cancel()
        release_translation.set()
        waiter.join(timeout=5)
        assert not waiter.is_alive()
        assert len(errors) == 1
        assert not isinstance(errors[0], asyncio.CancelledError)
        assert "The request is invalid." in str(errors[0])
    finally:
        release_translation.set()
        waiter.join(timeout=5)
        channel.sync_close(timeout=5)


def test_generated_done_state_includes_remote_cancellation() -> None:
    """Raw terminal code is visible before error translation completes."""
    translation_started = Event()
    release_translation = Event()
    errors: list[BaseException] = []

    class FailedCall:
        def __await__(self):
            async def result() -> Disk:
                raise grpc.aio.AioRpcError(
                    grpc.StatusCode.CANCELLED,
                    (),
                    (),
                    "The remote service canceled the RPC.",
                    "The remote service canceled the RPC.",
                )

            return result().__await__()

    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    request: Request[GetDiskRequest, Disk] = Request(
        channel,
        "nebius.compute.v1.DiskService",
        "Get",
        GetDiskRequest(id="remote-cancel"),
        Disk,
        retries=1,
    )

    def send(timeout: float | None) -> None:
        request._call = FailedCall()  # type: ignore[assignment]

    original_raise = request._raise_request_error

    def translate(error: grpc.aio.AioRpcError) -> None:
        translation_started.set()
        release_translation.wait(timeout=5)
        original_raise(error)

    request._send = send  # type: ignore[method-assign]
    request._raise_request_error = translate  # type: ignore[method-assign]

    def wait_for_result() -> None:
        try:
            asyncio.run(request._await_result())
        except BaseException as error:
            errors.append(error)

    waiter = Thread(target=wait_for_result)
    waiter.start()
    try:
        assert translation_started.wait(timeout=5)
        assert request.done()
        assert request.cancelled()
        assert not request.cancel()
        release_translation.set()
        waiter.join(timeout=5)
        assert not waiter.is_alive()
        assert len(errors) == 1
    finally:
        release_translation.set()
        waiter.join(timeout=5)
        channel.sync_close(timeout=5)


@pytest.mark.parametrize("structured_retry", [False, True])
def test_generated_request_accepts_cancel_while_deciding_to_retry(
    structured_retry: bool,
) -> None:
    """An attempt's terminal state must not hide a pending logical retry."""
    translation_started = Event()
    release_translation = Event()
    errors: list[BaseException] = []
    send_count = 0

    class RetriableCall:
        def __await__(self):
            async def result() -> Disk:
                if structured_retry:
                    from nebius.api.nebius.common.v1 import ServiceError
                    from nebius.base._service_error import trailing_metadata_of_errors

                    details = "The service returned a structured retryable failure."
                    service_error = ServiceError(
                        service="example.service",
                        code="retry requested",
                        retry_type=ServiceError.RetryType.CALL,
                    )
                    trailing_metadata = trailing_metadata_of_errors(
                        service_error,
                        status_code=grpc.StatusCode.FAILED_PRECONDITION.value,
                        status_message=details,
                    )
                    raise grpc.aio.AioRpcError(
                        grpc.StatusCode.FAILED_PRECONDITION,
                        (),
                        trailing_metadata,
                        details,
                        "The native call returned debug details.",
                    )
                raise grpc.aio.AioRpcError(
                    grpc.StatusCode.UNAVAILABLE,
                    (),
                    (),
                    "The service returned a retryable failure.",
                    "The native call returned debug details.",
                )

            return result().__await__()

    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    request: Request[GetDiskRequest, Disk] = Request(
        channel,
        "nebius.compute.v1.DiskService",
        "Get",
        GetDiskRequest(id="retry-decision-cancel"),
        Disk,
        retries=2,
    )

    def send(timeout: float | None) -> None:
        nonlocal send_count
        send_count += 1
        request._call = RetriableCall()  # type: ignore[assignment]

    original_raise = request._raise_request_error

    def translate(error: grpc.aio.AioRpcError) -> None:
        translation_started.set()
        release_translation.wait(timeout=5)
        original_raise(error)

    request._send = send  # type: ignore[method-assign]
    request._raise_request_error = translate  # type: ignore[method-assign]

    def wait_for_result() -> None:
        try:
            request.wait()
        except BaseException as error:
            errors.append(error)

    waiter = Thread(target=wait_for_result)
    waiter.start()
    try:
        assert translation_started.wait(timeout=5)
        assert not request.done()
        assert request.cancel()
        release_translation.set()
        waiter.join(timeout=5)
        assert not waiter.is_alive()
        assert request.done()
        assert request.cancelled()
        assert send_count == 1
        assert len(errors) == 1
        assert isinstance(errors[0], ConcurrentCancelledError)
    finally:
        release_translation.set()
        waiter.join(timeout=5)
        channel.sync_close(timeout=5)


@pytest.mark.asyncio()
async def test_cancel_during_authorization_retry_decision_stops_retry() -> None:
    """Cancellation queued during synchronous auth classification wins."""
    from nebius.aio.request import RequestIsCancelledError
    from nebius.aio.service_error import RequestError as ServiceRequestError
    from nebius.aio.service_error import RequestStatusExtended

    decision_started = Event()
    release_decision = Event()
    cancel_result: list[bool] = []

    class BlockingAuthenticator(Authenticator):
        async def authenticate(
            self,
            metadata: Metadata,
            timeout: float | None = None,
            options: dict[str, str] | None = None,
        ) -> None:
            return None

        def can_retry(
            self,
            err: Exception,
            options: dict[str, str] | None = None,
        ) -> bool:
            decision_started.set()
            release_decision.wait(timeout=5)
            return True

    class BlockingProvider(Provider):
        def authenticator(self) -> Authenticator:
            return BlockingAuthenticator()

    class LegacyChannel:
        def get_authorization_provider(self) -> Provider:
            return BlockingProvider()

    request: Request[GetDiskRequest, Disk] = Request(
        LegacyChannel(),  # type: ignore[arg-type]
        "nebius.compute.v1.DiskService",
        "Get",
        GetDiskRequest(id="cancel-auth-decision"),
        Disk,
    )
    retry_count = 0

    async def retry_loop(
        *,
        outer_deadline: float | None = None,
        defer_unauthenticated_release: bool = False,
    ) -> Disk:
        nonlocal retry_count
        retry_count += 1
        with request._future_lock:
            request._native_terminal = True
            request._native_attempt_terminal = True
            request._retry_decision_pending = True
        raise ServiceRequestError(
            RequestStatusExtended(
                code=grpc.StatusCode.UNAUTHENTICATED,
                message="The credential expired.",
                details=[],
                service_errors=[],
                request_id="",
                trace_id="",
            ),
        )

    request._retry_loop = retry_loop  # type: ignore[method-assign]
    pending = asyncio.create_task(request._request_with_authorization_loop())
    with request._future_lock:
        request._future = pending

    def cancel_during_decision() -> None:
        assert decision_started.wait(timeout=5)
        cancel_result.append(request.cancel())
        release_decision.set()

    canceller = Thread(target=cancel_during_decision)
    canceller.start()
    try:
        with pytest.raises(RequestIsCancelledError):
            await pending
        assert cancel_result == [True]
        assert retry_count == 1
        assert request.cancelled()
    finally:
        release_decision.set()
        canceller.join(timeout=5)


def test_generated_request_discards_wrong_loop_override() -> None:
    """An incompatible override must close on its owner loop, not enter the pool."""
    from nebius.aio.request import RequestError

    foreign_loop, foreign_thread = _start_loop()
    closed = Event()
    close_loops: list[asyncio.AbstractEventLoop] = []

    class RecordingTransport:
        async def close(self, grace: float | None = None) -> None:
            close_loops.append(asyncio.get_running_loop())
            closed.set()

    override = AddressChannel(  # type: ignore[arg-type]
        RecordingTransport(),
        "foreign.example:443",
        event_loop=foreign_loop,
    )
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    request: Request[GetDiskRequest, Disk] = Request(
        channel,
        "nebius.compute.v1.DiskService",
        "Get",
        GetDiskRequest(id="wrong-loop-override"),
        Disk,
        grpc_channel_override=override,
        retries=1,
    )
    try:
        with pytest.raises(RequestError, match="belongs to a different event loop"):
            request.wait()
        assert closed.wait(timeout=5)
        assert close_loops == [foreign_loop]
        with channel._channel_pool_lock:
            assert all(pooled is not override for channels in channel._free_channels.values() for pooled in channels)
    finally:
        channel.sync_close(timeout=5)
        _stop_loop(foreign_loop, foreign_thread)


def test_request_inputs_are_snapshotted_at_first_submission() -> None:
    """External mutation after submission must not race SDK-loop processing."""
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
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


@pytest.mark.parametrize("value", (float("nan"), float("inf"), float("-inf")))
@pytest.mark.parametrize("parameter", ("timeout", "per_retry_timeout", "auth_timeout"))
def test_request_rejects_non_finite_timeouts(value: float, parameter: str) -> None:
    """Request deadlines require a portable finite value or ``None``."""
    with pytest.raises(
        ValueError,
        match=f"The {parameter} value must be finite or None",
    ):
        Request(
            object(),  # type: ignore[arg-type]
            "nebius.compute.v1.DiskService",
            "Get",
            GetDiskRequest(id="invalid-timeout"),
            Disk,
            **{parameter: value},
        )


@pytest.mark.asyncio()
@pytest.mark.parametrize("value", (float("nan"), float("inf"), float("-inf")))
async def test_channel_rejects_non_finite_token_timeout(value: float) -> None:
    """Token dispatch rejects deadlines unsupported by asyncio and gRPC."""
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    try:
        with pytest.raises(
            ValueError,
            match="The timeout value must be finite or None",
        ):
            await channel.get_token(value)
    finally:
        await channel.close()


@pytest.mark.parametrize("value", (float("nan"), float("inf"), float("-inf")))
def test_low_level_call_rejects_non_finite_timeout(value: float) -> None:
    """Low-level cross-loop calls validate timeouts before submission."""
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    unary = channel.unary_unary("/acme.Service/Get")
    try:
        with pytest.raises(
            ValueError,
            match="The timeout value must be finite or None",
        ):
            unary(GetDiskRequest(id="invalid-timeout"), timeout=value)
    finally:
        channel.sync_close(timeout=5)


def test_generated_update_payload_matches_eager_reset_mask() -> None:
    """Mutation after wrapper creation cannot invalidate reset-mask metadata."""
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    source = UpdateDiskRequest()
    source.spec.size_gibibytes = 4
    pending = DiskServiceClient(channel).update(source)
    reset_mask = pending.input_metadata().get_one("x-resetmask")

    source.spec.size_gibibytes = None
    try:
        assert pending._input.spec.size_gibibytes == 4
        assert pending._input.get_full_update_reset_mask().marshal() == reset_mask
        assert source.get_full_update_reset_mask().marshal() != reset_mask
    finally:
        channel.sync_close(timeout=5)


def test_custom_copy_from_payload_retains_pass_through_compatibility() -> None:
    """Unknown serializable payloads are not treated as protobuf messages."""

    class CustomPayload:
        def __init__(self, value: str) -> None:
            self.value = value

        def CopyFrom(self, other: object) -> None:  # noqa: N802
            raise AssertionError("The SDK must not use the custom CopyFrom method.")

        def SerializeToString(self) -> bytes:  # noqa: N802
            return self.value.encode()

    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
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


def test_legacy_constant_request_memoizes_a_reusable_task() -> None:
    """A legacy Constant fallback must not retain a one-shot coroutine."""

    class LegacySource:
        def parent_id(self) -> None:
            return None

    channel = Constant(
        "custom.Service.Call",
        LegacySource(),  # type: ignore[arg-type]
    )
    request: Request[GetDiskRequest, Disk] = Request(
        channel,
        "custom.Service",
        "Call",
        GetDiskRequest(id="legacy"),
        Disk,
    )
    calls = 0
    initial_metadata = Metadata()

    async def capture() -> Disk:
        nonlocal calls
        calls += 1
        request._initial_metadata = initial_metadata
        return Disk()

    request._request_with_authorization_loop = capture  # type: ignore[method-assign]

    async def run() -> None:
        assert isinstance(await request, Disk)
        assert await request.initial_metadata() is initial_metadata
        assert isinstance(await request._await_result(), Disk)

    asyncio.run(run())
    assert calls == 1


@pytest.mark.parametrize("hook_name", ["close", "_cancel_unstarted_threadsafe"])
@pytest.mark.parametrize(
    "cleanup_error",
    [
        ValueError("The test cleanup failed."),
        KeyboardInterrupt("The test cleanup failed with a fatal error."),
    ],
)
def test_failed_unstarted_disposal_preserves_submission_error(
    hook_name: str,
    cleanup_error: BaseException,
) -> None:
    """A custom cleanup failure must not mask runtime rejection."""

    class CustomAwaitable:
        def __await__(self):
            async def result() -> None:
                return None

            return result().__await__()

    def fail_disposal() -> None:
        raise cleanup_error

    runtime = AsyncRuntime(None, 2)
    runtime.shutdown_async().result(timeout=5)
    awaitable = CustomAwaitable()
    setattr(awaitable, hook_name, fail_disposal)

    with pytest.raises(RuntimeError, match="closing or closed"):
        runtime.submit(awaitable)


def test_async_close_does_not_block_external_loop_needed_by_worker() -> None:
    async def run() -> None:
        external_loop = asyncio.get_running_loop()
        channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
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
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
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
    channel = Channel(
        user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials(), executor_max_workers=1
    )
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


@pytest.mark.asyncio()
async def test_operation_service_factories_do_not_block_async_callers() -> None:
    """Synchronous client factories defer source-address resolution."""
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    try:
        transport = channel.get_corresponding_operation_service(DiskServiceClient)
        assert callable(transport.Get)
        client = DiskServiceClient(channel)
        assert client.operation_service() is client.operation_service()
    finally:
        await channel.close()


def test_cross_loop_handles_fail_fast_from_owned_executor_worker() -> None:
    """A worker cannot wait on a handle whose work may need that worker."""
    channel = Channel(
        user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials(), executor_max_workers=1
    )
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
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    holder: Future[object] = Future()

    async def await_self() -> None:
        handle = await asyncio.wrap_future(holder)
        await handle  # type: ignore[misc]

    handle = channel.run_async(await_self())
    holder.set_result(handle)
    try:
        with pytest.raises(RuntimeError, match="own SDK submission"):
            handle.result(timeout=5)
    finally:
        channel.sync_close(timeout=5)


def test_submission_cannot_wrap_its_own_handle_on_another_runtime() -> None:
    """Cross-runtime wrapping cannot turn self-await into an A-B-A cycle."""
    channel_a = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    channel_b = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    holder: Future[object] = Future()

    async def await_wrapped_self() -> None:
        own_handle = await asyncio.wrap_future(holder)
        await channel_b.run_async(own_handle)  # type: ignore[arg-type]

    handle = channel_a.run_async(await_wrapped_self())
    holder.set_result(handle)
    try:
        with pytest.raises(RuntimeError, match="own SDK submission"):
            handle.result(timeout=5)
    finally:
        channel_a.sync_close(timeout=5)
        channel_b.sync_close(timeout=5)


def test_inherited_child_context_can_await_completed_parent_handle() -> None:
    """A child task's inherited marker is not self-await after parent completion."""
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    holder: Future[object] = Future()
    child_started = Event()
    release_child = Event()
    child_done = Event()
    child_results: list[int] = []
    child_errors: list[BaseException] = []

    async def parent() -> int:
        async def child() -> None:
            child_started.set()
            await asyncio.to_thread(release_child.wait)
            try:
                handle = holder.result(timeout=5)
                child_results.append(await handle)  # type: ignore[misc]
            except BaseException as error:
                child_errors.append(error)
            finally:
                child_done.set()

        asyncio.create_task(child())
        return 42

    handle = channel.run_async(parent())
    holder.set_result(handle)
    try:
        assert child_started.wait(timeout=5)
        assert handle.result(timeout=5) == 42
        release_child.set()
        assert child_done.wait(timeout=5)
        assert child_errors == []
        assert child_results == [42]
    finally:
        release_child.set()
        channel.sync_close(timeout=5)


def test_borrowed_loop_sync_close_from_external_async_loop_is_rejected() -> None:
    """Sync close cannot block a loop that borrowed SDK work may need."""
    sdk_loop, sdk_thread = _start_loop()
    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials(), event_loop=sdk_loop)

    async def close_from_external_loop() -> None:
        with pytest.raises(LoopError, match="Await close"):
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
        channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
        try:
            with pytest.raises(LoopError, match="asynchronous context"):
                channel.get_addr_from_service_name("example.Service")
        finally:
            await channel.close()

    asyncio.run(run())


def test_sync_close_from_external_async_context_preserves_loop_error() -> None:
    async def run() -> None:
        channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
        with pytest.raises(LoopError, match="Await close"):
            channel.sync_close(timeout=0.1)
        await channel.close()

    asyncio.run(run())


class _BlockingCloseResource:
    """Keep channel cleanup active until a close-race test releases it."""

    def __init__(self) -> None:
        """Create the cleanup synchronization events."""
        self.started = Event()
        self.release = Event()

    async def close(self, grace: float | None = None) -> None:
        """Report cleanup entry and wait for the test to release it."""
        self.started.set()
        while not self.release.is_set():
            await asyncio.sleep(0)


def _observe_external_close_join(
    channel: Channel,
    monkeypatch: pytest.MonkeyPatch,
) -> Event:
    """Return an event that reports an external caller joining close."""
    joined = Event()
    original_get_close_handle = channel._get_close_handle

    def observe_close_handle(grace: float | None) -> CrossLoopAwaitable[None]:
        """Report an external caller after it gets the shared close handle."""
        closing = original_get_close_handle(grace)
        if not channel._runtime.in_event_loop():
            joined.set()
        return closing

    monkeypatch.setattr(
        channel,
        "_get_close_handle",
        observe_close_handle,
    )
    return joined


def test_external_close_does_not_cancel_concurrent_internal_close_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An external close preserves a protected internal close result."""

    async def run_once() -> None:
        """Run one synchronized close race."""
        channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
        resource = _BlockingCloseResource()
        channel._gracefuls.add(resource)
        external_joined = _observe_external_close_join(channel, monkeypatch)

        async def internal() -> int:
            """Close from the SDK loop and publish a result."""
            await channel.close()
            return 42

        submitted = channel.run_async(internal())
        external_close: asyncio.Task[None] | None = None
        try:
            assert await asyncio.to_thread(resource.started.wait, 5)
            external_close = asyncio.create_task(channel.close())
            assert await asyncio.to_thread(external_joined.wait, 5)
        finally:
            resource.release.set()
            if external_close is None:
                await channel.close()
            else:
                await external_close
        assert submitted.result(timeout=5) == 42

    for _ in range(20):
        asyncio.run(run_once())


def test_sync_close_does_not_cancel_concurrent_internal_close_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A synchronous close preserves a protected internal close result."""
    for _ in range(20):
        channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
        resource = _BlockingCloseResource()
        channel._gracefuls.add(resource)
        external_joined = _observe_external_close_join(channel, monkeypatch)
        close_errors: list[BaseException] = []

        async def internal() -> int:
            """Close from the SDK loop and publish a result."""
            await channel.close()
            return 42

        def close_externally() -> None:
            """Join close synchronously and retain an unexpected error."""
            try:
                channel.sync_close(timeout=5)
            except BaseException as error:
                close_errors.append(error)

        submitted = channel.run_async(internal())
        close_thread: Thread | None = None
        try:
            assert resource.started.wait(timeout=5)
            close_thread = Thread(target=close_externally)
            close_thread.start()
            assert external_joined.wait(timeout=5)
        finally:
            resource.release.set()
            if close_thread is None:
                channel.sync_close(timeout=5)
            else:
                close_thread.join(timeout=5)
        assert close_thread is not None
        assert not close_thread.is_alive()
        assert close_errors == []
        assert submitted.result(timeout=5) == 42
