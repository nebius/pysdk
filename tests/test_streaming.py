from __future__ import annotations

import asyncio
from concurrent.futures import Future
from threading import Barrier, Event, Thread
from time import monotonic, sleep

import grpc
import pytest

from nebius.aio.channel import Channel as SDKChannel
from nebius.aio.channel import NoCredentials
from nebius.aio.constant_channel import Constant
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


@pytest.mark.parametrize("value", (float("nan"), float("inf"), float("-inf")))
@pytest.mark.parametrize("parameter", ("timeout", "auth_timeout"))
def test_stream_rejects_non_finite_timeouts(value: float, parameter: str) -> None:
    """Stream deadlines require a portable finite value or ``None``."""

    with pytest.raises(ValueError, match=f"{parameter} must be finite or None"):
        StreamRequest(
            channel=object(),
            route=Route("acme.Service", "Watch"),
            request=object(),
            result_class=object,
            client_streaming=False,
            server_streaming=True,
            **{parameter: value},
        )


def test_stream_unary_native_completion_wins_before_wrapper_resumes() -> None:
    """SDK shutdown cannot replace a completed stream-unary response."""

    native_waiting = Event()
    release_result = Event()
    released: list[tuple[object, bool]] = []
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

        def cancel(self) -> bool:
            return True

    native_call = CompletedCall()

    class Transport:
        def stream_unary(self, path, serializer, deserializer):
            return lambda **kwargs: native_call

    channel = SDKChannel(credentials=NoCredentials())
    address = type(
        "Address",
        (),
        {"channel": Transport(), "event_loop": channel._event_loop},
    )()
    channel.get_channel_by_route = lambda route: address  # type: ignore[method-assign]
    channel.release_channel = (  # type: ignore[method-assign]
        lambda value, *, discard=False: released.append((value, discard))
    )
    stream = StreamRequest(
        channel=channel,
        route=Route("acme.Service", "Upload"),
        request=None,
        result_class=Disk,
        client_streaming=True,
        server_streaming=False,
    )

    def wait_for_result() -> None:
        try:
            results.append(asyncio.run(stream._result()))
        except BaseException as error:
            errors.append(error)

    waiter = Thread(target=wait_for_result)
    waiter.start()
    closer: Thread | None = None
    try:
        assert native_waiting.wait(timeout=5)
        native_call.publish_completion()
        assert not stream.cancel()
        closer = Thread(target=channel.sync_close, kwargs={"timeout": 5})
        closer.start()
        assert closer.is_alive()
        release_result.set()
        waiter.join(timeout=5)
        closer.join(timeout=5)
        assert not waiter.is_alive()
        assert not closer.is_alive()
        assert errors == []
        assert len(results) == 1
        assert isinstance(results[0], Disk)
        assert released == [(address, False)]
    finally:
        release_result.set()
        waiter.join(timeout=5)
        if closer is not None:
            closer.join(timeout=5)
        channel.sync_close(timeout=5)


def test_terminal_server_stream_cancel_still_releases_lease() -> None:
    """Native terminal state rejects cancellation but not lease cleanup."""

    released = Event()
    release_calls: list[tuple[object | None, bool]] = []
    native_cancel_calls = 0

    class NativeCall:
        def cancel(self) -> bool:
            nonlocal native_cancel_calls
            native_cancel_calls += 1
            return False

    channel = SDKChannel(credentials=NoCredentials())
    address = object()

    def release(value: object | None, *, discard: bool = False) -> None:
        release_calls.append((value, discard))
        released.set()

    channel.release_channel = release  # type: ignore[method-assign]
    stream = StreamRequest(
        channel=channel,
        route=Route("acme.Service", "Watch"),
        request=GetDiskRequest(id="terminal"),
        result_class=Disk,
        client_streaming=False,
        server_streaming=True,
        grpc_channel_override=address,  # type: ignore[arg-type]
    )
    stream._call = NativeCall()
    with stream._state_lock:
        stream._native_terminal = True
    try:
        assert not stream.cancel()
        assert released.wait(timeout=5)
        assert release_calls == [(address, True)]
        assert native_cancel_calls == 1
        assert stream._released
    finally:
        channel.sync_close(timeout=5)


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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("timeout", "auth_timeout", "authorization_enabled"),
    ((0.05, 5, False), (5, 0.05, True)),
    ids=("request-timeout", "authorization-timeout"),
)
async def test_stream_timeout_includes_sdk_loop_queueing(
    timeout: float,
    auth_timeout: float,
    authorization_enabled: bool,
) -> None:
    """A queued stream operation expires before opening a native RPC."""

    loop_blocked = Event()
    release_loop = Event()
    released = Event()
    call_factory_used = Event()
    from nebius.aio.token.static import Bearer as StaticBearer

    credentials = StaticBearer("token") if authorization_enabled else NoCredentials()
    channel = SDKChannel(credentials=credentials)

    async def block_sdk_loop() -> None:
        loop_blocked.set()
        release_loop.wait(timeout=5)

    class Transport:
        def stream_unary(self, *args, **kwargs):
            call_factory_used.set()
            raise AssertionError("expired stream must not open a native RPC")

    address = type(
        "Address",
        (),
        {"channel": Transport(), "event_loop": channel._event_loop},
    )()
    channel.release_channel = (  # type: ignore[method-assign]
        lambda value, *, discard=False: released.set()
    )
    blocker = channel.run_async(block_sdk_loop())
    assert await asyncio.to_thread(loop_blocked.wait, 5)
    stream = StreamRequest(
        channel=channel,
        route=Route("acme.Service", "Upload"),
        request=None,
        result_class=Disk,
        client_streaming=True,
        server_streaming=False,
        timeout=timeout,
        auth_timeout=auth_timeout,
        grpc_channel_override=address,  # type: ignore[arg-type]
    )
    try:
        with pytest.raises(TimeoutError, match="Stream timed out"):
            await stream.done_writing()
        release_loop.set()
        await blocker
        assert await asyncio.to_thread(released.wait, 5)
        assert not call_factory_used.is_set()
    finally:
        release_loop.set()
        await channel.close()


