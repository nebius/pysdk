"""Store SDK runtime helpers in the current execution context.

Why context variables are used
------------------------------

An application can run several SDK instances at the same time. The instances
can also use the same event loop. A thread-local variable cannot distinguish
tasks that share one thread. A normal module variable would let one SDK
replace the value for another SDK.

:class:`contextvars.ContextVar` stores a different value for each execution
context. Each SDK task therefore gets the scheduler and bridge of its own
runtime. Nested calls are also safe. A nested call can set a new value and can
then restore the previous value with a context token.

How values are retained
-----------------------

The runtime sets both variables before it starts SDK work. A context keeps the
values across each ``await``. By default, a new asyncio task copies the current
context when code creates the task. The child task therefore keeps the same
runtime helpers after its parent continues or resets its own values.

Creating a coroutine object does not copy the current context. A coroutine
uses the context of the task that eventually runs it. Code that needs to
retain the current bindings must create a task while the bindings are active,
or must submit the coroutine through the active scheduler.

The runtime resets both variables in a ``finally`` block when submitted work
ends. Synchronous SDK callbacks use the same set-and-reset procedure. The
stored values are bound methods, so an inherited context keeps its SDK runtime
alive until that context is released.

Limitations
-----------

The :class:`ContextVar` objects are module-level keys. Their values are not
process-wide mutable values, but code outside an active SDK context gets
``None``.

Context inheritance does not register a raw task with the SDK runtime. Code
that calls :func:`asyncio.create_task` directly can keep the runtime helpers.
On a caller-supplied loop, this untracked task can outlive SDK close. On an
SDK-owned loop, final loop shutdown cancels remaining tasks, but normal SDK
submission tracking still omits the raw task. Use the active
``task_scheduler`` or :meth:`nebius.aio.channel.Channel.bg_task` for work that
SDK close must track.

Code can override the copied context when it creates a task. Context values
also do not propagate automatically to an arbitrary worker thread.
:func:`asyncio.to_thread` copies the current context, but
:meth:`asyncio.loop.run_in_executor` does not.

The bridge can identify an :class:`asyncio.Future` and its owner loop. It
cannot identify hidden loop ownership in every custom awaitable. A custom
awaitable with loop-affine state must provide its own cross-loop behavior or
must be used on the event loop that owns that state. A loop-neutral custom
awaitable can be created and used on any loop.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from typing import Any

TaskScheduler = Callable[[Awaitable[Any]], object]
"""Function that submits tracked work to the current SDK runtime."""

AwaitableBridge = Callable[[Awaitable[Any]], Awaitable[Any]]
"""Function that adapts an awaitable for the current SDK runtime."""

task_scheduler: ContextVar[TaskScheduler | None] = ContextVar(
    "nebius_sdk_task_scheduler",
    default=None,
)
"""Tracked-work scheduler for the current execution context.

The value is normally
:meth:`nebius.aio._runtime.AsyncRuntime.submit_background`. It is a bound
method for one SDK runtime.
"""

awaitable_bridge: ContextVar[AwaitableBridge | None] = ContextVar(
    "nebius_sdk_awaitable_bridge",
    default=None,
)
"""Awaitable bridge for the current execution context.

The value is normally
:meth:`nebius.aio._runtime.AsyncRuntime.bridge_awaitable`. It is a bound method
for one SDK runtime.
"""


def bridge_awaitable(awaitable: Awaitable[Any]) -> Awaitable[Any]:
    """Make an awaitable usable by the current SDK runtime.

    This function reads ``awaitable_bridge`` from the current context. It does
    not read a process-wide runtime. Return ``awaitable`` without a change when
    no runtime bridge is active.

    The active bridge converts a foreign-loop :class:`asyncio.Future` to a
    cross-loop awaitable. It does not change a future that already belongs to
    the SDK loop. It also does not inspect custom awaitables for hidden loop
    ownership.

    :param awaitable: Awaitable to examine.
    :return: The original awaitable or a cross-loop awaitable.
    """

    bridge = awaitable_bridge.get()
    return awaitable if bridge is None else bridge(awaitable)
