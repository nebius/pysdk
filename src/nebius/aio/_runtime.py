"""Private event-loop runtime used by the SDK."""

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
    def __init__(
        self,
        future: Future[Any],
        fn: Callable[..., Any],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> None:
        self.future = future
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    def run(self) -> None:
        if not self.future.set_running_or_notify_cancel():
            return
        try:
            result = self.fn(*self.args, **self.kwargs)
        except BaseException as error:
            self.future.set_exception(error)
        else:
            self.future.set_result(result)


class DaemonThreadPoolExecutor(ThreadPoolExecutor):
    """Small ``ThreadPoolExecutor``-compatible pool with daemon workers.

    ``asyncio`` requires its default executor to be a
    :class:`ThreadPoolExecutor`. The standard implementation deliberately uses
    non-daemon workers, so the SDK supplies the same public executor contract
    with an independent, eagerly started daemon worker set.
    """

    def __init__(
        self,
        max_workers: int,
        thread_name_prefix: str = "nebius-sdk",
    ) -> None:
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
        return self

    def owns_thread(self, thread: Thread) -> bool:
        return thread in self._threads

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.shutdown(wait=True)


class CrossLoopAwaitable(Generic[T]):
    """Await a concurrent future from any asyncio event loop."""

    def __init__(
        self,
        future: Future[T],
        event_loop: asyncio.AbstractEventLoop,
    ) -> None:
        self._future = future
        self._event_loop = event_loop

    @property
    def event_loop(self) -> asyncio.AbstractEventLoop:
        return self._event_loop

    def cancel(self) -> bool:
        return self._future.cancel()

    def cancelled(self) -> bool:
        return self._future.cancelled()

    def done(self) -> bool:
        return self._future.done()

    def result(self, timeout: float | None = None) -> T:
        return self._future.result(timeout)

    def exception(self, timeout: float | None = None) -> BaseException | None:
        return self._future.exception(timeout)

    def add_done_callback(
        self,
        callback: Callable[[CrossLoopAwaitable[T]], object],
    ) -> None:
        self._future.add_done_callback(lambda _: callback(self))

    async def _wait(self) -> T:
        return await asyncio.wrap_future(self._future)

    def __await__(self) -> Generator[Any, None, T]:
        return self._wait().__await__()


class AsyncRuntime:
    """Own or attach to the single event loop used by an SDK instance."""

    def __init__(
        self,
        event_loop: asyncio.AbstractEventLoop | None,
        executor_max_workers: int,
    ) -> None:
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
        return self._loop

    @property
    def owned(self) -> bool:
        return self._owned

    def in_event_loop(self) -> bool:
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
        holder: Future[CrossLoopAwaitable[T]] = Future()
        start_lock = Lock()
        started = False

        async def run() -> T:
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
        with self._submissions_lock:
            self._submissions.add(submitted)
        submitted.add_done_callback(self._discard_submission)

    def _discard_submission(self, submitted: CrossLoopAwaitable[Any]) -> None:
        with self._submissions_lock:
            self._submissions.discard(submitted)
            self._protected_submissions.discard(submitted)
            self._close_returning_submissions.discard(submitted)

    def protect_current_submission(self) -> CrossLoopAwaitable[Any] | None:
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
        submitted = self._current_submission.get()
        if submitted is not None:
            with self._submissions_lock:
                if submitted in self._protected_submissions:
                    self._close_returning_submissions.add(submitted)

    def begin_close(self) -> None:
        with self._shutdown_lock:
            self._accepting = False

    async def cancel_submissions(self) -> None:
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
        bridged: Future[T] = Future()

        def copy_result(completed: asyncio.Future[T]) -> None:
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
        submitted = self.submit(awaitable)
        with self._background_lock:
            self._background.add(submitted)
        submitted.add_done_callback(self._discard_background)
        return submitted

    def _discard_background(self, submitted: CrossLoopAwaitable[Any]) -> None:
        with self._background_lock:
            self._background.discard(submitted)

    def run_sync(self, awaitable: Awaitable[T], timeout: float | None = None) -> T:
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
        """Quiesce protected close callers, then tear down without blocking."""

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
        scheduler_token = task_scheduler.set(self.submit_background)
        bridge_token = awaitable_bridge.set(self.bridge_awaitable)
        try:
            return callable_(*args, **kwargs)
        finally:
            awaitable_bridge.reset(bridge_token)
            task_scheduler.reset(scheduler_token)

    def _cancel_remaining_tasks(self) -> None:
        pending = asyncio.all_tasks(self._loop)
        for task in pending:
            task.cancel()
        if pending:
            self._loop.run_until_complete(
                asyncio.gather(*pending, return_exceptions=True)
            )
        self._loop.run_until_complete(self._loop.shutdown_asyncgens())