@pytest.mark.asyncio
async def test_stream_timeout_includes_synchronous_submission_delay() -> None:
    """Admission elapsed time is subtracted from the absolute deadline."""

    submissions = 0
    work_started = False

    class Channel:
        def get_authorization_provider(self) -> None:
            return None

        def run_async(self, awaitable):
            nonlocal submissions
            submissions += 1
            if submissions == 1:
                sleep(0.05)
            return awaitable

        def release_channel(
            self,
            released: object,
            *,
            discard: bool = False,
        ) -> None:
            pass

    async def work() -> None:
        nonlocal work_started
        work_started = True

    stream = StreamRequest(
        channel=Channel(),
        route=Route("acme.Service", "Upload"),
        request=None,
        result_class=Disk,
        client_streaming=True,
        server_streaming=False,
        timeout=0.01,
    )
    with pytest.raises(TimeoutError, match="before SDK-loop dispatch"):
        await stream._on_sdk_loop(work())
    assert not work_started


def test_legacy_constant_stream_cancel_runs_on_owner_loop() -> None:
    """Constant's one-shot fallback must not discard stream cancellation."""

    ready: Future[asyncio.AbstractEventLoop] = Future()
    cancelled = Event()
    discarded = Event()

    def run_loop() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        ready.set_result(loop)
        loop.run_forever()
        loop.close()

    class LegacySource:
        def parent_id(self) -> None:
            return None

        def discard_channel(self, channel: object) -> None:
            discarded.set()

    class NativeCall:
        def cancel(self) -> bool:
            cancelled.set()
            return True

    thread = Thread(target=run_loop, daemon=True)
    thread.start()
    owner_loop = ready.result(timeout=5)
    channel = Constant(
        "acme.Service.Watch",
        LegacySource(),  # type: ignore[arg-type]
    )
    stream = StreamRequest(
        channel=channel,
        route=Route("acme.Service", "Watch"),
        request=object(),
        result_class=object,
        client_streaming=False,
        server_streaming=True,
    )
    stream._owner_loop = owner_loop
    stream._call = NativeCall()
    stream._address_channel = object()
    try:
        assert stream.cancel()
        assert cancelled.wait(timeout=5)
        assert discarded.wait(timeout=5)
    finally:
        owner_loop.call_soon_threadsafe(owner_loop.stop)
        thread.join(timeout=5)
        assert not thread.is_alive()


@pytest.mark.asyncio
async def test_legacy_stream_discovers_and_enforces_auth_timeout() -> None:
    """Provider discovery restores the legacy in-loop auth budget."""

    auth_started = asyncio.Event()
    auth_cancelled = asyncio.Event()
    released: list[object] = []

    class Authenticator:
        async def authenticate(self, metadata, timeout, options) -> None:
            auth_started.set()
            try:
                await asyncio.Event().wait()
            finally:
                auth_cancelled.set()

    class Provider:
        def authenticator(self) -> Authenticator:
            return Authenticator()

    class LegacyChannel:
        def get_authorization_provider(self) -> Provider:
            return Provider()

        def return_channel(self, address: object) -> None:
            released.append(address)

    address = object()
    stream = StreamRequest(
        channel=LegacyChannel(),
        route=Route("acme.Service", "Watch"),
        request=GetDiskRequest(id="legacy-auth-timeout"),
        result_class=Disk,
        client_streaming=False,
        server_streaming=True,
        timeout=None,
        auth_timeout=0.01,
        grpc_channel_override=address,
    )

    with pytest.raises(TimeoutError, match="stream authorization timed out"):
        await anext(stream.__aiter__())
    assert auth_started.is_set()
    assert auth_cancelled.is_set()
    assert released == [address]


