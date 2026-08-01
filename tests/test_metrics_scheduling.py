import asyncio
from concurrent.futures import Future
from threading import Thread
from time import monotonic

import pytest

from nebius.aio import metrics as metrics_module
from nebius.aio._task_context import task_scheduler


class _ScheduledProbe:
    """Capture scheduler input and expose controllable cancellation."""

    def __init__(self) -> None:
        self.awaitable = None
        self.callbacks = []
        self.is_cancelled = False

    def schedule(self, awaitable):
        self.awaitable = awaitable
        return self

    def _add_internal_done_callback(self, callback) -> None:
        self.callbacks.append(callback)

    def cancelled(self) -> bool:
        return self.is_cancelled

    def cancel(self) -> None:
        self.is_cancelled = True
        for callback in self.callbacks:
            callback(self)

    def fail(self) -> None:
        """Complete exceptionally without reporting cancellation."""

        for callback in self.callbacks:
            callback(self)


@pytest.mark.asyncio
async def test_scheduled_metric_task_is_referenced_until_done() -> None:
    started = asyncio.Event()
    release = asyncio.Event()

    async def awaitable() -> None:
        started.set()
        await release.wait()

    previous_tasks = set(metrics_module._metric_tasks)
    metrics_module._schedule_metric_awaitable(awaitable())
    await started.wait()
    scheduled_tasks = metrics_module._metric_tasks - previous_tasks

    # The task must be retained while pending; asyncio only keeps weak references,
    # so an unreferenced pending task can be garbage collected mid-execution,
    # producing "Task was destroyed but it is pending!" (reported in #94).
    assert len(scheduled_tasks) == 1
    task = next(iter(scheduled_tasks))

    release.set()
    await task
    await asyncio.sleep(0)  # allow the done callback to run

    assert scheduled_tasks.isdisjoint(metrics_module._metric_tasks)


def test_scheduled_metric_runs_synchronously_without_running_loop() -> None:
    ran: list[bool] = []

    async def awaitable() -> None:
        ran.append(True)

    # No running loop -> executed synchronously, nothing scheduled.
    previous_tasks = set(metrics_module._metric_tasks)
    metrics_module._schedule_metric_awaitable(awaitable())

    assert ran == [True]
    assert metrics_module._metric_tasks == previous_tasks


def test_metrics_callbacks_can_be_set_at_creation() -> None:
    events: list[object] = []
    metric = object()

    metrics = metrics_module.Metrics(config_load=events.append)
    metrics_module.emit_metric(metrics, ("config_load", "configLoad"), metric)

    assert events == [metric]
    assert (
        metrics.callback_timeout_seconds
        == metrics_module.DEFAULT_METRIC_CALLBACK_TIMEOUT_SECONDS
    )


@pytest.mark.asyncio
async def test_scheduled_metric_task_uses_sanitized_capped_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(metrics_module, "MAX_METRIC_CALLBACK_TIMEOUT_SECONDS", 0.01)
    cancelled = asyncio.Event()
    never = asyncio.Event()

    async def config_load(metric: object) -> None:
        try:
            await never.wait()
        finally:
            cancelled.set()

    metrics = metrics_module.Metrics(
        config_load=config_load,
        callback_timeout_seconds=3600,
    )
    assert metrics.callback_timeout_seconds == 0.01

    previous_tasks = set(metrics_module._metric_tasks)
    metrics_module.emit_metric(metrics, ("config_load", "configLoad"), object())
    scheduled_tasks = metrics_module._metric_tasks - previous_tasks

    assert len(scheduled_tasks) == 1
    task = next(iter(scheduled_tasks))
    await asyncio.wait_for(cancelled.wait(), timeout=1)
    await task
    await asyncio.sleep(0)  # allow the done callback to run
    assert scheduled_tasks.isdisjoint(metrics_module._metric_tasks)


def test_sync_metric_task_uses_default_for_invalid_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        metrics_module,
        "DEFAULT_METRIC_CALLBACK_TIMEOUT_SECONDS",
        0.01,
    )

    async def config_load(metric: object) -> None:
        await asyncio.sleep(3600)

    start = monotonic()
    metrics_module.emit_metric(
        {
            "config_load": config_load,
            "callback_timeout_seconds": "invalid",
        },
        ("config_load", "configLoad"),
        object(),
    )

    assert monotonic() - start < 0.5


def test_sdk_metric_cancelled_before_start_uses_threadsafe_disposal_hook() -> None:
    """Pre-start cancellation uses the explicit thread-safe cleanup hook."""

    probe = _ScheduledProbe()

    class Awaitable:
        def __init__(self) -> None:
            self.close_calls = 0

        def __await__(self):
            return asyncio.sleep(0).__await__()

        def _cancel_unstarted_threadsafe(self) -> bool:
            self.close_calls += 1
            return True

    awaitable = Awaitable()
    token = task_scheduler.set(probe.schedule)
    try:
        metrics_module._schedule_metric_awaitable(awaitable)
        probe.cancel()
    finally:
        task_scheduler.reset(token)
    assert awaitable.close_calls == 1
    assert probe.awaitable is not None
    probe.awaitable.close()


