"""Run SDK asynchronous work on one event loop.

The runtime can own an event loop or use a loop that the caller supplies. An
owned runtime also owns a daemon thread pool. The runtime converts submitted
work to awaitables that callers can use from other event loops.

Runtime state moves in one direction: accepting submissions, preparing close,
then shut down. ``_shutdown_lock`` protects submission acceptance and the
terminal shutdown flag. When code needs both it and ``_submissions_lock``, it
always acquires them in that order. The background and shutdown-preparation
locks protect independent sets and are never held while another thread is
joined or a future result is awaited.

``_active_tasks``, ``_protected_tasks``, and ``_task_submissions`` belong only
to the SDK event-loop thread. They need no thread lock. Code must not acquire a
runtime lock and then synchronously wait for work that needs the SDK loop. This
rule keeps shutdown callbacks able to make progress.
"""

from __future__ import annotations

import asyncio
import os
import sys
import weakref
from collections.abc import Awaitable, Callable, Generator
from concurrent.futures import (
    CancelledError as FutureCancelledError,
)
from concurrent.futures import (
    Future,
    InvalidStateError,
    ThreadPoolExecutor,
)
from concurrent.futures import (
    TimeoutError as FutureTimeoutError,
)
from contextvars import Context, ContextVar, copy_context
from logging import getLogger
from queue import Empty, Queue
from threading import Event as ThreadEvent
from threading import Lock, Thread, current_thread, local
from types import TracebackType
from typing import Any, Generic, TypeVar, cast

from ._task_context import (
    awaitable_bridge,
    close_rejected_sync_awaitable,
    dispose_unstarted_awaitable,
    task_scheduler,
)

T = TypeVar("T")
logger = getLogger(__name__)
_sdk_executor_worker = local()


def _in_sdk_executor_thread() -> bool:
    """Return whether the current thread belongs to any SDK executor."""

    return bool(getattr(_sdk_executor_worker, "active", False))


_current_submission: ContextVar[
    tuple["AsyncRuntime", "CrossLoopAwaitable[Any]"] | None
] = ContextVar("nebius_sdk_current_submission", default=None)
"""Runtime and submission bound to the current SDK task.

The key is module-level, as required by :mod:`contextvars`. Its value belongs
to an execution context rather than to the process as a whole. Storing the
runtime beside the submission lets several SDKs safely share a thread or event
loop: a runtime accepts only a binding whose runtime identity matches itself.
"""


