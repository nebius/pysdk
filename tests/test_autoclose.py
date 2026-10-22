"""Garbage-collection fallback for an SDK dropped without ``close()``.

The SDK's own token renewal runs as a task on the SDK event loop. A strong
reference from that task back to the SDK would keep a dropped SDK reachable
forever: the loop thread keeps the loop alive, the loop keeps the task alive.
These tests prove that renewal alone does not pin the SDK, and that collection
stops renewal and the owned runtime threads.
"""

from __future__ import annotations

import asyncio
import gc
from collections.abc import AsyncIterator, Callable
from concurrent.futures import Future
from pathlib import Path
from threading import Event, Thread
from time import monotonic, sleep
from typing import Any
from weakref import ref

import grpc
import grpc.aio
import nebius.aio.channel as channel_module
import pytest
import pytest_asyncio
from cryptography.hazmat.primitives.asymmetric import rsa
from nebius.aio.abc import ClientChannelInterface
from nebius.aio.channel import ChannelClosedError, _WeakChannel
from nebius.aio.token import renewable
from nebius.aio.token.exchangeable import Bearer as ExchangeableBearer
from nebius.aio.token.file_cache import async_renewable_bearer as file_cache
from nebius.aio.token.options import OPTION_RENEW_SYNCHRONOUS, OPTION_REPORT_ERROR
from nebius.aio.token.static import Bearer as StaticBearer
from nebius.aio.token.static import Receiver as StaticReceiver
from nebius.aio.token.token import NamedBearer, Token
from nebius.api.nebius.iam.v1 import (
    CreateTokenResponse,
    ExchangeTokenRequest,
    TokenExchangeServiceClient,
)
from nebius.base.options import INSECURE
from nebius.base.service_account.service_account import ServiceAccount, TokenRequester
from nebius.sdk import SDK

from .grpc_service import add_service


class _ExchangeService:
    """Count token exchanges and answer with a long-lived token."""

    def __init__(self) -> None:
        self.calls = 0
        self.started = asyncio.Event()
        self.block: asyncio.Event | None = None

    async def Exchange(  # noqa: N802 — gRPC method name
        self,
        request: ExchangeTokenRequest,
        context: grpc.aio.ServicerContext[ExchangeTokenRequest, CreateTokenResponse],
    ) -> CreateTokenResponse:
        self.calls += 1
        self.started.set()
        if self.block is not None:
            await self.block.wait()
        return CreateTokenResponse(
            access_token="token",
            expires_in=3600,
            issued_token_type="Bearer",
            token_type="Bearer",
        )


@pytest_asyncio.fixture()
async def exchange_server() -> AsyncIterator[tuple[str, _ExchangeService]]:
    """Serve a mock token exchange on a free local port."""
    service = _ExchangeService()
    server = grpc.aio.server()
    port = server.add_insecure_port("[::]:0")
    add_service(server, TokenExchangeServiceClient, service)
    await server.start()
    try:
        yield f"localhost:{port}", service
    finally:
        await server.stop(0)


def _service_account() -> ServiceAccount:
    return ServiceAccount(
        private_key=rsa.generate_private_key(public_exponent=65537, key_size=2048),
        public_key_id="public-key-test",
        service_account_id="service-account-test",
    )


def _wait_until(condition: Callable[[], bool], timeout: float = 5.0) -> None:
    """Poll ``condition`` with garbage collection until it holds."""
    deadline = monotonic() + timeout
    while not condition():
        assert monotonic() < deadline, "The condition did not hold before the deadline."
        gc.collect()
        sleep(0.01)


@pytest.mark.asyncio()
async def test_dropped_sdk_with_started_renewal_is_collected_and_shut_down(
    exchange_server: tuple[str, _ExchangeService],
) -> None:
    """Renewal must not pin a dropped SDK, and collection stops its threads."""
    address, service = exchange_server
    sdk = SDK(
        user_agent_prefix="nebius-python-sdk-tests/1.0",
        domain=address,
        options=[(INSECURE, True)],
        credentials=_service_account(),
    )
    token = await sdk.get_token(timeout=5)
    assert token.token == "token"
    assert service.calls == 1

    runtime = sdk._runtime
    loop_thread = runtime._loop_thread
    assert loop_thread is not None
    assert loop_thread.is_alive()
    sdk_ref = ref(sdk)
    del sdk
    del token

    _wait_until(lambda: sdk_ref() is None)
    _wait_until(lambda: not loop_thread.is_alive())
    assert runtime._shutdown_complete.result(timeout=5) is None
    assert service.calls == 1


