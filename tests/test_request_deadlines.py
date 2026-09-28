"""Order native completion and caller deadlines without timing-dependent sleeps."""

import asyncio
from threading import Event, Thread
from time import monotonic

import grpc
import pytest
from nebius.aio.channel import Channel, NoCredentials
from nebius.aio.request import Request
from nebius.aio.service_error import RequestError
from nebius.api.nebius.compute.v1 import Disk, GetDiskRequest


@pytest.mark.parametrize("mode", ["async", "sync", "sync-accessor"])
@pytest.mark.parametrize(
    ("phase", "outcome"),
    [
        ("native", "success"),
        ("native", "final_error"),
        ("native", "retry_error"),
        ("metadata", "success"),
        ("metadata", "wrapper_timeout"),
        ("translation", "final_error"),
        ("translation", "retry_error"),
        ("authorization", "auth_retry"),
    ],
)
def test_request_deadline_preserves_completed_attempt(mode, phase, outcome):
    """Expiry preserves final outcomes and prevents retries after native completion."""
    reached = Event()
    release = Event()
    expired = Event()
    finished = Event()
    results = []
    errors = []
    sends = []
    response = Disk()
    wrapper_error = TimeoutError("The result wrapper timed out.")

    async def pause():
        reached.set()
        assert await asyncio.to_thread(release.wait, 5)

    class NativeCall:
        def __await__(self):
            async def result():
                if phase == "native":
                    request._mark_native_attempt_terminal(self)
                    await pause()
                if outcome in ("final_error", "retry_error", "auth_retry"):
                    code = grpc.StatusCode.INVALID_ARGUMENT if outcome == "final_error" else grpc.StatusCode.UNAVAILABLE
                    if outcome == "auth_retry":
                        code = grpc.StatusCode.UNAUTHENTICATED
                    raise grpc.aio.AioRpcError(code, (), (), "Native failure", None)
                return response

            return result().__await__()

        async def code(self):
            return grpc.StatusCode.OK

        async def details(self):
            return ""

        async def initial_metadata(self):
            return ()

        async def trailing_metadata(self):
            return ()

    class ObservedRequest(Request):
        def _expire_wait(self):
            decision = super()._expire_wait()
            expired.set()
            return decision

    def wrap(service, channel, value):
        if phase == "metadata":
            reached.set()
            assert release.wait(5)
        if outcome == "wrapper_timeout":
            raise wrapper_error
        return value

    channel = Channel(user_agent_prefix="nebius-python-sdk-tests/1.0", credentials=NoCredentials())
    if outcome == "auth_retry":

        class Authenticator:
            async def authenticate(self, *args):
                pass

            def can_retry(self, *args):
                reached.set()
                assert release.wait(5)
                return True

        class Provider:
            def authenticator(self):
                return Authenticator()

        channel._get_runtime_authorization_provider = lambda *args: Provider()
        channel._has_authorization_provider = lambda: True

    request = ObservedRequest(
        channel,
        "nebius.compute.v1.DiskService",
        "Get",
        GetDiskRequest(id="deadline-order"),
        Disk,
        timeout=None,
        auth_timeout=None,
        retries=3,
        result_wrapper=wrap,
    )

    def send(timeout):
        sends.append(timeout)
        request._call = NativeCall()

    request._send = send
    original_translate = request._raise_request_error

    def translate(error):
        if phase == "translation":
            reached.set()
            assert release.wait(5)
        original_translate(error)

    request._raise_request_error = translate

    async def await_request():
        return await request

    def run():
        try:
            if mode == "sync-accessor":
                results.append(request.run_sync_with_timeout(request._await_result()))
            else:
                results.append(request.wait() if mode == "sync" else asyncio.run(await_request()))
        except BaseException as error:  # noqa: BLE001 — capture cancellation from the worker too
            errors.append(error)
        finally:
            finished.set()

    worker = Thread(target=run)
    try:
        request._ensure_submitted()
        assert reached.wait(5)
        # Expire the caller's clock only after the selected native boundary.
        request._submission_deadline = monotonic() - 1
        worker.start()
        assert expired.wait(5)
        assert not finished.is_set()
        release.set()
        worker.join(5)
        assert not worker.is_alive()
        assert len(sends) == 1
        if outcome == "success":
            assert errors == []
            assert results == [response]
            assert request.current_status().code is grpc.StatusCode.OK
        elif outcome == "wrapper_timeout":
            assert errors == [wrapper_error]
        elif outcome == "final_error":
            assert len(errors) == 1
            assert isinstance(errors[0], RequestError)
            assert errors[0].status.code is grpc.StatusCode.INVALID_ARGUMENT
        else:
            assert len(errors) == 1
            if mode != "async":
                assert isinstance(errors[0], RequestError)
                assert errors[0].status.code is grpc.StatusCode.DEADLINE_EXCEEDED
            else:
                assert isinstance(errors[0], TimeoutError)
    finally:
        release.set()
        if worker.ident is not None:
            worker.join(5)
        channel.sync_close(timeout=5)


def test_sync_accessor_uses_non_cross_loop_submission_once():
    """A custom runner receives its submitted handle, not the consumed coroutine."""
    loop = asyncio.new_event_loop()
    submitted = []
    waited = []
    response = Disk()

    class Runtime:
        def in_executor_thread(self):
            return False

    class Adapter:
        _runtime = Runtime()

        def run_async(self, work):
            task = loop.create_task(work)
            loop.run_until_complete(task)
            submitted.append(task)
            return task

        def run_sync(self, work, timeout=None):
            waited.append(work)
            return loop.run_until_complete(work)

    request = Request(
        Adapter(),
        "nebius.compute.v1.DiskService",
        "Get",
        GetDiskRequest(id="custom-runner"),
        Disk,
    )

    async def accessor():
        return response

    try:
        assert request.run_sync_with_timeout(accessor()) is response
        assert waited == submitted
        assert len(waited) == 1
    finally:
        loop.close()