def test_rejected_stream_cancel_restores_retryable_state() -> None:
    """A rejected SDK dispatch must not retain an accepted-cancel marker."""

    class ClosedChannel:
        def run_async(self, awaitable: object) -> None:
            raise RuntimeError("closed")

        def get_state(self):
            return grpc.ChannelConnectivity.SHUTDOWN

    stream = StreamRequest(
        channel=ClosedChannel(),
        route=Route("acme.Service", "Watch"),
        request=object(),
        result_class=object,
        client_streaming=False,
        server_streaming=True,
    )

    assert not stream.cancel()
    assert not stream._cancel_requested


def test_rejected_stream_cancel_preserves_submission_error() -> None:
    """A secondary legacy state failure must not mask dispatch rejection."""

    rejection = RuntimeError("cancellation submission rejected")

    class BrokenChannel:
        def run_async(self, awaitable: object) -> None:
            raise rejection

        def get_state(self):
            raise ValueError("state unavailable")

    stream = StreamRequest(
        channel=BrokenChannel(),
        route=Route("acme.Service", "Watch"),
        request=object(),
        result_class=object,
        client_streaming=False,
        server_streaming=True,
    )

    with pytest.raises(RuntimeError, match="submission rejected") as raised:
        stream.cancel()
    assert raised.value is rejection
    assert not stream._cancel_requested


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


def test_stream_request_timeout_excludes_slow_authentication() -> None:
    """Stream auth uses its own budget before request timeout resumes."""

    class Authenticator:
        async def authenticate(self, metadata, timeout, options) -> None:
            await asyncio.sleep(0.08)

        def can_retry(self, err, options=None) -> bool:
            return False

    class Provider:
        def authenticator(self) -> Authenticator:
            return Authenticator()

    channel = SDKChannel(credentials=NoCredentials())
    channel._authorization_provider = Provider()  # type: ignore[assignment]
    stream = StreamRequest(
        channel=channel,
        route=Route("acme.Service", "Watch"),
        request=GetDiskRequest(id="independent-stream-auth-clock"),
        result_class=Disk,
        client_streaming=False,
        server_streaming=True,
        timeout=0.05,
        auth_timeout=0.5,
    )

    async def authenticate() -> float:
        await stream._on_sdk_loop(stream._authenticate())
        deadline = stream._request_deadline
        assert deadline is not None
        return deadline - monotonic()

    try:
        remaining = asyncio.run(authenticate())
        assert 0 < remaining <= 0.05
    finally:
        channel.sync_close(timeout=5)


def test_legacy_constant_stream_preserves_independent_auth_clock() -> None:
    """A pass-through Constant does not time authentication as request work."""

    class Authenticator:
        async def authenticate(self, metadata, timeout, options) -> None:
            await asyncio.sleep(0.08)

        def can_retry(self, err, options=None) -> bool:
            return False

    class Provider:
        def authenticator(self) -> Authenticator:
            return Authenticator()

    class LegacySource:
        def parent_id(self) -> None:
            return None

        def get_authorization_provider(self) -> Provider:
            return Provider()

    channel = Constant(
        "acme.Service.Watch",
        LegacySource(),  # type: ignore[arg-type]
    )
    stream = StreamRequest(
        channel=channel,
        route=Route("acme.Service", "Watch"),
        request=GetDiskRequest(id="legacy-independent-stream-auth-clock"),
        result_class=Disk,
        client_streaming=False,
        server_streaming=True,
        timeout=0.02,
        auth_timeout=0.5,
    )

    async def authenticate() -> float:
        await stream._on_sdk_loop(stream._authenticate())
        deadline = stream._request_deadline
        assert deadline is not None
        return deadline - monotonic()

    remaining = asyncio.run(authenticate())
    assert 0 < remaining <= 0.02


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


