import asyncio

import pytest

from nebius.aio.metrics import _metric_tasks, _schedule_metric_awaitable


@pytest.mark.asyncio
async def test_scheduled_metric_task_is_referenced_until_done() -> None:
    _metric_tasks.clear()
    started = asyncio.Event()
    release = asyncio.Event()

    async def awaitable() -> None:
        started.set()
        await release.wait()

    _schedule_metric_awaitable(awaitable())
    await started.wait()

    # The task must be retained while pending; asyncio only keeps weak references,
    # so an unreferenced pending task can be garbage collected mid-execution,
    # producing "Task was destroyed but it is pending!" (reported in #94).
    assert len(_metric_tasks) == 1
    task = next(iter(_metric_tasks))

    release.set()
    await task
    await asyncio.sleep(0)  # allow the done callback to run

    assert len(_metric_tasks) == 0


def test_scheduled_metric_runs_synchronously_without_running_loop() -> None:
    ran: list[bool] = []

    async def awaitable() -> None:
        ran.append(True)

    # No running loop -> executed synchronously, nothing scheduled.
    _schedule_metric_awaitable(awaitable())

    assert ran == [True]
    assert len(_metric_tasks) == 0