@pytest.mark.asyncio()
async def test_dropped_sdk_on_supplied_loop_stops_renewal_and_keeps_loop(
    exchange_server: tuple[str, _ExchangeService],
) -> None:
    """The fallback cancels renewal on a supplied loop without stopping it."""
    address, _ = exchange_server
    ready: asyncio.Future[asyncio.AbstractEventLoop] = asyncio.get_running_loop().create_future()
    main_loop = asyncio.get_running_loop()

    def run() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        main_loop.call_soon_threadsafe(ready.set_result, loop)
        loop.run_forever()
        loop.close()

    thread = Thread(target=run, daemon=True)
    thread.start()
    loop = await ready
    try:
        baseline = asyncio.run_coroutine_threadsafe(_count_tasks(), loop).result(timeout=5)
        sdk = SDK(
            user_agent_prefix="nebius-python-sdk-tests/1.0",
            domain=address,
            options=[(INSECURE, True)],
            credentials=_service_account(),
            event_loop=loop,
        )
        await sdk.get_token(timeout=5)
        assert asyncio.run_coroutine_threadsafe(_count_tasks(), loop).result(timeout=5) > baseline
        sdk_ref = ref(sdk)
        del sdk

        _wait_until(lambda: sdk_ref() is None)
        _wait_until(
            lambda: asyncio.run_coroutine_threadsafe(_count_tasks(), loop).result(timeout=5) == baseline,
        )
        assert loop.is_running()
        assert thread.is_alive()
    finally:
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=5)


async def _count_tasks() -> int:
    """Count tasks on the running loop, excluding this one."""
    return len(asyncio.all_tasks()) - 1


@pytest.mark.parametrize("renewal_mode", ["background", "report-error", "synchronous"])
def test_dropped_sdk_with_failed_renewal_is_collected(
    monkeypatch: pytest.MonkeyPatch,
    renewal_mode: str,
) -> None:
    """A failed fetch must not pin a dropped SDK through its exception.

    The renewal task copies the context of the request that started it. The
    exception that the caller received carries a traceback with the SDK's
    own frames. The renewal task must not reach that exception through its
    context, otherwise the loop thread keeps the SDK alive.
    """
    # Captured log records would retain the exception traceback.
    monkeypatch.setattr(renewable.log, "disabled", True)

    message = "Token exchange failed."

    async def exchange(self: Any, *args: Any, **kwargs: Any) -> Any:
        raise RuntimeError(message)

    monkeypatch.setattr(TokenExchangeServiceClient, "exchange", exchange)
    sdk = SDK(
        user_agent_prefix="nebius-python-sdk-tests/1.0",
        domain="localhost:1",
        credentials=_service_account(),
    )
    runtime = sdk._runtime
    sdk_ref = ref(sdk)
    options = {
        "background": None,
        "report-error": {OPTION_REPORT_ERROR: "1"},
        "synchronous": {OPTION_RENEW_SYNCHRONOUS: "1"},
    }[renewal_mode]
    try:
        # Python 3.10 has distinct asyncio and builtin TimeoutError classes.
        # The sync wrapper can surface either for a background timeout.
        expected = (asyncio.TimeoutError, TimeoutError) if options is None else RuntimeError
        with pytest.raises(expected):
            sdk.get_token_sync(timeout=0.2, options=options)
        del sdk
        _wait_until(lambda: sdk_ref() is None)
        assert runtime._shutdown_complete.result(timeout=5) is None
    finally:
        remaining = sdk_ref()
        if remaining is not None:
            remaining.sync_close(timeout=5)