def test_sdk_metric_start_failure_uses_threadsafe_disposal_hook() -> None:
    """Exceptional scheduler completion also disposes unstarted callback work."""

    probe = _ScheduledProbe()

    class Awaitable:
        def __init__(self) -> None:
            self.close_calls = 0

        def __await__(self):
            return asyncio.sleep(0).__await__()

        def _cancel_unstarted_threadsafe(self) -> bool:
            self.close_calls += 1
            return True

    awaitable = Awaitable()
    token = task_scheduler.set(probe.schedule)
    try:
        metrics_module._schedule_metric_awaitable(awaitable)
        probe.fail()
    finally:
        task_scheduler.reset(token)
    assert awaitable.close_calls == 1
    assert probe.awaitable is not None
    probe.awaitable.close()


def test_sdk_metric_fatal_scheduler_failure_disposes_and_propagates() -> None:
    """Fatal scheduler failure still disposes fresh metric work exactly once."""

    wrapped = []

    class Awaitable:
        def __init__(self) -> None:
            self.close_calls = 0

        def __await__(self):
            return asyncio.sleep(0).__await__()

        def _cancel_unstarted_threadsafe(self) -> bool:
            self.close_calls += 1
            return True

    failure = KeyboardInterrupt("fatal scheduler failure")

    def fail(awaitable):
        wrapped.append(awaitable)
        raise failure

    awaitable = Awaitable()
    token = task_scheduler.set(fail)
    try:
        with pytest.raises(KeyboardInterrupt) as raised:
            metrics_module._schedule_metric_awaitable(awaitable)
        assert raised.value is failure
    finally:
        task_scheduler.reset(token)
    assert awaitable.close_calls == 1
    assert len(wrapped) == 1
    assert wrapped[0].cr_frame is None


def test_metric_fallback_tracking_resets_after_fork() -> None:
    """A child replaces inherited task state and a possibly held lock."""

    inherited_lock = metrics_module._metric_tasks_lock
    inherited_lock.acquire()
    try:
        metrics_module._metric_tasks = {object()}  # type: ignore[assignment]
        metrics_module._reset_metric_tasks_after_fork()
        assert metrics_module._metric_tasks == set()
        assert metrics_module._metric_tasks_lock is not inherited_lock
        assert metrics_module._metric_tasks_lock.acquire(blocking=False)
        metrics_module._metric_tasks_lock.release()
    finally:
        inherited_lock.release()


def test_sdk_metric_pre_start_cancellation_reaches_foreign_future() -> None:
    ready: Future[asyncio.AbstractEventLoop] = Future()

    def run_loop() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        ready.set_result(loop)
        loop.run_forever()
        loop.close()

    thread = Thread(target=run_loop, daemon=True)
    thread.start()
    loop = ready.result(timeout=5)

    async def create_future() -> asyncio.Future[None]:
        return asyncio.get_running_loop().create_future()

    source = asyncio.run_coroutine_threadsafe(create_future(), loop).result(timeout=5)
    probe = _ScheduledProbe()
    token = task_scheduler.set(probe.schedule)
    try:
        metrics_module._schedule_metric_awaitable(source)
        probe.cancel()

        async def wait_until_cancelled() -> None:
            for _ in range(100):
                if source.cancelled():
                    return
                await asyncio.sleep(0.01)
            raise AssertionError("foreign Future was not cancelled")

        asyncio.run_coroutine_threadsafe(
            wait_until_cancelled(),
            loop,
        ).result(timeout=5)
    finally:
        task_scheduler.reset(token)
        if probe.awaitable is not None:
            probe.awaitable.close()
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=5)
        assert not thread.is_alive()


@pytest.mark.asyncio
async def test_active_sdk_metric_cancellation_does_not_force_close() -> None:
    """Active task cancellation owns cleanup of the user awaitable."""

    probe = _ScheduledProbe()
    started = asyncio.Event()
    release = asyncio.Event()

    class Awaitable:
        def __init__(self) -> None:
            self.close_calls = 0
            self.finalized = False

        def __await__(self):
            async def run() -> None:
                started.set()
                try:
                    await release.wait()
                finally:
                    self.finalized = True

            return run().__await__()

        def close(self) -> None:
            self.close_calls += 1

    awaitable = Awaitable()
    token = task_scheduler.set(probe.schedule)
    try:
        metrics_module._schedule_metric_awaitable(awaitable)
    finally:
        task_scheduler.reset(token)
    assert probe.awaitable is not None
    task = asyncio.create_task(probe.awaitable)
    await started.wait()
    probe.cancel()
    assert awaitable.close_calls == 0
    task.cancel()
    await task
    assert awaitable.finalized