class _WorkItem:
    """Store one function call for a daemon worker.

    A work item writes the call result or exception to a concurrent future.
    """

    def __init__(
        self,
        future: Future[Any],
        fn: Callable[..., Any],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> None:
        """Initialize a worker item.

        :param future: Future that receives the call result.
        :param fn: Function to call.
        :param args: Positional arguments for ``fn``.
        :param kwargs: Keyword arguments for ``fn``.
        """

        self.future = future
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    def run(self) -> None:
        """Run the stored call and complete its future."""

        if not self.future.set_running_or_notify_cancel():
            return
        try:
            result = self.fn(*self.args, **self.kwargs)
        except BaseException as error:
            self.future.set_exception(error)
            # Break the exception -> traceback -> frame -> self cycle while
            # the future retains the exception.
            self = None  # type: ignore[assignment]
        else:
            self.future.set_result(result)


class DaemonThreadPoolExecutor(ThreadPoolExecutor):
    """Run functions in a bounded set of daemon threads.

    :mod:`asyncio` requires a :class:`ThreadPoolExecutor` as its default
    executor. This class provides that interface and creates daemon workers
    lazily as work is submitted, up to the configured maximum.
    """

    def __init__(
        self,
        max_workers: int,
        thread_name_prefix: str = "nebius-sdk",
    ) -> None:
        """Initialize the executor without eagerly starting workers.

        :param max_workers: Number of worker threads.
        :param thread_name_prefix: Prefix for each worker thread name.
        :raises ValueError: If ``max_workers`` is not positive.
        """

        if max_workers <= 0:
            raise ValueError("max_workers must be greater than 0")
        # ThreadPoolExecutor.__init__ establishes its private invariants but
        # does not start threads. We replace only the queue and worker creation
        # needed to guarantee daemon threads; inherited asyncio checks still
        # see a fully initialized ThreadPoolExecutor.
        super().__init__(max_workers, thread_name_prefix=thread_name_prefix)
        self._work_queue: Queue[_WorkItem | None] = Queue()  # type: ignore[assignment]
        self._threads: set[Thread] = set()

    def _worker(self) -> None:
        """Run queued work until the queue contains a stop marker."""

        previous = getattr(_sdk_executor_worker, "active", False)
        _sdk_executor_worker.active = True
        try:
            while True:
                work_item = self._work_queue.get()
                if work_item is None:
                    return
                try:
                    work_item.run()
                except BaseException as error:
                    # Concurrent Future callbacks run inline when a work item
                    # publishes its result. One callback must not permanently
                    # remove a daemon worker from this bounded executor.
                    logger.critical(
                        "Unhandled exception in SDK executor completion callback",
                        exc_info=error,
                    )
                finally:
                    del work_item
                    self._idle_semaphore.release()
        finally:
            _sdk_executor_worker.active = previous

    def submit(
        self,
        fn: Callable[..., T],
        /,
        *args: Any,
        **kwargs: Any,
    ) -> Future[T]:
        """Submit a function call to the worker queue.

        :param fn: Function to call.
        :param args: Positional arguments for ``fn``.
        :param kwargs: Keyword arguments for ``fn``.
        :return: Future that receives the call result.
        :raises RuntimeError: If executor shutdown has started.
        """

        with self._shutdown_lock:
            if self._shutdown:
                raise RuntimeError("cannot schedule new futures after shutdown")
            has_idle_worker = self._idle_semaphore.acquire(blocking=False)
            if not has_idle_worker and len(self._threads) < self._max_workers:
                thread = Thread(
                    name=f"{self._thread_name_prefix}_{len(self._threads)}",
                    target=self._worker,
                    daemon=True,
                )
                self._threads.add(thread)
                try:
                    thread.start()
                except BaseException:
                    self._threads.discard(thread)
                    raise
            future: Future[T] = Future()
            self._work_queue.put(_WorkItem(future, fn, args, kwargs))
            return future

    def shutdown(
        self,
        wait: bool = True,
        *,
        cancel_futures: bool = False,
    ) -> None:
        """Stop the executor.

        This method does not interrupt a function that is already running.

        :param wait: Wait for worker threads to stop when this value is
            ``True``.
        :param cancel_futures: Cancel queued work that has not started when
            this value is ``True``.
        """

        with self._shutdown_lock:
            first_shutdown = not self._shutdown
            self._shutdown = True
            if cancel_futures:
                while True:
                    try:
                        work_item = self._work_queue.get_nowait()
                    except Empty:
                        break
                    if work_item is not None:
                        work_item.future.cancel()
            if first_shutdown or cancel_futures:
                for _ in self._threads:
                    self._work_queue.put(None)
        if wait:
            calling_thread = current_thread()
            for thread in self._threads:
                if thread is not calling_thread:
                    thread.join()

    def __enter__(self) -> DaemonThreadPoolExecutor:
        """Return this executor for use as a context manager."""

        return self

    def owns_thread(self, thread: Thread) -> bool:
        """Return whether this executor owns ``thread``.

        :param thread: Thread to examine.
        :return: ``True`` if ``thread`` is an executor worker.
        """

        return thread in self._threads

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Stop the executor when its context exits."""

        self.shutdown(wait=True)


def _publish_cross_loop_waiter(
    source: Future[T],
    loop_ref: weakref.ReferenceType[asyncio.AbstractEventLoop],
    relay_ref: weakref.ReferenceType[asyncio.Future[T]],
) -> None:
    """Publish one concurrent result to a weakly retained asyncio waiter.

    :param source: Authoritative concurrent completion.
    :param loop_ref: Weak reference to the waiter's event loop.
    :param relay_ref: Weak reference to the waiter's relay future.
    """

    def publish() -> None:
        """Copy the result on the relay's owner loop."""

        relay = relay_ref()
        if relay is None or relay.done():
            if not source.cancelled():
                source.exception()
            return
        if source.cancelled():
            relay.cancel()
            return
        error = source.exception()
        if error is not None:
            relay.set_exception(error)
        else:
            relay.set_result(source.result())

    loop = loop_ref()
    if loop is None:
        if not source.cancelled():
            source.exception()
        return
    try:
        loop.call_soon_threadsafe(publish)
    except RuntimeError:
        # A caller-owned loop can close after its waiter is cancelled.
        # Consume only diagnostic state; the shared result remains available
        # to other loops and synchronous readers.
        if not source.cancelled():
            source.exception()


class CrossLoopAwaitable(Generic[T]):
    """Provide loop-independent access to a concurrent future.

    Callers can await the same instance from the SDK loop and from multiple
    external loops. Synchronous callers can use :meth:`result`. An SDK-owned
    executor worker cannot wait for a pending handle because the submitted
    work can need that finite executor. A submission also cannot await its own
    handle.

    All waiters share one concurrent future. Cancellation by one direct
    awaiter cancels that future and therefore affects every waiter. Use
    :func:`asyncio.shield` when cancellation of one waiter must not cancel the
    shared submission. The concurrent future reports cancellation as soon as
    it accepts the request. The SDK coroutine can still be running its
    asynchronous ``finally`` block; SDK close drains that finalization.

    This object is awaitable but is not an :class:`asyncio.Future` or
    :class:`asyncio.Task`. Functions such as :func:`asyncio.gather` accept it.
    Wrap it with :func:`asyncio.ensure_future` before giving it to
    :func:`asyncio.wait`. Task-only naming, coroutine-inspection, and callback
    removal methods are not available.

    A public completion callback uses the running event loop that registers
    it. The loop must stay running until delivery. The SDK does not move the
    callback to its completion thread if the registration loop stops or
    closes. Dispatch is best effort: a loop that stops after accepting the
    callback can retain it until that loop is closed or run again.
    """

    def __init__(
        self,
        future: Future[T],
        event_loop: asyncio.AbstractEventLoop,
    ) -> None:
        """Initialize a cross-loop awaitable.

        Applications normally receive this type from SDK methods instead of
        constructing it directly.

        :param future: Concurrent future that stores the result.
        :param event_loop: Event loop for the associated SDK runtime. A
            bridged foreign future can still be owned by another loop.
        """

        self._process_id = os.getpid()
        self._future = future
        self._event_loop = event_loop
        self._waiters_lock = Lock()
        self._waiters: dict[
            object,
            tuple[
                weakref.ReferenceType[asyncio.AbstractEventLoop],
                weakref.ReferenceType[asyncio.Future[T]],
            ],
        ] = {}
        waiters_lock = self._waiters_lock
        waiters = self._waiters

        def publish_waiters(source: Future[T]) -> None:
            """Detach and publish every waiter through its owner loop."""

            with waiters_lock:
                destinations = list(waiters.values())
                waiters.clear()
            for loop_ref, relay_ref in destinations:
                _publish_cross_loop_waiter(source, loop_ref, relay_ref)

        # One callback serves every asyncio waiter. Cancelled waiters remove
        # themselves from the registry instead of accumulating callbacks on a
        # long-lived concurrent future.
        self._future.add_done_callback(publish_waiters)

    @classmethod
    def _for_runtime(
        cls,
        future: Future[T],
        event_loop: asyncio.AbstractEventLoop,
    ) -> CrossLoopAwaitable[T]:
        """Create a handle associated with an SDK event loop."""

        return cls(future, event_loop)

    def _check_process(self) -> None:
        """Reject a handle inherited by a child process before locking."""

        if os.getpid() != self._process_id:
            raise RuntimeError(
                "an SDK awaitable cannot be used after fork; construct SDK "
                "objects only after the child process starts"
            )

    @property
    def event_loop(self) -> asyncio.AbstractEventLoop:
        """Return the event loop for the associated SDK runtime."""

        self._check_process()
        return self._event_loop

    def cancel(self, msg: object | None = None) -> bool:
        """Request cancellation of the submitted work.

        ``msg`` is accepted for :class:`asyncio.Task` call compatibility. A
        concurrent future cannot carry that message, so it is ignored.

        :param msg: Optional cancellation message, retained only for call
            compatibility.
        :return: ``True`` if the future accepted the cancellation request.
        """

        self._check_process()
        return self._future.cancel()

    def _cancel_unstarted_threadsafe(self) -> bool:
        """Cancel this thread-safe handle for an unstarted wrapper."""

        return self.cancel()

    def cancelled(self) -> bool:
        """Return whether the submission accepted cancellation.

        The SDK coroutine can still be completing an asynchronous finalizer.
        """

        self._check_process()
        return self._future.cancelled()

    def done(self) -> bool:
        """Return whether the cross-loop result has reached a terminal state.

        A cancelled result can become terminal before the SDK coroutine has
        completed its asynchronous finalizer.
        """

        self._check_process()
        return self._future.done()

    def result(self, timeout: float | None = None) -> T:
        """Wait for and return the submitted work result.

        A pending result cannot be synchronously read from an active asyncio
        loop because doing so would block that loop. Await this object instead.

        :param timeout: Maximum wait time in seconds. Use ``None`` to wait
            without a time limit.
        :return: Result of the submitted work.
        :raises concurrent.futures.TimeoutError: If the time limit expires.
        :raises RuntimeError: If a pending result is requested from an active
            asyncio loop or an SDK-owned executor worker.
        :raises concurrent.futures.CancelledError: If the submitted work was
            cancelled. This is the concurrent-future exception, not
            :class:`asyncio.CancelledError`.
        """

        self._check_process()
        self._reject_executor_wait()
        self._reject_blocking_async_wait()
        return self._future.result(timeout)

    def _result(self, timeout: float | None = None) -> T:
        """Return the result for a compatibility path that permits blocking.

        Internal synchronous SDK adapters use this method after applying their
        own loop and deadlock rules.

        :param timeout: Maximum wait time in seconds.
        :return: Submitted work result.
        """

        self._check_process()
        self._reject_executor_wait()
        return self._future.result(timeout)

    def exception(self, timeout: float | None = None) -> BaseException | None:
        """Wait for and return the submitted work exception.

        A pending exception cannot be synchronously read from an active
        asyncio loop because doing so would block that loop. Await this object
        instead.

        :param timeout: Maximum wait time in seconds. Use ``None`` to wait
            without a time limit.
        :return: Exception from the submitted work, or ``None`` if it
            completed successfully.
        :raises concurrent.futures.TimeoutError: If the time limit expires.
        :raises RuntimeError: If a pending exception is requested from an
            active asyncio loop or an SDK-owned executor worker.
        :raises concurrent.futures.CancelledError: If the submitted work was
            cancelled. This is the concurrent-future exception, not
            :class:`asyncio.CancelledError`.
        """

        self._check_process()
        self._reject_executor_wait()
        self._reject_blocking_async_wait()
        return self._future.exception(timeout)

    def _reject_executor_wait(self) -> None:
        """Reject a pending wait from a worker in any SDK finite pool."""

        if self._future.done():
            return
        if _in_sdk_executor_thread():
            raise RuntimeError(
                "cannot wait for pending SDK work from an SDK executor worker"
            )

    def _reject_blocking_async_wait(self) -> None:
        """Reject a pending synchronous wait from an active event loop."""

        self._check_process()
        if self._future.done():
            return
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return
        raise RuntimeError(
            "cannot synchronously wait for pending SDK work from an asyncio "
            "event loop; await it instead"
        )

    def add_done_callback(
        self,
        callback: Callable[[CrossLoopAwaitable[T]], object],
        *,
        context: Context | None = None,
    ) -> None:
        """Add a function to call when the submitted work is complete.

        Like :class:`asyncio.Task`, this method schedules the callback instead
        of calling it inline. It uses the event loop active at registration,
        or the associated SDK loop when no loop is active. The registration
        context is retained unless ``context`` is supplied explicitly. The
        registration loop must stay running until callback delivery. The SDK
        logs and drops a callback if the loop has already stopped or rejects
        dispatch. A loop that stops after accepting dispatch can retain the
        queued callback until it is closed or run again.

        :param callback: Function that receives this awaitable.
        :param context: Optional context in which to run ``callback``.
        :raises RuntimeError: If the callback loop is not running.
        """

        self._check_process()
        try:
            callback_loop = asyncio.get_running_loop()
        except RuntimeError:
            callback_loop = self._event_loop
        if callback_loop.is_closed() or not callback_loop.is_running():
            raise RuntimeError("callback event loop is not running")
        callback_context = copy_context() if context is None else context
        state: dict[str, Any] = {
            "callback": callback,
            "context": callback_context,
            "loop": callback_loop,
        }

        def schedule(_: Future[T]) -> None:
            """Schedule the public callback on its registration loop."""

            retained_callback = state.pop("callback", None)
            retained_context = state.pop("context", None)
            retained_loop = state.pop("loop", None)
            if retained_callback is None or retained_loop is None:
                return
            if not retained_loop.is_running():
                logger.warning(
                    "SDK completion callback was not run because its "
                    "registration loop is not running"
                )
                return
            try:
                retained_loop.call_soon_threadsafe(
                    retained_callback,
                    self,
                    context=retained_context,
                )
            except RuntimeError:
                # Affinity cannot be preserved after a caller-owned loop
                # closes. Do not run loop-affine user code on the completion
                # thread.
                logger.warning(
                    "SDK completion callback was not run because its "
                    "registration loop is not running"
                )

        self._future.add_done_callback(schedule)

    def _add_internal_done_callback(
        self,
        callback: Callable[[CrossLoopAwaitable[T]], object],
    ) -> None:
        """Run a lifecycle callback synchronously on future completion.

        Internal cleanup must not depend on a caller-owned callback loop that
        can stop or close independently of the SDK.

        :param callback: Runtime callback that receives this awaitable.
        """

        state: list[object] = [callback, self]

        def invoke(_: Future[T]) -> None:
            """Run once and release callback/runtime references."""

            if not state:
                return
            retained_callback = cast(
                Callable[[CrossLoopAwaitable[T]], object], state.pop(0)
            )
            retained_self = cast(CrossLoopAwaitable[T], state.pop(0))
            retained_callback(retained_self)

        self._future.add_done_callback(invoke)

    async def _wait(self) -> T:
        """Wait for the concurrent future from the current event loop."""

        try:
            return await self._wait_shielded()
        except asyncio.CancelledError:
            # A direct waiter owns cancellation of the shared submission.
            # _wait_shielded uses an identity-preserving relay instead of
            # asyncio.wrap_future(), whose exception conversion clones
            # built-in TimeoutError on some supported Python versions.
            self.cancel()
            raise

    async def _wait_shielded(self) -> T:
        """Wait without letting one asyncio waiter cancel shared work.

        A private relay copies completion onto the current loop without
        chaining cancellation back to the shared concurrent future. This is
        deliberately not implemented with :func:`asyncio.shield`: newer
        asyncio versions report a late inner exception when a shielded waiter
        has already been cancelled. The relay observes that abandoned result
        while independent waits retain the same shared outcome.

        :return: Submitted work result.
        """

        self._check_process()
        binding = _current_submission.get()
        if binding is not None and binding[1] is self and not self._future.done():
            raise RuntimeError("SDK work cannot await its own submission handle")
        self._reject_executor_wait()
        loop = asyncio.get_running_loop()
        relay: asyncio.Future[T] = loop.create_future()
        loop_ref = weakref.ref(loop)
        relay_ref = weakref.ref(relay)
        waiter_id = object()
        with self._waiters_lock:
            completed = self._future.done()
            if not completed:
                self._waiters[waiter_id] = (loop_ref, relay_ref)
        if completed:
            _publish_cross_loop_waiter(self._future, loop_ref, relay_ref)
        try:
            return await relay
        finally:
            with self._waiters_lock:
                self._waiters.pop(waiter_id, None)

    def __await__(self) -> Generator[Any, None, T]:
        """Return an iterator that waits for the submitted work."""

        self._check_process()
        return self._wait().__await__()


class AsyncRuntime:
    """Run all asynchronous work for one SDK instance.

    An owned runtime starts one daemon event-loop thread and an independent
    daemon executor. A borrowed runtime uses an event loop that the caller
    supplies. Shutdown does not stop a borrowed loop or manage its default
    executor. Consequently, callers must not occupy every worker of that
    executor with synchronous SDK waits: internal or extension code on the
    borrowed loop may need the same executor, and arbitrary executor worker
    threads cannot be identified reliably by the SDK.
    """

    def __init__(
        self,
        event_loop: asyncio.AbstractEventLoop | None,
        executor_max_workers: int,
    ) -> None:
        """Initialize an SDK runtime.

        :param event_loop: Running caller-owned loop to use. Use ``None`` to
            create an owned loop.
        :param executor_max_workers: Number of daemon executor workers for an
            owned loop. A borrowed loop ignores this value.
        :raises ValueError: If a supplied loop is not running, or if an owned
            executor size is not positive.
        """

        self._owned = event_loop is None
        self._process_id = os.getpid()
        if self._owned and executor_max_workers <= 0:
            raise ValueError("executor_max_workers must be greater than 0")
        self._loop = event_loop or asyncio.new_event_loop()
        try:
            self._executor = (
                DaemonThreadPoolExecutor(
                    executor_max_workers,
                    "nebius-sdk-worker",
                )
                if self._owned
                else None
            )
        except BaseException:
            if self._owned:
                self._loop.close()
            raise
        self._loop_thread: Thread | None = None
        self._shutdown_lock = Lock()
        self._accepting = True
        self._shutdown = False
        self._shutdown_failure: BaseException | None = None
        self._shutdown_complete = Future[None]()
        self._shutdown_prepare_lock = Lock()
        self._shutdown_preparing = False
        self._shutdown_dispatch_abandoned = False
        self._background_lock = Lock()
        self._background: set[CrossLoopAwaitable[Any]] = set()
        self._submissions_lock = Lock()
        self._submissions: set[CrossLoopAwaitable[Any]] = set()
        self._protected_submissions: set[CrossLoopAwaitable[Any]] = set()
        self._close_returning_submissions: set[CrossLoopAwaitable[Any]] = set()
        self._active_tasks: set[asyncio.Task[Any]] = set()
        self._protected_tasks: set[asyncio.Task[Any]] = set()
        self._protected_cancelling_tasks: set[asyncio.Task[Any]] = set()
        self._task_submissions: dict[
            asyncio.Task[Any],
            CrossLoopAwaitable[Any],
        ] = {}
        self._task_cancellation_requested: set[asyncio.Task[Any]] = set()
        if self._owned:
            started = Future[None]()

            def run() -> None:
                """Run and close the owned event loop."""
                try:
                    asyncio.set_event_loop(self._loop)
                    executor = self._executor
                    if executor is None:
                        raise RuntimeError("owned SDK runtime has no executor")
                    self._loop.set_default_executor(executor)
                except BaseException as error:
                    try:
                        self._loop.close()
                    finally:
                        started.set_exception(error)
                    return
                try:
                    # Publish readiness from a loop callback, not merely from
                    # the thread that is about to enter ``run_forever``. This
                    # guarantees that constructor return and immediate
                    # cross-thread submission cannot race loop startup.
                    self._loop.call_soon(started.set_result, None)
                    self._loop.run_forever()
                except BaseException as error:
                    if not started.done():
                        started.set_exception(error)
                    else:
                        self._record_shutdown_failure(error)
                finally:
                    with self._shutdown_lock:
                        shutdown_started = self._shutdown
                    with self._shutdown_prepare_lock:
                        recover_shutdown = (
                            self._shutdown_preparing and not shutdown_started
                        )
                        if recover_shutdown:
                            # A queued preparation callback can otherwise run
                            # during the cleanup loop's run_until_complete and
                            # create a task too late to drain safely.
                            self._shutdown_dispatch_abandoned = True
                    try:
                        self._cancel_remaining_tasks()
                    except BaseException as error:
                        self._record_shutdown_failure(error)
                    finally:
                        try:
                            self._loop.close()
                        except BaseException as error:
                            self._record_shutdown_failure(error)
                    # A thread-safe shutdown-preparation callback can be
                    # accepted immediately after the loop takes its final
                    # ready-queue snapshot. If it never executes, recover
                    # after loop closure instead of stranding completion.
                    if recover_shutdown:
                        self._start_shutdown_thread()

            self._loop_thread = Thread(
                name="nebius-sdk-loop",
                target=run,
                daemon=True,
            )
            try:
                self._loop_thread.start()
                started.result()
            except BaseException:
                executor = self._executor
                try:
                    if self._loop.is_running():
                        try:
                            self._loop.call_soon_threadsafe(self._loop.stop)
                        except RuntimeError:
                            pass
                    if self._loop_thread.ident is not None:
                        self._loop_thread.join()
                    if not self._loop.is_closed():
                        self._loop.close()
                finally:
                    if executor is not None:
                        executor.shutdown(wait=True, cancel_futures=True)
                raise
        else:
            if not self._loop.is_running():
                raise ValueError("a supplied event loop must already be running")

    @property
    def event_loop(self) -> asyncio.AbstractEventLoop:
        """Return the event loop that runs SDK work."""

        return self._loop

    @property
    def owned(self) -> bool:
        """Return whether this runtime owns its event loop."""

        return self._owned

    def in_event_loop(self) -> bool:
        """Return whether the caller runs on this runtime's event loop."""

        try:
            return asyncio.get_running_loop() is self._loop
        except RuntimeError:
            return False

    def in_executor_thread(self) -> bool:
        """Return whether the caller runs on any SDK-owned executor."""

        return _in_sdk_executor_thread()

    def submit(
        self,
        awaitable: Awaitable[T],
        *,
        track: bool = True,
    ) -> CrossLoopAwaitable[T]:
        """Submit an awaitable to the SDK event loop.

        The returned object can be awaited from any event loop. If
        ``awaitable`` is a future from a different loop, this method creates a
        completion bridge.

        :param awaitable: Work to run.
        :param track: Track the submission for cancellation during close.
            Set this value to ``False`` only for shutdown work that the runtime
            must protect.
        :return: Cross-loop awaitable for the result.
        :raises RuntimeError: If runtime close has started.
        """

        if os.getpid() != self._process_id:
            dispose_unstarted_awaitable(awaitable)
            raise RuntimeError(
                "an SDK runtime cannot be used after fork; construct SDK "
                "objects only after the child process starts"
            )
        self._reject_self_submission(awaitable)
        try:
            return self._submit_without_disposal(awaitable, track=track)
        except BaseException:
            # Custom close/cancellation hooks can re-enter SDK lifecycle APIs.
            # Run them only after the runtime admission lock is released.
            dispose_unstarted_awaitable(awaitable)
            raise

    def _reject_self_submission(self, awaitable: Awaitable[object]) -> None:
        """Reject a handle that would indirectly await its own submission.

        Rejection deliberately does not dispose the handle: it represents the
        currently running submission rather than new, unowned work.

        :param awaitable: Candidate SDK work.
        :raises RuntimeError: If the current submission resubmits its own
            pending handle.
        """

        binding = _current_submission.get()
        if (
            isinstance(awaitable, CrossLoopAwaitable)
            and binding is not None
            and binding[1] is awaitable
            and not awaitable.done()
        ):
            # Wrapping the current handle would hide direct self-await behind
            # a child task: the parent would await the child while the child
            # awaited the parent. This is also true across runtimes (A submits
            # its handle to B, then awaits B). Keep ownership with the running
            # submission and reject without cancelling or disposing its
            # handle.
            raise RuntimeError("SDK work cannot submit its own submission handle")

    def _submit_without_disposal(
        self,
        awaitable: Awaitable[T],
        *,
        track: bool = True,
    ) -> CrossLoopAwaitable[T]:
        """Admit SDK work without invoking caller cleanup hooks on failure.

        Callers use this primitive while they hold a lifecycle admission lock.
        They must dispose rejected work after releasing that lock. Process and
        self-submission validation must already be complete.

        :param awaitable: Work to schedule.
        :param track: Track the submission for normal close cancellation.
        :return: Cross-loop awaitable for the result.
        :raises RuntimeError: If the runtime is closing or its loop stopped.
        """

        rejection: RuntimeError | None = None
        with self._shutdown_lock:
            if self._shutdown or not self._accepting:
                rejection = RuntimeError("SDK runtime is closing or closed")
            elif not self._loop.is_running():
                rejection = RuntimeError("SDK event loop is not running")
            elif isinstance(awaitable, asyncio.Future):
                owner_loop = awaitable.get_loop()
                if owner_loop is not self._loop:
                    submitted = self._bridge_foreign_future(awaitable, owner_loop)
                else:
                    submitted = self._submit_to_loop(
                        awaitable,
                        protect_task=not track,
                    )
            elif rejection is None:
                submitted = self._submit_to_loop(
                    awaitable,
                    protect_task=not track,
                )
            if rejection is None and track:
                self._track_submission(submitted)
        if rejection is not None:
            raise rejection
        return submitted

    def _submit_to_loop(
        self,
        awaitable: Awaitable[T],
        *,
        protect_task: bool = False,
    ) -> CrossLoopAwaitable[T]:
        """Schedule an awaitable on the SDK event loop.

        :param awaitable: Work to schedule.
        :param protect_task: Protect the asyncio task from normal submission
            cancellation.
        :return: Cross-loop awaitable for the result.
        """

        event_loop = self._loop
        future: Future[T] = Future()
        submitted = CrossLoopAwaitable._for_runtime(
            future,
            event_loop,
        )
        state_lock = Lock()
        task: asyncio.Task[T] | None = None
        start_claimed = False
        started = False
        disposed = False
        work: list[Awaitable[T]] = [awaitable]

        async def run() -> T:
            """Run the awaitable with its submission context."""

            nonlocal started
            with state_lock:
                started = True
                current_work = work[0]
            token = _current_submission.set((self, submitted))
            try:
                return await self._run_awaitable(
                    current_work,
                    protect_task=protect_task,
                )
            finally:
                _current_submission.reset(token)

        def forward_cancellation(completed: Future[T]) -> None:
            """Send destination cancellation to the SDK task."""

            nonlocal disposed
            if not completed.cancelled():
                return
            with state_lock:
                current_task = task
                should_dispose = (
                    current_task is None
                    and not start_claimed
                    and not started
                    and not disposed
                )
                if should_dispose:
                    disposed = True
                    rejected_work = work.pop()
            if should_dispose:
                dispose_unstarted_awaitable(rejected_work)
            elif current_task is not None:
                try:
                    event_loop.call_soon_threadsafe(
                        self._cancel_task_once,
                        current_task,
                    )
                except RuntimeError:
                    # Final loop cleanup also cancels remaining tasks. If the
                    # loop is already closed, no callback can be dispatched.
                    pass

        def copy_outcome(completed: asyncio.Task[T]) -> None:
            """Publish task completion without translating its exception."""

            nonlocal disposed, task
            if completed.cancelled():
                with state_lock:
                    should_dispose = not started and not disposed
                    if should_dispose:
                        disposed = True
                        rejected_work = work.pop()
                    else:
                        work.clear()
                    task = None
                if should_dispose:
                    dispose_unstarted_awaitable(rejected_work)
                future.cancel()
                return
            try:
                result = completed.result()
            except BaseException as error:
                with state_lock:
                    work.clear()
                    task = None
                try:
                    future.set_exception(error)
                except InvalidStateError:
                    pass
            else:
                with state_lock:
                    work.clear()
                    task = None
                try:
                    future.set_result(result)
                except InvalidStateError:
                    # The public handle won a cancellation race. Its callback
                    # has already forwarded cancellation to the SDK task.
                    pass

        def start_on_loop() -> None:
            """Create the SDK task only after dispatch reaches its loop."""

            nonlocal disposed, start_claimed, task
            with state_lock:
                skip_start = future.cancelled() or disposed
                should_dispose = skip_start and not disposed
                if skip_start:
                    if not disposed:
                        disposed = True
                        rejected_work = work.pop()
                else:
                    # A borrowed loop may use an eager task factory. Reserve
                    # ownership before create_task(), then release this
                    # non-reentrant lock before user code can start.
                    start_claimed = True
            if skip_start:
                if should_dispose:
                    dispose_unstarted_awaitable(rejected_work)
                return

            runner = run()
            try:
                created_task = event_loop.create_task(runner)
            except BaseException as start_error:
                runner.close()
                with state_lock:
                    start_claimed = False
                    should_dispose = not started and not disposed
                    if should_dispose:
                        disposed = True
                        rejected_work = work.pop()
                if should_dispose:
                    dispose_unstarted_awaitable(rejected_work)
                try:
                    future.set_exception(start_error)
                except InvalidStateError:
                    pass
                return

            with state_lock:
                task = created_task
                start_claimed = False
                cancel_now = future.cancelled()
            created_task.add_done_callback(copy_outcome)
            if cancel_now:
                self._cancel_task_once(created_task)

        future.add_done_callback(forward_cancellation)
        try:
            event_loop.call_soon_threadsafe(start_on_loop)
        except BaseException:
            with state_lock:
                disposed = True
                work.clear()
            future.cancel()
            raise
        return submitted

    def _track_submission(self, submitted: CrossLoopAwaitable[Any]) -> None:
        """Track a submission until it is complete.

        :param submitted: Submission to track.
        """

        with self._submissions_lock:
            self._submissions.add(submitted)
        submitted._add_internal_done_callback(self._discard_submission)

    def _discard_submission(self, submitted: CrossLoopAwaitable[Any]) -> None:
        """Remove a completed submission from runtime tracking.

        :param submitted: Completed submission to remove.
        """

        with self._submissions_lock:
            self._submissions.discard(submitted)
            self._protected_submissions.discard(submitted)
            self._close_returning_submissions.discard(submitted)

    def protect_current_submission(self) -> CrossLoopAwaitable[Any] | None:
        """Protect the current internal close caller from normal cancellation.

        :return: Current submission, or ``None`` if the caller is not a
            runtime submission.
        """

        binding = _current_submission.get()
        submitted = binding[1] if binding is not None and binding[0] is self else None
        task = asyncio.current_task() if self.in_event_loop() else None
        if submitted is not None:
            with self._submissions_lock:
                if submitted in self._submissions:
                    self._protected_submissions.add(submitted)
            if task is not None:
                first_protection = task not in self._protected_tasks
                self._protected_tasks.add(task)
                cancelling = getattr(task, "cancelling", None)
                if (
                    isinstance(sys.exc_info()[1], asyncio.CancelledError)
                    or callable(cancelling)
                    and cancelling() > 0
                ):
                    # Python 3.10 has no Task.cancelling(). Capture the active
                    # CancelledError while a raw child enters close so runtime
                    # shutdown cannot inject a second cancellation into that
                    # child's asynchronous finalizer.
                    self._protected_cancelling_tasks.add(task)
                if first_protection and task not in self._task_submissions:
                    # A raw child task can inherit the current submission
                    # context without passing through ``_run_awaitable``.
                    # It is not covered by that wrapper's ``finally`` block,
                    # so discard its temporary protection when it completes.
                    task.add_done_callback(self._discard_protected_task)
        return submitted

    def _discard_protected_task(self, task: asyncio.Task[Any]) -> None:
        """Forget protection and captured cancellation state for one task."""

        self._protected_tasks.discard(task)
        self._protected_cancelling_tasks.discard(task)

    def mark_current_submission_close_returning(self) -> None:
        """Mark that the current internal caller can return from close."""

        binding = _current_submission.get()
        submitted = binding[1] if binding is not None and binding[0] is self else None
        if submitted is not None:
            with self._submissions_lock:
                if submitted in self._protected_submissions:
                    self._close_returning_submissions.add(submitted)

    def begin_close(self) -> None:
        """Reject new runtime submissions."""

        with self._shutdown_lock:
            self._accepting = False

    def _cancel_task_once(self, task: asyncio.Task[Any]) -> None:
        """Request cancellation through one SDK-loop-owned task edge.

        A public handle cancellation and runtime shutdown can race to cancel
        the same task. Recording the request on the SDK loop prevents the
        later edge from injecting another ``CancelledError`` while the task
        is executing an asynchronous finalizer. Runtime shutdown deliberately
        does not cancel the public concurrent future here: a native RPC that
        is already terminal can still absorb task cancellation and publish
        its authoritative result.

        :param task: SDK-loop task to cancel.
        """

        if task.done() or task in self._task_cancellation_requested:
            return
        self._task_cancellation_requested.add(task)
        task.cancel()

    async def cancel_submissions(self) -> None:
        """Cancel tracked work once and wait for task finalizers.

        This method does not cancel protected internal close callers. It
        cancels active SDK work through one private task-cancellation edge.
        Recording every request before tasks resume prevents parent-to-child
        propagation from injecting a second cancellation into an asynchronous
        finalizer. Public handles remain pending until their task publishes an
        outcome, which preserves native RPC results that won the close race.
        """

        current = asyncio.current_task(self._loop)
        tasks = list(
            self._active_tasks
            - self._protected_tasks
            - ({current} if current is not None else set())
        )
        for task in tasks:
            self._cancel_task_once(task)
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        # Let active task outcomes publish before cancelling submissions that
        # never started. Their public handles are not cancellation markers for
        # runtime-initiated shutdown because native completion may have won.
        await asyncio.sleep(0)
        with self._submissions_lock:
            submissions = list(self._submissions - self._protected_submissions)
        for submitted in submissions:
            submitted.cancel()
        await asyncio.sleep(0)

        # A submission may have started between the initial task snapshot and
        # cancellation of the remaining concurrent Futures. Its one forwarded
        # cancellation is enough; only wait for its finalizer here.
        tasks = list(
            self._active_tasks
            - self._protected_tasks
            - ({current} if current is not None else set())
        )
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def _bridge_foreign_future(
        self,
        source: asyncio.Future[T],
        owner_loop: asyncio.AbstractEventLoop,
    ) -> CrossLoopAwaitable[T]:
        """Bridge a future from another event loop.

        The bridge copies completion to a concurrent future. Cancellation of
        the bridge is sent to the source loop. Every source operation,
        including terminal-state inspection, runs on that owning loop. The
        owner must therefore remain running even when the source is already
        complete; otherwise the bridge fails promptly without inspecting it.

        :param source: Future to bridge.
        :param owner_loop: Event loop that owns ``source``.
        :return: Cross-loop awaitable for the source result.
        """

        bridged: Future[T] = Future()
        state: dict[str, object] = {"source": source, "owner_loop": owner_loop}

        def copy_result(completed: asyncio.Future[T]) -> None:
            """Copy source completion to the bridge."""

            if completed.cancelled():
                bridged.cancel()
                return
            try:
                exception = completed.exception()
            except BaseException as error:
                try:
                    bridged.set_exception(error)
                except InvalidStateError:
                    pass
                return
            try:
                if exception is not None:
                    bridged.set_exception(exception)
                else:
                    bridged.set_result(completed.result())
            except InvalidStateError:
                pass

        def forward_cancellation(completed: Future[T]) -> None:
            """Send bridge cancellation to the source loop."""

            retained_source = cast(
                "asyncio.Future[T] | None", state.pop("source", None)
            )
            retained_loop = cast(
                "asyncio.AbstractEventLoop | None", state.pop("owner_loop", None)
            )
            if (
                completed.cancelled()
                and retained_source is not None
                and retained_loop is not None
            ):
                try:
                    retained_loop.call_soon_threadsafe(
                        cancel_on_owner,
                        retained_source,
                    )
                except RuntimeError:
                    pass

        def cancel_on_owner(retained_source: asyncio.Future[T]) -> None:
            """Cancel the source only from its owning event loop."""

            if not retained_source.done():
                retained_source.cancel()

        def attach_on_owner() -> None:
            """Attach completion handling only from the owning event loop."""

            retained_source = cast("asyncio.Future[T] | None", state.get("source"))
            if retained_source is None:
                return
            if bridged.cancelled():
                cancel_on_owner(retained_source)
            else:
                retained_source.add_done_callback(copy_result)

        bridged.add_done_callback(forward_cancellation)
        if not owner_loop.is_running():
            bridged.set_exception(
                RuntimeError("foreign future owner event loop is not running")
            )
        else:
            try:
                owner_loop.call_soon_threadsafe(attach_on_owner)
            except RuntimeError as error:
                bridged.set_exception(error)
        return CrossLoopAwaitable._for_runtime(
            bridged,
            self._loop,
        )

    async def _run_awaitable(
        self,
        awaitable: Awaitable[T],
        *,
        protect_task: bool = False,
    ) -> T:
        """Run an awaitable with SDK task context and lifecycle tracking.

        The method binds ``task_scheduler`` and ``awaitable_bridge`` to this
        runtime before it awaits the submitted work. Context variables retain
        these bound methods across suspension points. By default, a child
        asyncio task also receives a copy of the context that exists when code
        creates the child.

        The ``finally`` block restores the previous bindings with context
        tokens. This restoration supports nested runtime calls in the same
        context. Context isolation prevents one SDK task from replacing
        another task's bindings.

        Context inheritance does not add a raw child task to
        ``_active_tasks``. On a caller-supplied loop, such a task can outlive
        SDK close. Final shutdown of an SDK-owned loop cancels remaining tasks,
        including untracked tasks. SDK code must use the bound scheduler when
        normal SDK shutdown tracking must include the child task. The bridge
        can also detect only explicit :class:`asyncio.Future` loop ownership.
        It cannot make an arbitrary loop-affine custom awaitable
        loop-independent.

        :param awaitable: Work to run.
        :param protect_task: Protect the current task from normal submission
            cancellation.
        :return: Result of ``awaitable``.
        """

        task = asyncio.current_task(self._loop)
        if task is not None:
            self._active_tasks.add(task)
            binding = _current_submission.get()
            submitted = (
                binding[1] if binding is not None and binding[0] is self else None
            )
            if submitted is not None:
                self._task_submissions[task] = submitted
            if protect_task:
                self._protected_tasks.add(task)
        scheduler_token = task_scheduler.set(self.submit_background)
        bridge_token = awaitable_bridge.set(self.bridge_awaitable)
        try:
            return await awaitable
        finally:
            awaitable_bridge.reset(bridge_token)
            task_scheduler.reset(scheduler_token)
            if task is not None:
                self._active_tasks.discard(task)
                self._protected_tasks.discard(task)
                self._protected_cancelling_tasks.discard(task)
                self._task_submissions.pop(task, None)
                self._task_cancellation_requested.discard(task)

    def bridge_awaitable(self, awaitable: Awaitable[T]) -> Awaitable[T]:
        """Bridge an asyncio future when another loop owns it.

        :param awaitable: Awaitable to examine.
        :return: The original awaitable or a cross-loop awaitable.
        """

        if (
            isinstance(awaitable, asyncio.Future)
            and awaitable.get_loop() is not self._loop
        ):
            return self.submit(awaitable)
        return awaitable

    def submit_background(
        self,
        awaitable: Awaitable[T],
    ) -> CrossLoopAwaitable[T]:
        """Submit and track background SDK work.

        :param awaitable: Background work to run.
        :return: Cross-loop awaitable for the result.
        """

        submitted = self.submit(awaitable)
        with self._background_lock:
            self._background.add(submitted)
        submitted._add_internal_done_callback(self._discard_background)
        return submitted

    def _discard_background(self, submitted: CrossLoopAwaitable[Any]) -> None:
        """Remove completed background work from tracking.

        :param submitted: Completed background submission.
        """

        with self._background_lock:
            self._background.discard(submitted)

    def run_sync(self, awaitable: Awaitable[T], timeout: float | None = None) -> T:
        """Run an awaitable and block the calling thread.

        :param awaitable: Work to run.
        :param timeout: Maximum wait time in seconds. Use ``None`` to wait
            without a time limit.
        :return: Result of ``awaitable``.
        :raises RuntimeError: If the caller runs on the SDK event loop.
        :raises TimeoutError: If the time limit expires.
        """

        if self.in_executor_thread():
            close_rejected_sync_awaitable(awaitable)
            raise RuntimeError("cannot synchronously wait from an SDK executor worker")
        try:
            current = asyncio.get_running_loop()
        except RuntimeError:
            current = None
        if current is self._loop:
            close_rejected_sync_awaitable(awaitable)
            raise RuntimeError("cannot synchronously wait on the SDK event loop")
        submitted = (
            awaitable
            if isinstance(awaitable, CrossLoopAwaitable)
            else self.submit(awaitable)
        )
        try:
            return cast(CrossLoopAwaitable[T], submitted)._result(timeout)
        except FutureTimeoutError as error:
            submitted_handle = cast(CrossLoopAwaitable[T], submitted)
            # Future.result() raises the same built-in TimeoutError both when
            # its wait expires and when completed work raised TimeoutError.
            # Completion can race the wait deadline, so terminal state alone
            # is insufficient. Only the identical stored exception proves
            # that the application raised the error we caught.
            if submitted_handle.done():
                try:
                    terminal_error = submitted_handle.exception(timeout=0)
                except FutureCancelledError:
                    terminal_error = None
                if terminal_error is error:
                    raise
            submitted_handle.cancel()
            raise TimeoutError("Awaitable timed out") from None

    def shutdown(self) -> None:
        """Stop this runtime and release owned resources.

        This method is safe to call more than once. Finalization stops and
        joins an owned loop thread. A call from that loop starts a daemon
        finalizer thread and returns before the join completes. The method
        does not stop a borrowed event loop.
        """

        with self._shutdown_lock:
            already_shutdown = self._shutdown
            if not already_shutdown:
                self._shutdown = True
            completion = self._shutdown_complete
            executor = self._executor
            should_wait = self._loop_thread is not current_thread() and (
                executor is None or not executor.owns_thread(current_thread())
            )
        if already_shutdown:
            if should_wait:
                completion.result()
            return
        with self._background_lock:
            background = list(self._background)
        for submitted in background:
            submitted.cancel()
        with self._submissions_lock:
            submissions = list(self._submissions)
        for submitted in submissions:
            submitted.cancel()
        if self._owned:
            if self._loop.is_running():
                try:
                    self._loop.call_soon_threadsafe(self._loop.stop)
                except RuntimeError:
                    # The loop may stop and close between ``is_running`` and
                    # the thread-safe callback. Resource finalization must
                    # still publish shutdown completion in that race.
                    pass
            loop_thread = self._loop_thread
            if loop_thread is current_thread():
                finalizer = Thread(
                    name="nebius-sdk-shutdown",
                    target=self._finish_owned_shutdown,
                    daemon=True,
                )
                try:
                    finalizer.start()
                except BaseException as error:
                    # Joining from the event-loop thread is impossible. Its
                    # normal ``run`` finalizer closes the loop. Still publish
                    # the executor's shutdown boundary so it rejects new work,
                    # cancels queued work, and lets running workers exit after
                    # their current call returns. Waiting here would deadlock
                    # if one of those calls depends on this loop.
                    self._record_shutdown_failure(error)
                    executor = self._executor
                    if executor is not None:
                        try:
                            executor.shutdown(wait=False, cancel_futures=True)
                        except BaseException as executor_error:
                            self._record_shutdown_failure(executor_error)
                    self._complete_shutdown()
                return
            self._finish_owned_shutdown()
            return
        self._complete_shutdown()

    def shutdown_async(self) -> CrossLoopAwaitable[None]:
        """Start runtime shutdown without blocking the caller.

        Each call returns an independent result handle. Cancelling one caller's
        handle does not cancel the runtime-wide shutdown completion used by
        later callers.

        :return: Cross-loop awaitable that completes after shutdown.
        """

        with self._shutdown_prepare_lock:
            schedule = not self._shutdown_preparing and not self._shutdown
            if schedule:
                self._shutdown_preparing = True
        if schedule:
            self.begin_close()
            if not self._loop.is_running():
                self._start_shutdown_thread()
            else:
                try:
                    self._loop.call_soon_threadsafe(
                        self._start_shutdown_preparation_on_loop
                    )
                except RuntimeError:
                    self._start_shutdown_thread()
                else:
                    if not self._owned:
                        self._start_borrowed_shutdown_watch()
        completion = Future[None]()

        def publish_shutdown(source: Future[None]) -> None:
            """Copy shutdown completion without accepting reverse cancellation."""

            if completion.cancelled():
                if not source.cancelled():
                    source.exception()
                return
            try:
                if source.cancelled():
                    completion.cancel()
                    return
                error = source.exception()
                if error is None:
                    completion.set_result(None)
                else:
                    completion.set_exception(error)
            except InvalidStateError:
                # Cancellation can win after the check above. The source
                # outcome has still been observed and remains authoritative
                # for other shutdown callers.
                if not source.cancelled():
                    source.exception()

        self._shutdown_complete.add_done_callback(publish_shutdown)
        return CrossLoopAwaitable._for_runtime(
            completion,
            self._loop,
        )

    def _start_borrowed_shutdown_watch(self) -> None:
        """Finish shutdown if a caller-owned loop stops after dispatch.

        A supplied loop remains caller-owned and must stay running until SDK
        close completes. It can nevertheless stop after accepting the
        preparation callback. A daemon monitor converts that otherwise
        permanent pending state into the same synchronous best-effort cleanup
        used when shutdown begins after the loop has already stopped. The
        monitor never stops or closes the supplied loop.
        """

        completed = ThreadEvent()
        self._shutdown_complete.add_done_callback(lambda _: completed.set())

        def watch() -> None:
            """Fall back once the borrowed loop can no longer make progress."""

            while not completed.wait(0.01):
                if self._loop.is_running():
                    continue
                with self._shutdown_prepare_lock:
                    self._shutdown_dispatch_abandoned = True
                self._start_shutdown_thread()
                return

        try:
            Thread(
                name="nebius-sdk-borrowed-shutdown-watch",
                target=watch,
                daemon=True,
            ).start()
        except RuntimeError:
            # Resource exhaustion must not turn a supplied-loop stop race into
            # an unfinishable close. Synchronous fallback is idempotent.
            with self._shutdown_prepare_lock:
                self._shutdown_dispatch_abandoned = True
            self._start_shutdown_thread()

    def _start_shutdown_preparation_on_loop(self) -> None:
        """Create graceful-shutdown work after dispatch reaches the loop.

        Deferring coroutine creation avoids retaining an unawaited coroutine
        when an accepted callback is left in the ready queue as the loop
        stops. An owned loop's thread finalizer detects that case and starts
        synchronous fallback shutdown.
        """

        with self._shutdown_prepare_lock:
            if self._shutdown_dispatch_abandoned:
                return
        preparation = self._prepare_shutdown()
        try:
            self._loop.create_task(preparation)
        except BaseException as error:
            dispose_unstarted_awaitable(preparation)
            with self._shutdown_prepare_lock:
                self._shutdown_dispatch_abandoned = True
            self._record_shutdown_failure(error)
            self._start_shutdown_thread()

    async def _prepare_shutdown(self) -> None:
        """Drain protected close callers and start final shutdown.

        A protected caller can run its immediate continuation after
        :meth:`nebius.aio.channel.Channel.close` returns. The runtime cancels
        the caller if that continuation waits again. The runtime does not
        cancel a caller that already received external cancellation.
        """

        try:
            while True:
                with self._submissions_lock:
                    waiting = [
                        submitted
                        for submitted in self._protected_submissions
                        if not submitted.done()
                        and submitted not in self._close_returning_submissions
                    ]
                if not waiting:
                    break
                # A protected external caller may remain active for an
                # arbitrary interval. Yield with a bounded delay instead of
                # continuously spinning the SDK loop while it finishes.
                await asyncio.sleep(0.001)

            # Let protected callers execute the immediate continuation after
            # ``await close()``. A caller that yields again is post-close work.
            await asyncio.sleep(0)
            protected_tasks = list(self._protected_tasks)
            for task in protected_tasks:
                submitted = self._task_submissions.get(task)
                cancelling = getattr(task, "cancelling", None)
                already_cancelling = (
                    task in self._protected_cancelling_tasks
                    or callable(cancelling)
                    and cancelling() > 0
                )
                if (
                    not task.done()
                    and not already_cancelling
                    and (submitted is None or not submitted.cancelled())
                ):
                    task.cancel()
            if protected_tasks:
                await asyncio.gather(
                    *protected_tasks,
                    return_exceptions=True,
                )

            # asyncio Task completion and run_coroutine_threadsafe result
            # publication are separate callbacks. Keep the loop alive until
            # each protected concurrent result is observably complete.
            while True:
                with self._submissions_lock:
                    protected = list(self._protected_submissions)
                if all(submitted.done() for submitted in protected):
                    break
                # Task completion and concurrent-future publication normally
                # differ by one loop turn. A short delay also bounds CPU use
                # if a non-standard future publishes more slowly.
                await asyncio.sleep(0.001)

            # Tracked tasks can have asynchronous finalizers that continue
            # after cancellation becomes visible on their concurrent result.
            # Drain those finalizers on borrowed as well as owned loops before
            # publishing runtime shutdown completion.
            await self.cancel_submissions()
            if self._owned:
                # Match asyncio.run ordering while this loop can still make
                # progress: cancel raw untracked tasks, close async generators,
                # then drain the default executor. A worker can use
                # run_coroutine_threadsafe and depend on this loop for its
                # final result.
                current = asyncio.current_task(self._loop)
                remaining_tasks = asyncio.all_tasks(self._loop) - (
                    {current} if current is not None else set()
                )
                for task in remaining_tasks:
                    task.cancel()
                if remaining_tasks:
                    await asyncio.gather(*remaining_tasks, return_exceptions=True)
                await self._loop.shutdown_asyncgens()
                await self._loop.shutdown_default_executor()
            self.shutdown()
        except BaseException as error:
            self._record_shutdown_failure(error)
            self._start_shutdown_thread()

    def _start_shutdown_thread(self) -> None:
        """Start a daemon thread that completes synchronous shutdown."""

        if self._shutdown_complete.done():
            return
        try:
            finalizer = Thread(
                name="nebius-sdk-async-shutdown",
                target=self.shutdown,
                daemon=True,
            )
            finalizer.start()
        except RuntimeError:
            self.shutdown()

    def _finish_owned_shutdown(self) -> None:
        """Join the owned loop thread and stop the owned executor."""

        try:
            loop_thread = self._loop_thread
            if loop_thread is not None and loop_thread is not current_thread():
                loop_thread.join()
            executor = self._executor
            if executor is not None:
                executor.shutdown(wait=True, cancel_futures=True)
        except BaseException as error:
            self._record_shutdown_failure(error)
        self._complete_shutdown()

    def _record_shutdown_failure(self, error: BaseException) -> None:
        """Retain and log the first graceful-shutdown failure.

        :param error: Failure raised while draining runtime resources.
        """

        with self._shutdown_lock:
            if self._shutdown_failure is not None:
                return
            self._shutdown_failure = error
        logger.error("SDK runtime shutdown failed", exc_info=error)

    def _complete_shutdown(self) -> None:
        """Publish the retained shutdown result exactly once."""

        with self._shutdown_lock:
            error = self._shutdown_failure
        try:
            if error is None:
                self._shutdown_complete.set_result(None)
            else:
                self._shutdown_complete.set_exception(error)
        except InvalidStateError:
            pass

    def call_with_context(
        self,
        callable_: Callable[..., T],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """Call a function with the SDK runtime context.

        The method temporarily binds the current execution context to this
        runtime. Code called by ``callable_`` can use the active task scheduler
        and awaitable bridge without a process-wide runtime variable. A
        task created during the call receives a copy of these bindings by
        default.

        The context tokens restore any previous bindings after the call.
        Retained bindings keep this runtime alive until the copied context is
        released. A raw child task is not automatically tracked for shutdown;
        the callback must use the active scheduler for tracked SDK work.
        Creating a bare coroutine does not retain the context. The coroutine
        uses the context of the task that eventually runs it.

        :param callable\\_: Function to call.
        :param args: Positional arguments for ``callable_``.
        :param kwargs: Keyword arguments for ``callable_``.
        :return: Result of ``callable_``.
        """

        scheduler_token = task_scheduler.set(self.submit_background)
        bridge_token = awaitable_bridge.set(self.bridge_awaitable)
        try:
            return callable_(*args, **kwargs)
        finally:
            awaitable_bridge.reset(bridge_token)
            task_scheduler.reset(scheduler_token)

    def _cancel_remaining_tasks(self) -> None:
        """Cancel and drain tasks before an owned loop closes."""

        pending = asyncio.all_tasks(self._loop)
        for task in pending:
            task.cancel()
        if pending:
            self._loop.run_until_complete(
                asyncio.gather(*pending, return_exceptions=True)
            )
        self._loop.run_until_complete(self._loop.shutdown_asyncgens())