def test_weak_channel_reports_collected_sdk() -> None:
    """A bearer call through the weak handle fails clearly after collection."""
    sdk = SDK(
        user_agent_prefix="nebius-python-sdk-tests/1.0",
        domain="localhost:1",
        credentials="static-token",
    )
    handle = _WeakChannel(sdk)
    assert isinstance(handle, ClientChannelInterface)
    assert handle.get_authorization_provider() is sdk.get_authorization_provider()
    assert handle.parent_id() == sdk.parent_id()
    assert handle.run_sync(asyncio.sleep(0, result="forwarded")) == "forwarded"
    assert handle.user_agent == sdk.user_agent
    sdk.sync_close(timeout=5)
    del sdk
    gc.collect()
    with pytest.raises(ChannelClosedError, match="garbage collected"):
        _ = handle.user_agent
    work = asyncio.sleep(0)
    with pytest.raises(ChannelClosedError, match="garbage collected"):
        handle.run_sync(work)
    assert work.cr_frame is None


def _run_loop_in_thread() -> tuple[asyncio.AbstractEventLoop, Thread]:
    """Start a caller-owned loop on a daemon thread."""
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


def _make_bearer(
    use_file_cache: bool, source: StaticBearer
) -> renewable.Bearer | file_cache.AsynchronousRenewableFileCacheBearer:
    if use_file_cache:
        return file_cache.AsynchronousRenewableFileCacheBearer(NamedBearer(source, "autoclose-test"))
    return renewable.Bearer(source)


@pytest.mark.parametrize("use_file_cache", [False, True])
def test_finalizer_cancels_blocked_renewal_fetch_on_supplied_loop(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    use_file_cache: bool,
) -> None:
    """Fallback cleanup cancels a blocked source fetch and keeps the loop."""
    monkeypatch.setattr(file_cache, "DEFAULT_CONFIG_DIR", str(tmp_path))
    started = Event()
    cancelled = Event()

    async def fetch(self: Any, *args: Any, **kwargs: Any) -> Any:
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    monkeypatch.setattr(StaticReceiver, "_fetch", fetch)
    loop, thread = _run_loop_in_thread()

    async def prepare() -> tuple[ref[SDK], Any]:
        credentials = _make_bearer(use_file_cache, StaticBearer("unused"))
        sdk = SDK(
            user_agent_prefix="nebius-python-sdk-tests/1.0",
            domain="localhost:1",
            credentials=credentials,
            event_loop=loop,
        )
        with pytest.raises(asyncio.TimeoutError):
            await credentials.receiver().fetch(timeout=0.05)
        return ref(sdk), sdk._runtime

    sdk_ref: Callable[[], SDK | None] | None = None
    try:
        sdk_ref, runtime = asyncio.run_coroutine_threadsafe(prepare(), loop).result(timeout=5)
        assert started.is_set()
        _wait_until(lambda: sdk_ref() is None)
        assert runtime._shutdown_complete.result(timeout=5) is None
        assert cancelled.wait(timeout=5)
        assert loop.is_running()
    finally:
        remaining = sdk_ref() if sdk_ref is not None else None
        if remaining is not None:
            asyncio.run_coroutine_threadsafe(remaining.close(), loop).result(timeout=5)
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=5)


class _Requester(TokenRequester):
    def get_exchange_token_request(self) -> ExchangeTokenRequest:
        return ExchangeTokenRequest()