@pytest.mark.parametrize("operation", ["result", "write", "done_writing", "aclose"])
def test_prestart_stream_operation_cancellation_discards_override(
    operation: str,
) -> None:
    """Queued stream cancellation still establishes cleanup and finality."""

    loop_blocked = Event()
    release_loop = Event()
    released = Event()
    opened = Event()
    release_calls: list[tuple[object | None, bool]] = []

    class Transport:
        def stream_unary(self, *args: object) -> object:
            opened.set()
            raise AssertionError("cancelled queued stream must not start")

    channel = SDKChannel(credentials=NoCredentials())
    override = type(
        "Address",
        (),
        {"channel": Transport(), "event_loop": channel._event_loop},
    )()

    def release(address: object | None, *, discard: bool = False) -> None:
        release_calls.append((address, discard))
        released.set()

    channel.release_channel = release  # type: ignore[method-assign]

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
        grpc_channel_override=override,  # type: ignore[arg-type]
    )

    async def cancel_operation() -> None:
        if operation == "result":
            awaitable = stream._result()
        elif operation == "write":
            awaitable = stream.write(GetDiskRequest(id="queued"))
        elif operation == "done_writing":
            awaitable = stream.done_writing()
        else:
            awaitable = stream.aclose()
        pending = asyncio.create_task(awaitable)
        await asyncio.sleep(0)
        pending.cancel()
        with pytest.raises(asyncio.CancelledError):
            await pending

    try:
        asyncio.run(cancel_operation())
        release_loop.set()
        blocker.result(timeout=5)
        assert released.wait(timeout=5)
        assert not opened.is_set()
        assert release_calls == [(override, True)]
        assert stream._cancel_requested
        assert stream._cancelled
    finally:
        release_loop.set()
        channel.sync_close(timeout=5)


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


def test_stream_cancel_rolls_back_synchronous_cancelled_submission() -> None:
    """A submitter cancellation must close its coroutine and remain retryable."""

    submitted = []

    class CancellingChannel:
        def run_async(self, awaitable):
            submitted.append(awaitable)
            raise asyncio.CancelledError()

    class Result:
        @classmethod
        def FromString(cls, data):  # noqa: N802
            return cls()

    stream = StreamRequest(
        channel=CancellingChannel(),
        route=Route("acme.Service", "Watch"),
        request=object(),
        result_class=Result,
        client_streaming=False,
        server_streaming=True,
    )

    with pytest.raises(asyncio.CancelledError):
        stream.cancel()
    assert not stream._cancel_requested
    assert submitted[0].cr_frame is None

    with pytest.raises(asyncio.CancelledError):
        stream.cancel()
    assert not stream._cancel_requested
    assert submitted[1].cr_frame is None


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
    released: list[tuple[object | None, bool]] = []

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

        def discard_channel(self, address):
            released.append((address, True))

    class Result:
        @classmethod
        def FromString(cls, data):  # noqa: N802
            return cls()

    override = object()
    stream = StreamRequest(
        channel=Channel(),
        route=Route("acme.Service", "Watch"),
        request=object(),
        result_class=Result,
        client_streaming=False,
        server_streaming=True,
        grpc_channel_override=override,  # type: ignore[arg-type]
    )
    iteration = stream.__aiter__()
    pending = asyncio.create_task(anext(iteration))
    await entered.wait()

    assert stream.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(pending, 0.1)
    assert opened == []
    assert released == [(override, True)]


@pytest.mark.asyncio
async def test_rejected_stream_submission_discards_explicit_override() -> None:
    """A scheduler rejection cannot strand a stream-owned transport lease."""

    rejection = RuntimeError("submission rejected")
    override = object()
    released: list[tuple[object | None, bool]] = []

    class RejectingChannel:
        def get_authorization_provider(self):
            return None

        def run_async(self, awaitable):
            raise rejection

        def release_channel(self, address, *, discard=False):
            released.append((address, discard))

    stream = StreamRequest(
        channel=RejectingChannel(),
        route=Route("acme.Service", "Upload"),
        request=None,
        result_class=Disk,
        client_streaming=True,
        server_streaming=False,
        grpc_channel_override=override,  # type: ignore[arg-type]
    )
    with pytest.raises(RuntimeError) as raised:
        await stream.done_writing()
    assert raised.value is rejection
    assert released == [(override, True)]


def test_rejected_stream_cancel_discards_explicit_override() -> None:
    """Rejected cancellation still releases a stream-owned transport lease."""

    override = object()
    released: list[tuple[object | None, bool]] = []

    class ClosedChannel:
        def get_authorization_provider(self):
            return None

        def run_async(self, awaitable):
            raise RuntimeError("closed")

        def get_state(self):
            return grpc.ChannelConnectivity.SHUTDOWN

        def release_channel(self, address, *, discard=False):
            released.append((address, discard))

    stream = StreamRequest(
        channel=ClosedChannel(),
        route=Route("acme.Service", "Upload"),
        request=None,
        result_class=Disk,
        client_streaming=True,
        server_streaming=False,
        grpc_channel_override=override,  # type: ignore[arg-type]
    )
    assert not stream.cancel()
    assert released == [(override, True)]


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


