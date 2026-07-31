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
import weakref
from collections.abc import Awaitable, Callable, Generator
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
from threading import Lock, Thread, current_thread
from types import TracebackType
from typing import Any, Generic, TypeVar, cast

from ._task_context import (
    awaitable_bridge,
    dispose_unstarted_awaitable,
    task_scheduler,
)

T = TypeVar("T")
logger = getLogger(__name__)

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

        while True:
            work_item = self._work_queue.get()
            if work_item is None:
                return
            work_item.run()
            del work_item

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
            if len(self._threads) < self._max_workers:
                thread = Thread(
                    name=f"{self._thread_name_prefix}_{len(self._threads)}",
                    target=self._worker,
                    daemon=True,
                )
                thread.start()
                self._threads.add(thread)
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

    A public completion callback uses the event loop that registers it. The
    loop must stay open until delivery. The SDK does not move the callback to
    its completion thread if the registration loop closes.
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
        self._executor: weakref.ReferenceType[DaemonThreadPoolExecutor] | None = None

    @classmethod
    def _for_runtime(
        cls,
        future: Future[T],
        event_loop: asyncio.AbstractEventLoop,
        executor: DaemonThreadPoolExecutor | None,
    ) -> CrossLoopAwaitable[T]:
        """Create a handle that can detect waits from its owned executor."""

        ret = cls(future, event_loop)
        if executor is not None:
            ret._executor = weakref.ref(executor)
        return ret

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
        """Reject a pending wait from a worker in the owned finite pool."""

        if self._future.done() or self._executor is None:
            return
        executor = self._executor()
        if executor is not None and executor.owns_thread(current_thread()):
            raise RuntimeError(
                "cannot wait for pending SDK work from its executor worker"
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
        registration loop must stay open until callback delivery. If it closes
        later, the SDK logs a warning and drops the callback instead of running
        loop-affine code on another thread.

        :param callback: Function that receives this awaitable.
        :param context: Optional context in which to run ``callback``.
        :raises RuntimeError: If the callback loop is already closed.
        """

        self._check_process()
        try:
            callback_loop = asyncio.get_running_loop()
        except RuntimeError:
            callback_loop = self._event_loop
        if callback_loop.is_closed():
            raise RuntimeError("callback event loop is closed")
        callback_context = copy_context() if context is None else context

        def schedule(_: Future[T]) -> None:
            """Schedule the public callback on its registration loop."""

            try:
                callback_loop.call_soon_threadsafe(
                    callback,
                    self,
                    context=callback_context,
                )
            except RuntimeError:
                # Affinity cannot be preserved after a caller-owned loop
                # closes. Do not run loop-affine user code on the completion
                # thread.
                logger.warning(
                    "SDK completion callback was not run because its "
                    "registration loop is closed"
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

        self._future.add_done_callback(lambda _: callback(self))

    async def _wait(self) -> T:
        """Wait for the concurrent future from the current event loop."""

        self._check_process()
        binding = _current_submission.get()
        if binding is not None and binding[1] is self:
            raise RuntimeError("SDK work cannot await its own submission handle")
        self._reject_executor_wait()
        return await asyncio.wrap_future(self._future)

    def __await__(self) -> Generator[Any, None, T]:
        """Return an iterator that waits for the submitted work."""

        self._check_process()
        return self._wait().__await__()


class AsyncRuntime:
    """Run all asynchronous work for one SDK instance.

    An owned runtime starts one daemon event-loop thread and an independent
    daemon executor. A borrowed runtime uses an event loop that the caller
    supplies. Shutdown does not stop a borrowed loop.
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
        self._background_lock = Lock()
        self._background: set[CrossLoopAwaitable[Any]] = set()
        self._submissions_lock = Lock()
        self._submissions: set[CrossLoopAwaitable[Any]] = set()
        self._protected_submissions: set[CrossLoopAwaitable[Any]] = set()
        self._close_returning_submissions: set[CrossLoopAwaitable[Any]] = set()
        self._active_tasks: set[asyncio.Task[Any]] = set()
        self._protected_tasks: set[asyncio.Task[Any]] = set()
        self._task_submissions: dict[
            asyncio.Task[Any],
            CrossLoopAwaitable[Any],
        ] = {}
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
                started.set_result(None)
                try:
                    self._loop.run_forever()
                finally:
                    try:
                        self._cancel_remaining_tasks()
                    except BaseException as error:
                        self._record_shutdown_failure(error)
                    finally:
                        try:
                            self._loop.close()
                        except BaseException as error:
                            self._record_shutdown_failure(error)

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
        """Return whether the caller is an owned executor worker."""

        executor = self._executor
        return executor is not None and executor.owns_thread(current_thread())

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
            dispose_unstarted_awaitable(awaitable)
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

        holder: Future[CrossLoopAwaitable[T]] = Future()
        start_lock = Lock()
        started = False

        async def run() -> T:
            """Run the awaitable with its submission context."""

            nonlocal started
            submitted = await asyncio.wrap_future(holder)
            with start_lock:
                started = True
            token = _current_submission.set((self, submitted))
            try:
                return await self._run_awaitable(
                    awaitable,
                    protect_task=protect_task,
                )
            finally:
                _current_submission.reset(token)

        runner = run()
        try:
            future = asyncio.run_coroutine_threadsafe(runner, self._loop)
        except BaseException:
            runner.close()
            dispose_unstarted_awaitable(awaitable)
            raise
        submitted = CrossLoopAwaitable._for_runtime(
            future,
            self._loop,
            self._executor,
        )

        def close_unstarted(completed: Future[T]) -> None:
            """Close a coroutine that cancellation prevents from starting."""

            with start_lock:
                should_close = completed.cancelled() and not started
            if should_close:
                dispose_unstarted_awaitable(awaitable)

        future.add_done_callback(close_unstarted)
        holder.set_result(submitted)
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
                self._protected_tasks.add(task)
        return submitted

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

    async def cancel_submissions(self) -> None:
        """Cancel tracked work once and wait for task finalizers.

        This method does not cancel protected internal close callers. It first
        cancels active asyncio tasks. It then cancels submissions that did not
        start. This order prevents a second cancellation from interrupting an
        asynchronous finalizer.
        """

        current = asyncio.current_task(self._loop)
        tasks = list(
            self._active_tasks
            - self._protected_tasks
            - ({current} if current is not None else set())
        )
        for task in tasks:
            submitted = self._task_submissions.get(task)
            if submitted is None or not submitted.cancelled():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        # Task cancellation propagates to its concurrent Future. Let those
        # callbacks publish before cancelling submissions that never started;
        # cancelling both representations can inject a second CancelledError
        # into an async finalizer.
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
        the bridge is sent to the source loop.

        :param source: Future to bridge.
        :param owner_loop: Event loop that owns ``source``.
        :return: Cross-loop awaitable for the source result.
        """

        bridged: Future[T] = Future()

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

            if completed.cancelled() and not source.done():
                try:
                    owner_loop.call_soon_threadsafe(source.cancel)
                except RuntimeError:
                    pass

        bridged.add_done_callback(forward_cancellation)
        if source.done():
            copy_result(source)
        else:
            try:
                owner_loop.call_soon_threadsafe(source.add_done_callback, copy_result)
            except RuntimeError as error:
                bridged.set_exception(error)
        return CrossLoopAwaitable._for_runtime(
            bridged,
            self._loop,
            self._executor,
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
                self._task_submissions.pop(task, None)

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
            dispose_unstarted_awaitable(awaitable)
            raise RuntimeError("cannot synchronously wait from an SDK executor worker")
        try:
            current = asyncio.get_running_loop()
        except RuntimeError:
            current = None
        if current is self._loop:
            dispose_unstarted_awaitable(awaitable)
            raise RuntimeError("cannot synchronously wait on the SDK event loop")
        submitted = (
            awaitable
            if isinstance(awaitable, CrossLoopAwaitable)
            else self.submit(awaitable)
        )
        try:
            return cast(CrossLoopAwaitable[T], submitted)._result(timeout)
        except FutureTimeoutError:
            cast(CrossLoopAwaitable[T], submitted).cancel()
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
            self._loop.call_soon_threadsafe(self._loop.stop)
            loop_thread = self._loop_thread
            if loop_thread is current_thread():
                finalizer = Thread(
                    name="nebius-sdk-shutdown",
                    target=self._finish_owned_shutdown,
                    daemon=True,
                )
                finalizer.start()
                return
            self._finish_owned_shutdown()
            return
        self._complete_shutdown()

    def shutdown_async(self) -> CrossLoopAwaitable[None]:
        """Start runtime shutdown without blocking the caller.

        :return: Cross-loop awaitable that completes after shutdown.
        """

        with self._shutdown_prepare_lock:
            schedule = not self._shutdown_preparing and not self._shutdown
            if schedule:
                self._shutdown_preparing = True
        if schedule:
            if not self._loop.is_running():
                self._start_shutdown_thread()
            else:
                runner = self._prepare_shutdown()
                try:
                    asyncio.run_coroutine_threadsafe(runner, self._loop)
                except RuntimeError:
                    runner.close()
                    self._start_shutdown_thread()
        return CrossLoopAwaitable._for_runtime(
            self._shutdown_complete,
            self._loop,
            self._executor,
        )

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
                await asyncio.sleep(0)

            # Let protected callers execute the immediate continuation after
            # ``await close()``. A caller that yields again is post-close work.
            await asyncio.sleep(0)
            protected_tasks = list(self._protected_tasks)
            for task in protected_tasks:
                submitted = self._task_submissions.get(task)
                if not task.done() and (submitted is None or not submitted.cancelled()):
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
                await asyncio.sleep(0)
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