@pytest.mark.parametrize("renewal_mode", ["report-error", "synchronous"])
def test_dropped_sdk_with_failed_file_cache_renewal_is_collected(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    renewal_mode: str,
) -> None:
    """A config reader's file-cache bearer must not pin the SDK on failure."""
    monkeypatch.setattr(file_cache, "DEFAULT_CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(file_cache.log, "disabled", True)
    message = "Token exchange failed."

    async def exchange(self: Any, *args: Any, **kwargs: Any) -> Any:
        raise RuntimeError(message)

    monkeypatch.setattr(TokenExchangeServiceClient, "exchange", exchange)

    class Config:
        """Minimal config reader that wires its bearer to the SDK channel."""

        parent_id = None
        tenant_id = None

        def get_credentials(self, channel: Any, **kwargs: Any) -> Any:
            source = ExchangeableBearer(_Requester(), channel)
            return file_cache.AsynchronousRenewableFileCacheBearer(NamedBearer(source, "autoclose-test"))

    sdk = SDK(
        user_agent_prefix="nebius-python-sdk-tests/1.0",
        domain="localhost:1",
        config_reader=Config(),  # type: ignore[arg-type]
    )
    runtime = sdk._runtime
    sdk_ref = ref(sdk)
    options = {
        "report-error": {OPTION_REPORT_ERROR: "1"},
        "synchronous": {OPTION_RENEW_SYNCHRONOUS: "1"},
    }[renewal_mode]
    try:
        with pytest.raises(RuntimeError):
            sdk.get_token_sync(timeout=1, options=options)
        del sdk
        _wait_until(lambda: sdk_ref() is None)
        assert runtime._shutdown_complete.result(timeout=5) is None
    finally:
        remaining = sdk_ref()
        if remaining is not None:
            remaining.sync_close(timeout=5)


@pytest.mark.asyncio()
@pytest.mark.parametrize("use_file_cache", [False, True])
async def test_repeated_fetch_cancellation_releases_synchronous_waiters(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, use_file_cache: bool
) -> None:
    """Release synchronous waiters after repeated cancellation during child cleanup."""
    started = asyncio.Event()
    cancelling = asyncio.Event()
    release = asyncio.Event()
    monkeypatch.setattr(file_cache, "DEFAULT_CONFIG_DIR", str(tmp_path))

    async def fetch(self: StaticReceiver, *args: Any, **kwargs: Any) -> Token:
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelling.set()
            await release.wait()
        return Token("unused-token")

    monkeypatch.setattr(StaticReceiver, "_fetch", fetch)
    source = StaticBearer("fake-token")
    if use_file_cache:
        credentials = file_cache.AsynchronousRenewableFileCacheBearer(NamedBearer(source, "cancel-test"))
    else:
        credentials = renewable.Bearer(source)
    pending = asyncio.create_task(credentials._fetch_once())
    try:
        await asyncio.wait_for(started.wait(), 2)
        pending.cancel()
        await asyncio.wait_for(cancelling.wait(), 2)
        assert not credentials._synchronous_can_proceed.is_set()
        pending.cancel()
        await asyncio.gather(pending, return_exceptions=True)
        assert credentials._synchronous_can_proceed.is_set()
    finally:
        release.set()
        pending.cancel()
        await asyncio.gather(pending, return_exceptions=True)
        await credentials.close()


def test_finalization_finishes_when_caller_loop_stops_before_cleanup() -> None:
    ready: Future[asyncio.AbstractEventLoop] = Future()
    blocked = Event()
    release = Event()

    def run() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.call_soon(ready.set_result, loop)
        loop.run_forever()

    thread = Thread(target=run, daemon=True)
    thread.start()
    loop = ready.result(timeout=5)
    sdk = SDK(credentials="fake-token", event_loop=loop, user_agent_prefix="autoclose-tests/1.0")
    runtime = sdk._runtime
    sdk_ref = ref(sdk)

    def stop_before_dispatch() -> None:
        blocked.set()
        assert release.wait(timeout=5)
        loop.stop()

    loop.call_soon_threadsafe(stop_before_dispatch)
    try:
        assert blocked.wait(timeout=5)
        del sdk
        gc.collect()
        assert sdk_ref() is None
        release.set()
        thread.join(timeout=5)
        assert not thread.is_alive()
        runtime._shutdown_complete.result(timeout=5)
        assert not loop.is_closed()
    finally:
        release.set()
        if loop.is_running():
            loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=5)
        loop.close()


