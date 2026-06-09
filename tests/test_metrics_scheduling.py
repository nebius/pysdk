import asyncio
from time import monotonic

import pytest

from nebius.aio import metrics as metrics_module


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