@pytest.mark.asyncio
async def test_iterator_cleanup_surfaces_release_failure_and_remains_retryable() -> (
    None
):
    """Implicit iterator cleanup must not hide an unexpected release error."""

    release_calls = 0

    class Call:
        def __aiter__(self):
            async def responses():
                yield object()
                await asyncio.Event().wait()

            return responses()

        def cancel(self) -> bool:
            return True

    class Result:
        @classmethod
        def FromString(cls, data):  # noqa: N802
            return cls()

    class Transport:
        def unary_stream(self, *args, **kwargs):
            return lambda *call_args, **call_kwargs: Call()

    class Address:
        channel = Transport()

    class Channel:
        def get_channel_by_route(self, route):
            return Address()

        def run_async(self, awaitable):
            return awaitable

        def release_channel(self, address, *, discard=False) -> None:
            nonlocal release_calls
            release_calls += 1
            if release_calls == 1:
                raise RuntimeError("release failed")

    stream = StreamRequest(
        channel=Channel(),
        route=Route("acme.Service", "Watch"),
        request=object(),
        result_class=Result,
        client_streaming=False,
        server_streaming=True,
    )
    responses = stream.__aiter__()
    await anext(responses)

    with pytest.raises(RuntimeError, match="release failed"):
        await responses.aclose()
    assert not stream._released

    await stream.aclose()
    assert stream._released
    assert release_calls == 2


@pytest.mark.asyncio
async def test_server_stream_iterator_rejected_cleanup_discards_lease() -> None:
    """Iterator finalization uses rejection-safe cleanup admission."""

    submissions = 0
    releases: list[tuple[object, bool]] = []

    class Call:
        def __aiter__(self):
            async def responses():
                yield Disk()
                await asyncio.Event().wait()

            return responses()

        def cancel(self) -> bool:
            return True

    class Transport:
        def unary_stream(self, *args: object, **kwargs: object):
            return lambda *call_args, **call_kwargs: Call()

    class Address:
        channel = Transport()

    address = Address()

    class Channel:
        def get_authorization_provider(self) -> None:
            return None

        def get_channel_by_route(self, route: object) -> Address:
            return address

        def run_async(self, awaitable):
            nonlocal submissions
            submissions += 1
            if submissions > 1:
                raise RuntimeError("cleanup submission rejected")
            return awaitable

        def release_channel(
            self,
            released: object,
            *,
            discard: bool = False,
        ) -> None:
            releases.append((released, discard))

    stream = StreamRequest(
        channel=Channel(),
        route=Route("acme.Service", "Watch"),
        request=GetDiskRequest(id="rejected-iterator-cleanup"),
        result_class=Disk,
        client_streaming=False,
        server_streaming=True,
    )
    responses = stream.__aiter__()
    assert isinstance(await anext(responses), Disk)
    with pytest.raises(RuntimeError, match="cleanup submission rejected"):
        await responses.aclose()
    assert releases == [(address, True)]
    assert stream._released


def test_failed_async_stream_cancel_release_can_be_retried() -> None:
    """A scheduled cancellation observes cleanup failure and permits retry."""

    first_release = Event()
    successful_release = Event()
    release_calls = 0

    channel = SDKChannel(credentials=NoCredentials())
    address = type(
        "Address",
        (),
        {"channel": object(), "event_loop": channel._event_loop},
    )()

    def release(value: object, *, discard: bool = False) -> None:
        nonlocal release_calls
        release_calls += 1
        if release_calls == 1:
            first_release.set()
            raise RuntimeError("release failed")
        successful_release.set()

    channel.release_channel = release  # type: ignore[method-assign]
    stream = StreamRequest(
        channel=channel,
        route=Route("acme.Service", "Upload"),
        request=None,
        result_class=Disk,
        client_streaming=True,
        server_streaming=False,
        grpc_channel_override=address,  # type: ignore[arg-type]
    )
    try:
        assert stream.cancel()
        assert first_release.wait(timeout=5)
        for _ in range(100):
            with stream._state_lock:
                retryable = not stream._cancel_requested and not stream._cancelled
            if retryable:
                break
            Event().wait(0.01)
        assert retryable
        assert stream.cancel()
        assert successful_release.wait(timeout=5)
        assert release_calls == 2
    finally:
        channel.sync_close(timeout=5)