def test_finalizer_bounds_hanging_graceful_close(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stop owned runtime threads after a graceful close exceeds its budget."""
    cancelled = Event()
    monkeypatch.setattr(channel_module, "_FINALIZER_GRACE", 0.05)

    class HangingBearer(StaticBearer):
        async def close(self, grace: float | None = None) -> None:
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

    sdk = SDK(credentials=HangingBearer("token"), user_agent_prefix="autoclose-tests/1.0")
    runtime = sdk._runtime
    sdk.run_sync(asyncio.to_thread(lambda: None))
    executor = runtime._executor
    assert executor is not None
    workers = tuple(executor._threads)
    transport = sdk.get_channel_by_addr("localhost:1")
    sdk.return_channel(transport)
    sdk_ref = ref(sdk)
    del sdk
    _wait_until(lambda: sdk_ref() is None)
    runtime._shutdown_complete.result(timeout=5)
    assert cancelled.is_set()
    assert runtime.event_loop.is_closed()
    assert all(not worker.is_alive() for worker in workers)
    assert transport.channel.get_state() == grpc.ChannelConnectivity.SHUTDOWN


@pytest.mark.parametrize("supplied_loop", [False, True])
@pytest.mark.parametrize("use_file_cache", [False, True])
def test_finalizer_bypasses_rejecting_task_factory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    supplied_loop: bool,
    use_file_cache: bool,
) -> None:
    """Protected cleanup stops renewal despite a rejecting user task factory."""
    monkeypatch.setattr(file_cache, "DEFAULT_CONFIG_DIR", str(tmp_path))
    started, cancelled, installed, rejected = Event(), Event(), Event(), Event()

    async def fetch(self: Any, *args: Any, **kwargs: Any) -> Any:
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    monkeypatch.setattr(StaticReceiver, "_fetch", fetch)
    loop, thread = _run_loop_in_thread() if supplied_loop else (None, None)
    credentials = _make_bearer(use_file_cache, StaticBearer("unused"))
    sdk = SDK(credentials=credentials, event_loop=loop, user_agent_prefix="autoclose-tests/1.0")
    runtime = sdk._runtime
    sdk_ref = ref(sdk)

    def reject(loop: asyncio.AbstractEventLoop, coro: Any, **kwargs: Any) -> asyncio.Task[Any]:
        rejected.set()
        raise RuntimeError("The task factory rejected work.")

    def install() -> None:
        runtime.event_loop.set_task_factory(reject)
        installed.set()

    try:
        with pytest.raises((asyncio.TimeoutError, TimeoutError)):
            sdk.get_token_sync(timeout=0.05)
        assert started.wait(timeout=5)
        runtime.event_loop.call_soon_threadsafe(install)
        assert installed.wait(timeout=5)
        with pytest.raises(RuntimeError, match="task factory rejected"):
            runtime.submit(asyncio.sleep(0)).result(timeout=5)
        assert rejected.is_set()
        rejected.clear()
        del sdk
        _wait_until(lambda: sdk_ref() is None)
        runtime._shutdown_complete.result(timeout=5)
        assert cancelled.wait(timeout=1)
        assert not rejected.is_set()
        if loop is not None:
            assert loop.is_running()
            assert loop.get_task_factory() is reject
        else:
            assert runtime.event_loop.is_closed()
    finally:
        remaining = sdk_ref()
        if remaining is not None:
            remaining.sync_close(timeout=5)
        if loop is not None:
            loop.call_soon_threadsafe(loop.set_task_factory, None)
            asyncio.run_coroutine_threadsafe(credentials.close(), loop).result(timeout=5)
            loop.call_soon_threadsafe(loop.stop)
            assert thread is not None
            thread.join(timeout=5)


def test_owned_finalizer_closes_async_generator_with_rejecting_factory() -> None:
    """Owned graceful shutdown closes live generators before terminal drain."""
    sdk = SDK(credentials="token", user_agent_prefix="autoclose-tests/1.0")
    runtime = sdk._runtime
    closed, installed = Event(), Event()

    async def values() -> AsyncIterator[str]:
        try:
            yield "value"
        finally:
            closed.set()

    generator = values()

    async def first() -> str:
        return await generator.__anext__()

    assert sdk.run_sync(first(), timeout=5) == "value"

    def reject(loop: asyncio.AbstractEventLoop, coro: Any, **kwargs: Any) -> asyncio.Task[Any]:
        raise RuntimeError("The task factory rejected generator cleanup.")

    def install() -> None:
        runtime.event_loop.set_task_factory(reject)
        installed.set()

    runtime.event_loop.call_soon_threadsafe(install)
    assert installed.wait(timeout=5)
    sdk_ref = ref(sdk)
    try:
        del sdk
        _wait_until(lambda: sdk_ref() is None)
        assert runtime._shutdown_complete.result(timeout=5) is None
        assert closed.is_set()
        assert runtime.event_loop.is_closed()
    finally:
        remaining = sdk_ref()
        if remaining is not None:
            remaining.sync_close(timeout=5)
        if not closed.is_set():
            asyncio.run(generator.aclose())


@pytest.mark.asyncio()
@pytest.mark.parametrize("supplied_loop", [False, True])
@pytest.mark.parametrize("reject_task_creation", [False, True])
async def test_collection_closes_inflight_renewal_transport(
    exchange_server: tuple[str, _ExchangeService],
    monkeypatch: pytest.MonkeyPatch,
    supplied_loop: bool,
    reject_task_creation: bool,
) -> None:
    """Return and close a renewal transport after its SDK is collected."""
    address, service = exchange_server
    service.block = asyncio.Event()
    transports = []
    get_channel = channel_module.Channel.get_channel_by_route

    def capture(self: Any, route: Any) -> Any:
        transport = get_channel(self, route)
        transports.append(transport)
        return transport

    monkeypatch.setattr(channel_module.Channel, "get_channel_by_route", capture)
    loop, thread = await asyncio.to_thread(_run_loop_in_thread) if supplied_loop else (None, None)
    sdk = SDK(
        credentials=_service_account(),
        domain=address,
        options=[(INSECURE, True)],
        user_agent_prefix="autoclose-tests/1.0",
        event_loop=loop,
    )
    runtime = sdk._runtime
    sdk_ref = ref(sdk)
    installed = Event()

    def reject(loop: asyncio.AbstractEventLoop, coro: Any, **kwargs: Any) -> asyncio.Task[Any]:
        raise RuntimeError("The task factory rejected in-flight cleanup.")

    def install() -> None:
        runtime.event_loop.set_task_factory(reject)
        installed.set()

    try:
        with pytest.raises((asyncio.TimeoutError, TimeoutError)):
            await sdk.get_token(timeout=0.1)
        await asyncio.wait_for(service.started.wait(), 5)
        assert transports
        if reject_task_creation:
            runtime.event_loop.call_soon_threadsafe(install)
            assert await asyncio.to_thread(installed.wait, 5)
        del sdk
        deadline = monotonic() + 5
        while sdk_ref() is not None:
            assert monotonic() < deadline, "The SDK remained reachable after renewal stopped waiting."
            gc.collect()
            await asyncio.sleep(0.01)
        runtime._shutdown_complete.result(timeout=5)
        _wait_until(lambda: all(t.channel.get_state() == grpc.ChannelConnectivity.SHUTDOWN for t in transports))
        if loop is not None:
            assert loop.is_running()
            if reject_task_creation:
                assert loop.get_task_factory() is reject
    finally:
        remaining = sdk_ref()
        if remaining is not None:
            await remaining.close()
        if loop is not None:
            loop.call_soon_threadsafe(loop.stop)
            assert thread is not None
            thread.join(timeout=5)


@pytest.mark.parametrize("nonblocking", [False, True])
@pytest.mark.parametrize("reject_task_creation", [False, True])
def test_weak_channel_releases_orphan_transport(nonblocking: bool, reject_task_creation: bool) -> None:
    """Release paths close a lease after collection on a supplied loop."""
    loop, thread = _run_loop_in_thread()
    sdk = SDK(
        credentials="token",
        domain="localhost:1",
        event_loop=loop,
        user_agent_prefix="autoclose-tests/1.0",
    )
    runtime = sdk._runtime
    handle = _WeakChannel(sdk)
    transport = sdk.get_channel_by_addr("localhost:1")
    sdk_ref = ref(sdk)
    installed = Event()

    def reject(loop: asyncio.AbstractEventLoop, coro: Any, **kwargs: Any) -> asyncio.Task[Any]:
        raise RuntimeError("The task factory rejected orphan cleanup.")

    def install() -> None:
        loop.set_task_factory(reject)
        installed.set()

    try:
        del sdk
        _wait_until(lambda: sdk_ref() is None)
        runtime._shutdown_complete.result(timeout=5)
        if reject_task_creation:
            loop.call_soon_threadsafe(install)
            assert installed.wait(timeout=5)
        release = handle._release_channel_soon if nonblocking else handle.release_channel
        release(transport, discard=True)
        _wait_until(lambda: transport._is_closed_by_sdk())
        assert transport.channel.get_state() == grpc.ChannelConnectivity.SHUTDOWN
        assert loop.is_running()
        if reject_task_creation:
            assert loop.get_task_factory() is reject
    finally:
        remaining = sdk_ref()
        if remaining is not None:
            remaining.sync_close(timeout=5)
        loop.call_soon_threadsafe(loop.set_task_factory, None)
        asyncio.run_coroutine_threadsafe(transport.channel.close(), loop).result(timeout=5)
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=5)


@pytest.mark.parametrize("cancel_child", [False, True])
def test_expired_parent_submission_preserves_child_close(cancel_child: bool) -> None:
    """An inherited child can close after its parent handle is collected."""
    sdk = SDK(credentials="token", domain="localhost:1", user_agent_prefix="autoclose-tests/1.0")
    runtime = sdk._runtime
    child_ready: Future[asyncio.Task[None]] = Future()
    release = asyncio.Event()
    continued = Event()

    async def child() -> None:
        try:
            await release.wait()
            if not cancel_child:
                await sdk.close()
                continued.set()
        finally:
            if cancel_child:
                await sdk.close()
                await asyncio.sleep(0.05)
                continued.set()

    async def parent() -> None:
        child_ready.set_result(asyncio.create_task(child()))

    submitted = sdk.run_async(parent())
    submitted.result(timeout=5)
    child_task = child_ready.result(timeout=5)
    submitted_ref = ref(submitted)
    del submitted
    try:
        _wait_until(lambda: submitted_ref() is None)
        runtime.event_loop.call_soon_threadsafe(child_task.cancel if cancel_child else release.set)
        runtime._shutdown_complete.result(timeout=5)
        assert continued.is_set()
        assert child_task.done()
        assert child_task.cancelled() == cancel_child
    finally:
        runtime.shutdown_async().result(timeout=5)


@pytest.mark.parametrize("retain_parent", [False, True])
def test_foreign_loop_child_waits_for_complete_shutdown(retain_parent: bool) -> None:
    """Inherited SDK context does not make an application-loop caller internal."""
    sdk = SDK(credentials="token", domain="localhost:1", user_agent_prefix="autoclose-tests/1.0")
    runtime = sdk._runtime
    application_loop, thread = _run_loop_in_thread()
    worker_started, release_worker, close_started, close_returned = Event(), Event(), Event(), Event()
    release_child = asyncio.Event()
    child_ready: Future[asyncio.Task[None]] = Future()

    def worker() -> None:
        worker_started.set()
        assert release_worker.wait(timeout=5)

    async def child() -> None:
        await release_child.wait()
        close_started.set()
        await sdk.close()
        close_returned.set()

    def start_child() -> None:
        child_ready.set_result(asyncio.create_task(child()))

    async def parent() -> None:
        application_loop.call_soon_threadsafe(start_child)

    runtime.submit(asyncio.to_thread(worker))
    try:
        assert worker_started.wait(timeout=5)
        submitted = runtime.submit(parent())
        submitted.result(timeout=5)
        child_task = child_ready.result(timeout=5)
        submitted_ref = ref(submitted)
        if not retain_parent:
            del submitted
            _wait_until(lambda: submitted_ref() is None)
        application_loop.call_soon_threadsafe(release_child.set)
        assert close_started.wait(timeout=5)
        _wait_until(lambda: runtime._shutdown_preparing)
        assert not close_returned.wait(timeout=0.2)
        release_worker.set()
        assert close_returned.wait(timeout=5)
        runtime._shutdown_complete.result(timeout=5)
        assert runtime.event_loop.is_closed()
        assert child_task.done()
        assert not child_task.cancelled()
        child_task.result()
    finally:
        release_worker.set()
        runtime.shutdown_async().result(timeout=5)
        application_loop.call_soon_threadsafe(application_loop.stop)
        thread.join(timeout=5)


@pytest.mark.asyncio()
async def test_file_cache_observes_unclaimed_renewal_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Discarding a renewal failure does not log an unclaimed future error."""
    monkeypatch.setattr(file_cache, "DEFAULT_CONFIG_DIR", str(tmp_path))
    credentials = _make_bearer(True, StaticBearer("unused"))
    loop = asyncio.get_running_loop()
    errors: list[dict[str, Any]] = []
    previous_handler = loop.get_exception_handler()
    loop.set_exception_handler(lambda _, context: errors.append(context))
    try:
        future: asyncio.Future[Token] = loop.create_future()
        credentials._renewal_future = future
        future.set_exception(RuntimeError("The source failed after its waiters left."))
        credentials._discard_renewal_future(future)
        del future
        gc.collect()
        await asyncio.sleep(0)
        assert not errors
    finally:
        loop.set_exception_handler(previous_handler)
        await credentials.close()
