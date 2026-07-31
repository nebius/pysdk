"""Run SDK asynchronous work on one event loop.

The runtime can own an event loop or use a loop that the caller supplies. An
owned runtime also owns a daemon thread pool. The runtime converts submitted
work to awaitables that callers can use from other event loops.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Generator
from concurrent.futures import (
    Future,
    InvalidStateError,
    ThreadPoolExecutor,
)
from concurrent.futures import (
    TimeoutError as FutureTimeoutError,
)
from contextvars import ContextVar
from queue import Empty, Queue
from threading import Lock, Thread, current_thread
from types import TracebackType
from typing import Any, Generic, TypeVar, cast

from ._task_context import awaitable_bridge, task_scheduler

T = TypeVar("T")


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
        else:
            self.future.set_result(result)


class DaemonThreadPoolExecutor(ThreadPoolExecutor):
    """Run functions in a fixed set of daemon threads.

    :mod:`asyncio` requires a :class:`ThreadPoolExecutor` as its default
    executor. This class provides that interface and starts all worker threads
    as daemon threads. It starts the workers during initialization.
    """

    def __init__(
        self,
        max_workers: int,
        thread_name_prefix: str = "nebius-sdk",
    ) -> None:
        """Initialize the executor and start its worker threads.

        :param max_workers: Number of worker threads.
        :param thread_name_prefix: Prefix for each worker thread name.
        :raises ValueError: If ``max_workers`` is not positive.
        """

        if max_workers <= 0:
            raise ValueError("max_workers must be greater than 0")
        self._max_workers = max_workers
        self._thread_name_prefix = thread_name_prefix
        self._work_queue: Queue[_WorkItem | None] = Queue()  # type: ignore[assignment]
        self._shutdown = False
        self._shutdown_lock = Lock()
        self._threads: set[Thread] = set()
        for index in range(max_workers):
            thread = Thread(
                name=f"{thread_name_prefix}_{index}",
                target=self._worker,
                daemon=True,
            )
            self._threads.add(thread)
            thread.start()

    def _worker(self) -> None:
        """Run queued work until the queue contains a stop marker."""

        while True:
            work_item = self._work_queue.get()
            if work_item is None:
                return
            work_item.run()

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
    external loops. Synchronous callers can use :meth:`result`.

    All waiters share one concurrent future. Cancellation by one direct
    awaiter cancels that future and therefore affects every waiter. Use
    :func:`asyncio.shield` when cancellation of one waiter must not cancel the
    shared submission.
    """

    def __init__(
        self,
        future: Future[T],
        event_loop: asyncio.AbstractEventLoop,
    ) -> None:
        """Initialize a cross-loop awaitable.

        :param future: Concurrent future that stores the result.
        :param event_loop: Event loop for the associated SDK runtime. A
            bridged foreign future can still be owned by another loop.
        """

        self._future = future
        self._event_loop = event_loop

    @property
    def event_loop(self) -> asyncio.AbstractEventLoop:
        """Return the event loop for the associated SDK runtime."""

        return self._event_loop

    def cancel(self) -> bool:
        """Request cancellation of the submitted work.

        :return: ``True`` if the future accepted the cancellation request.
        """

        return self._future.cancel()

    def cancelled(self) -> bool:
        """Return whether the submitted work was cancelled."""

        return self._future.cancelled()

    def done(self) -> bool:
        """Return whether the submitted work is complete."""

        return self._future.done()

    def result(self, timeout: float | None = None) -> T:
        """Wait for and return the submitted work result.

        :param timeout: Maximum wait time in seconds. Use ``None`` to wait
            without a time limit.
        :return: Result of the submitted work.
        :raises concurrent.futures.TimeoutError: If the time limit expires.
        """

        return self._future.result(timeout)

    def exception(self, timeout: float | None = None) -> BaseException | None:
        """Wait for and return the submitted work exception.

        :param timeout: Maximum wait time in seconds. Use ``None`` to wait
            without a time limit.
        :return: Exception from the submitted work, or ``None`` if it
            completed successfully.
        :raises concurrent.futures.TimeoutError: If the time limit expires.
        """

        return self._future.exception(timeout)

    def add_done_callback(
        self,
        callback: Callable[[CrossLoopAwaitable[T]], object],
    ) -> None:
        """Add a function to call when the submitted work is complete.

        The concurrent future controls the callback thread. It calls the
        callback on the completion thread. If the future is already complete,
        it calls the callback immediately on the registering thread. The
        method does not dispatch the callback to an awaiter's event loop.

        :param callback: Function that receives this awaitable.
        """

        self._future.add_done_callback(lambda _: callback(self))

    async def _wait(self) -> T:
        """Wait for the concurrent future from the current event loop."""

        return await asyncio.wrap_future(self._future)

    def __await__(self) -> Generator[Any, None, T]:
        """Return an iterator that waits for the submitted work."""

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
        self._loop = event_loop or asyncio.new_event_loop()
        self._executor = (
            DaemonThreadPoolExecutor(
                executor_max_workers,
                "nebius-sdk-worker",
            )
            if self._owned
            else None
        )
        self._loop_thread: Thread | None = None
        self._shutdown_lock = Lock()
        self._accepting = True
        self._shutdown = False
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
        self._current_submission: ContextVar[CrossLoopAwaitable[Any] | None] = (
            ContextVar(
                f"nebius_sdk_submission_{id(self)}",
                default=None,
            )
        )
        if self._owned:
            started = Future[None]()

            def run() -> None:
                """Run and close the owned event loop."""

                asyncio.set_event_loop(self._loop)
                executor = self._executor
                if executor is None:
                    raise RuntimeError("owned SDK runtime has no executor")
                self._loop.set_default_executor(executor)
                started.set_result(None)
                try:
                    self._loop.run_forever()
                finally:
                    self._cancel_remaining_tasks()
                    self._loop.close()

            self._loop_thread = Thread(
                name="nebius-sdk-loop",
                target=run,
                daemon=True,
            )
            self._loop_thread.start()
            started.result()
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

        with self._shutdown_lock:
            if self._shutdown or not self._accepting:
                close = getattr(awaitable, "close", None)
                if callable(close):
                    close()
                raise RuntimeError("SDK runtime is closing or closed")
            if isinstance(awaitable, asyncio.Future):
                owner_loop = awaitable.get_loop()
                if owner_loop is not self._loop:
                    submitted = self._bridge_foreign_future(awaitable, owner_loop)
                else:
                    submitted = self._submit_to_loop(
                        awaitable,
                        protect_task=not track,
                    )
            else:
                submitted = self._submit_to_loop(
                    awaitable,
                    protect_task=not track,
                )
            if track:
                self._track_submission(submitted)
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
            token = self._current_submission.set(submitted)
            try:
                return await self._run_awaitable(
                    awaitable,
                    protect_task=protect_task,
                )
            finally:
                self._current_submission.reset(token)

        future = asyncio.run_coroutine_threadsafe(
            run(),
            self._loop,
        )
        submitted = CrossLoopAwaitable(future, self._loop)

        def close_unstarted(completed: Future[T]) -> None:
            """Close a coroutine that cancellation prevents from starting."""

            with start_lock:
                should_close = completed.cancelled() and not started
            if should_close:
                close = getattr(awaitable, "close", None)
                if callable(close):
                    close()

        future.add_done_callback(close_unstarted)
        holder.set_result(submitted)
        return submitted

    def _track_submission(self, submitted: CrossLoopAwaitable[Any]) -> None:
        """Track a submission until it is complete.

        :param submitted: Submission to track.
        """

        with self._submissions_lock:
            self._submissions.add(submitted)
        submitted.add_done_callback(self._discard_submission)

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

        submitted = self._current_submission.get()
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

        submitted = self._current_submission.get()
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
        return CrossLoopAwaitable(bridged, self._loop)

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
            submitted = self._current_submission.get()
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
        submitted.add_done_callback(self._discard_background)
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

        try:
            current = asyncio.get_running_loop()
        except RuntimeError:
            current = None
        if current is self._loop:
            close = getattr(awaitable, "close", None)
            if callable(close):
                close()
            raise RuntimeError("cannot synchronously wait on the SDK event loop")
        submitted = (
            awaitable
            if isinstance(awaitable, CrossLoopAwaitable)
            else self.submit(awaitable)
        )
        try:
            return cast(CrossLoopAwaitable[T], submitted).result(timeout)
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
            if self._shutdown:
                completion = self._shutdown_complete
                executor = self._executor
                if self._loop_thread is not current_thread() and (
                    executor is None or not executor.owns_thread(current_thread())
                ):
                    completion.result()
                return
            self._shutdown = True
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
        self._shutdown_complete.set_result(None)

    def shutdown_async(self) -> CrossLoopAwaitable[None]:
        """Start runtime shutdown without blocking the caller.

        :return: Cross-loop awaitable that completes after shutdown.
        """

        with self._shutdown_prepare_lock:
            schedule = not self._shutdown_preparing and not self._shutdown
            if schedule:
                self._shutdown_preparing = True
        if schedule:
            try:
                asyncio.run_coroutine_threadsafe(
                    self._prepare_shutdown(),
                    self._loop,
                )
            except RuntimeError:
                self._start_shutdown_thread()
        return CrossLoopAwaitable(self._shutdown_complete, self._loop)

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
            self.shutdown()
        except BaseException:
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

        loop_thread = self._loop_thread
        if loop_thread is not None and loop_thread is not current_thread():
            loop_thread.join()
        executor = self._executor
        if executor is not None:
            executor.shutdown(wait=True, cancel_futures=True)
        try:
            self._shutdown_complete.set_result(None)
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
