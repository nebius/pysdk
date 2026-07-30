"""Context shared by SDK-owned asynchronous task schedulers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from typing import Any

TaskScheduler = Callable[[Awaitable[Any]], object]
AwaitableBridge = Callable[[Awaitable[Any]], Awaitable[Any]]

task_scheduler: ContextVar[TaskScheduler | None] = ContextVar(
    "nebius_sdk_task_scheduler",
    default=None,
)

awaitable_bridge: ContextVar[AwaitableBridge | None] = ContextVar(
    "nebius_sdk_awaitable_bridge",
    default=None,
)


def bridge_awaitable(awaitable: Awaitable[Any]) -> Awaitable[Any]:
    """Make a loop-bound awaitable safe for the active SDK runtime."""

    bridge = awaitable_bridge.get()
    return awaitable if bridge is None else bridge(awaitable)
