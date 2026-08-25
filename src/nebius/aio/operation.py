"""Helpers for working with long-running operations.

The :class:`Operation` wrapper normalizes different service-operation
versions. Its methods poll, wait synchronously, and inspect operation metadata.

The wrapper accepts current v1 and older v1alpha1 operation messages. It
routes calls to the applicable operation-service client.
"""

from __future__ import annotations

import importlib
import os
from asyncio import FIRST_COMPLETED, CancelledError, ensure_future, gather, shield, sleep, wait, wait_for, wrap_future
from asyncio import Lock as AsyncLock
from asyncio import TimeoutError as AsyncTimeoutError
from collections.abc import Sequence
from concurrent.futures import Future as ConcurrentFuture
from datetime import datetime, timedelta
from math import isfinite
from threading import Lock
from time import monotonic
from typing import TYPE_CHECKING, Any, Generic, Protocol, TypeVar, cast

from grpc import StatusCode
from typing_extensions import Unpack

from ..base.error import SDKError
from ..base.metadata import Metadata
from ..base.protos.unset import Unset, UnsetType
from ..base.protos.well_known_direct import local_timezone
from ._task_context import dispose_unstarted_awaitable
from .abc import ClientChannelInterface
from .constant_channel import Constant
from .request import DEFAULT_AUTH_TIMEOUT, DEFAULT_TIMEOUT, _authorization_deadline_applies, _validate_timeout
from .request_kwargs import RequestKwargs, RequestKwargsForOperation
from .request_status import RequestStatus
from .route import Route

if TYPE_CHECKING:
    from ..api.nebius.common.v1 import ProgressTracker


class OperationMessage(Protocol):
    """Structural fields shared by current and alpha direct operations."""

    id: str
    description: str
    created_at: datetime | None
    created_by: str
    finished_at: datetime | None
    resource_id: str
    status: RequestStatus | None


OperationPb = TypeVar("OperationPb", bound=OperationMessage)
"""
A convenience wrapper around operation protobufs.
Either :class:`nebius.api.nebius.common.v1.Operation` or
:class:`nebius.api.nebius.common.v1alpha1.Operation`, or their protobuf classes.
"""
T = TypeVar("T")


class CurrentStep:
    """Describe one step in an operation progress tracker.

    This class wraps a ``ProgressTracker.Step`` instance. Its methods return
    ``None`` for missing fields.

    When a step includes work estimates (``work_done``), the
    :meth:`work_fraction` helper converts them into a usable fraction.
    The method returns ``None`` when the fraction cannot be computed.

    Example
    -------
    Inspecting steps and progress::

        tracker = operation.progress_tracker()
        if tracker:
            for step in tracker.steps():
                fraction = step.work_fraction()
                if fraction is None:
                    print(step.description())
                else:
                    print(f"{step.description()}: {fraction:.0%}")

    """

    def __init__(self, step: object) -> None:
        self._step = step

    def description(self) -> str:
        """Return a human-readable description of the step."""
        return getattr(self._step, "description", "")

    def started_at(self) -> datetime | None:
        """Return the step start timestamp or ``None`` if unknown."""
        return _get_timestamp(self._step, "started_at")

    def finished_at(self) -> datetime | None:
        """Return the step finished timestamp or ``None`` if unfinished."""
        return _get_timestamp(self._step, "finished_at")

    def work_done(self) -> ProgressTracker.WorkDone | None:
        """Return work progress details for the step when available."""
        return _get_work_done(self._step)

    def work_fraction(self) -> float | None:
        """Return the completed work fraction or ``None`` when unavailable."""
        work_done = self.work_done()
        if work_done is None:
            return None
        total = getattr(work_done, "total_tick_count", 0)
        if total <= 0:
            return None
        done = getattr(work_done, "done_tick_count", 0)
        return float(done) / float(total)

    def __repr__(self) -> str:
        parts = [f"{self.description()}"]
        started = self.started_at()
        if started is not None:
            parts.append(f"started_at: {started}")
        finished = self.finished_at()
        if finished is not None:
            parts.append(f"finished_at: {finished}")
        work = self.work_done()
        if work is not None and work.total_tick_count:
            parts.append(f"work_done: {work.done_tick_count}/{work.total_tick_count}")
        return "CurrentStep(" + ", ".join(parts) + ")"


class OperationProgressTracker(Protocol):
    """Define operation-level progress tracking.

    This protocol mirrors the server-side ``ProgressTracker`` object. It adds
    methods for time and work fractions.

    The tracker is only available for v1 operations that include a
    ``progress_tracker`` field. For v1alpha1 operations,
    :meth:`Operation.progress_tracker` returns ``None``.

    Example
    -------
    Reading overall progress::

        tracker = operation.progress_tracker()
        if tracker:
            print(tracker.description())
            work_fraction = tracker.work_fraction()
            if work_fraction is not None:
                print(f"Work: {work_fraction:.0%}")
            time_fraction = tracker.time_fraction()
            if time_fraction is not None:
                print(f"Time: {time_fraction:.0%}")

    """

    def description(self) -> str:
        """Return a human-readable description of the tracker."""
        ...

    def started_at(self) -> datetime | None:
        """Return the tracker start timestamp or ``None`` if unknown."""
        ...

    def finished_at(self) -> datetime | None:
        """Return the tracker finished timestamp or ``None`` if unfinished."""
        ...

    def work_done(self) -> ProgressTracker.WorkDone | None:
        """Return work progress details for the tracker when available."""
        ...

    def work_fraction(self) -> float | None:
        """Return the completed work fraction or ``None`` when unavailable."""
        ...

    def estimated_finished_at(self) -> datetime | None:
        """Return the estimated completion timestamp when available."""
        ...

    def time_fraction(self) -> float | None:
        """Return elapsed time fraction or ``None`` when unavailable."""
        ...

    def steps(self) -> Sequence[CurrentStep]:
        """Return steps reported by the progress tracker."""
        ...


class Operation(Generic[OperationPb]):
    """Wrap an operation message.

    The :class:`Operation` wrapper normalizes
    :class:`nebius.api.nebius.common.v1.Operation`
    and :class:`nebius.api.nebius.common.v1alpha1.Operation` representations.
    Its methods:

    - inspect operation metadata (id, resource_id, timestamps),
    - poll/update the operation state via the corresponding operation
      service, and
    - wait for completion either asynchronously or synchronously.

    The wrapper stores an operation-service client. A
    :class:`nebius.aio.constant_channel.Constant` points this client at
    ``source_method``. The client reuses ``channel`` for network and
    authorization functions.

    Built-in channels schedule polling on the SDK loop, so this wrapper can be
    used from unrelated caller loops. A legacy custom channel without
    ``run_async`` keeps the historical local-awaitable fallback. Its update
    lock becomes bound to the first caller loop that contends for it, and the
    same wrapper must not then be used concurrently from another loop.

    :param source_method: the originating ``service.method`` name used to build a
        constant channel for operation management calls
    :param channel: channel used for network and auth operations
    :type channel: :class:`ClientChannelInterface`
    :param operation: an operation protobuf instance (v1 or v1alpha1)
    :type operation: either :class:`nebius.api.nebius.common.v1.Operation` or
        :class:`nebius.api.nebius.common.v1alpha1.Operation`, or their protobuf
        classes.

    Example
    -------
    Operation from a service action (e.g., creating a bucket)::

        from nebius.sdk import SDK
        from nebius.aio.cli_config import Config
        from nebius.api.nebius.storage.v1 import (
            BucketServiceClient,
            CreateBucketRequest
        )

        sdk = SDK(
            config_reader=Config(),
            user_agent_prefix="example-application/1.0",
        )
        service = BucketServiceClient(sdk)

        # Create operation from service action
        operation = await service.create(CreateBucketRequest(
            # fill-in necessary fields
        ))

        # Wait for completion
        await operation.wait()
        print(f"New bucket ID: {operation.resource_id}")

    Operation from list of operations::

        from nebius.sdk import SDK
        from nebius.aio.cli_config import Config
        from nebius.api.nebius.storage.v1 import BucketServiceClient
        from nebius.api.nebius.common.v1 import ListOperationsRequest

        sdk = SDK(
            config_reader=Config(),
            user_agent_prefix="example-application/1.0",
        )
        service = BucketServiceClient(sdk)

        # Get operation service client from the bucket service
        operation_service = service.operation_service()
        operations_response = await operation_service.list(ListOperationsRequest(
            # fill-in necessary fields
        ))

        # Get first operation from list
        if operations_response.operations:
            operation = operations_response.operations[0]

            # Manual update
            await operation.update()
            print(f"Operation status: {operation.status()}")

    """

    def __init__(
        self,
        source_method: str | Route,
        channel: ClientChannelInterface,
        operation: OperationPb,
    ) -> None:
        """Create an operation wrapper from the operation protobuf."""
        self._channel = channel
        operation_type = type(operation)
        full_name = getattr(operation_type, "__PROTO_FULL_NAME__", None)
        if full_name not in {
            "nebius.common.v1.Operation",
            "nebius.common.v1alpha1.Operation",
        }:
            raise SDKError(f"Operation type {operation_type} not supported.")
        registry = getattr(operation_type, "__REGISTRY__", None)
        if registry is None:
            raise SDKError("Operation type has no direct-message registry.")
        package = full_name.rsplit(".", 1)[0]
        get_type = registry.message_class(f"{package}.GetOperationRequest")
        module = importlib.import_module(operation_type.__module__)
        service_type = getattr(module, "OperationServiceClient", None)
        if service_type is None:
            raise SDKError(f"Operation service for {full_name} is not generated.")
        self._service = service_type(Constant(source_method, channel))
        self._get_request_obj = get_type
        self._operation = operation
        self._state_lock = Lock()
        self._update_lock = AsyncLock()
        self._process_id = os.getpid()

    def _check_process(self) -> None:
        """Reject an operation inherited across ``fork`` before locking."""
        if os.getpid() != self._process_id:
            raise RuntimeError(
                "You cannot use an SDK operation after a fork. Create SDK objects after the child process starts.",
            )

    def _operation_snapshot(self) -> OperationPb:
        """Return the current operation message under the state lock."""
        self._check_process()
        with self._state_lock:
            return self._operation

    def __repr__(self) -> str:
        """Return a compact string representation useful for debugging."""
        parts = [
            f"{self.id}",
            f"resource_id: {self.resource_id}",
            f"status: {self.status()}",
        ]
        tracker = self.progress_tracker()
        if tracker is not None:
            work = tracker.work_done()
            if work is not None and work.total_tick_count:
                parts.append(f"work_done: {work.done_tick_count}/{work.total_tick_count}")
            eta = tracker.estimated_finished_at()
            if eta is not None:
                parts.append(f"eta: {eta}")
        return "Operation(" + ", ".join(parts) + ")"

    def status(self) -> RequestStatus | None:
        """Return the operation's current status object or ``None``.

        :rtype: :class:`RequestStatus` or nothing
        """
        return self._operation_snapshot().status

    def progress_tracker(self) -> OperationProgressTracker | None:
        """Return an operation progress tracker when available.

        Return ``None`` if the operation has no progress tracker. For example,
        v1alpha1 operations do not have one.

        Example
        -------
        Polling with a single-line progress display::

            from asyncio import sleep
            from datetime import datetime
            from nebius.base.protos.well_known import local_timezone

            while not operation.done():
                await operation.update()
                tracker = operation.progress_tracker()
                parts = [f"waiting for operation {operation.id} to complete:"]

                if tracker:
                    work = tracker.work_fraction()
                    if work is not None:
                        parts.append(f"{work:.0%}")

                    desc = tracker.description()
                    if desc:
                        parts.append(desc)

                    started = tracker.started_at()
                    if started is not None:
                        elapsed = datetime.now(local_timezone) - started
                        parts.append(f"{elapsed}")

                    eta = tracker.estimated_finished_at()
                    if eta is not None:
                        parts.append(f"eta {eta}")

                print(" ".join(parts), end="\\r", flush=True)
                await sleep(1)

            print()

        """
        return wrap_progress_tracker(self)

    def done(self) -> bool:
        """Return True when the operation has reached a terminal state."""
        return self.status() is not None

    async def update(
        self,
        **kwargs: Unpack[RequestKwargs],
    ) -> None:
        """Fetch the latest operation data from the operation service.

        This coroutine performs a single get operation using the internal
        operation service client and replaces the wrapped operation object
        with the returned value.

        :param kwargs: additional request keyword arguments
            see :class:`nebius.aio.request_kwargs.RequestKwargs` for details.
        :raises ValueError: If ``timeout`` or ``auth_timeout`` is NaN or
            infinite. Use ``None`` for an unlimited timeout.
        """
        self._check_process()
        await self._update_from_submission(monotonic(), **kwargs)

    async def _update_from_submission(
        self,
        submitted_at: float,
        **kwargs: Unpack[RequestKwargs],
    ) -> None:
        """Submit one update with a caller-captured monotonic start time.

        :param submitted_at: Monotonic time when the caller submitted the
            update. Request and authorization deadlines include all later
            dispatch delay.
        :param kwargs: Additional request options for the operation service.
        """
        if self.done():
            return
        metadata = kwargs.get("metadata")
        if metadata is not None:
            kwargs["metadata"] = Metadata(metadata)
        auth_options = kwargs.get("auth_options")
        if auth_options is not None:
            kwargs["auth_options"] = dict(auth_options)
        timeout_option = kwargs.get("timeout", Unset)
        timeout = DEFAULT_TIMEOUT if isinstance(timeout_option, UnsetType) else timeout_option
        auth_timeout_option = kwargs.get("auth_timeout", Unset)
        auth_timeout = DEFAULT_AUTH_TIMEOUT if isinstance(auth_timeout_option, UnsetType) else auth_timeout_option
        _validate_timeout(timeout, "timeout")
        _validate_timeout(auth_timeout, "auth_timeout")
        authorization_applies = _authorization_deadline_applies(
            self._channel,
            cast(dict[str, str], kwargs.get("auth_options") or {}),
        )
        request_deadline = None if timeout is None else submitted_at + max(timeout, 0)
        authorization_deadline = (
            None if auth_timeout is None or authorization_applies is not True else submitted_at + max(auth_timeout, 0)
        )
        submit = getattr(self._channel, "run_async", None)
        dispatch_started: ConcurrentFuture[None] = ConcurrentFuture()
        dispatch_state_lock = Lock()
        update_started = False
        update_work = self._update_internal(
            request_deadline=request_deadline,
            authorization_deadline=authorization_deadline,
            **kwargs,
        )

        async def start_update() -> None:
            """Publish SDK-loop dispatch before the update starts."""
            nonlocal update_started
            with dispatch_state_lock:
                update_started = True
            if not dispatch_started.done():
                dispatch_started.set_result(None)
            await update_work

        update = start_update()
        try:
            submitted = submit(update) if callable(submit) else update
        except BaseException:
            dispose_unstarted_awaitable(update)
            dispose_unstarted_awaitable(update_work)
            raise

        def dispose_update_if_unstarted(_: object) -> None:
            """Dispose update work if its dispatch wrapper did not start."""
            with dispatch_state_lock:
                if update_started:
                    return
            dispose_unstarted_awaitable(update_work)

        observe = getattr(submitted, "_add_internal_done_callback", None)
        if not callable(observe):
            observe = getattr(submitted, "add_done_callback", None)
        if callable(observe):
            observe(dispose_update_if_unstarted)
        # Authorization and request clocks are independent. An applicable
        # authorization deadline bounds the whole flow; the generated request
        # pauses its request clock while authenticating. For a legacy channel
        # whose provider is only discoverable on its owner loop, avoid an
        # incorrect caller-side deadline and let its request state machine
        # enforce both limits.
        caller_deadline = (
            authorization_deadline
            if authorization_applies is True
            else request_deadline
            if authorization_applies is False
            else None
        )
        done = getattr(submitted, "done", None)
        dispatch_limits = [deadline for deadline in (request_deadline, authorization_deadline) if deadline is not None]
        dispatch_deadline = min(dispatch_limits) if authorization_applies is True else None
        if (caller_deadline is None and dispatch_deadline is None) or (callable(done) and done()):
            await submitted
            return
        waiter = ensure_future(submitted)
        try:
            if dispatch_deadline is not None and not dispatch_started.done():
                remaining = dispatch_deadline - monotonic()
                if remaining > 0:
                    started_waiter = ensure_future(shield(wrap_future(dispatch_started)))
                    try:
                        completed, _ = await wait(
                            (waiter, started_waiter),
                            timeout=remaining,
                            return_when=FIRST_COMPLETED,
                        )
                    finally:
                        started_waiter.cancel()
                        await gather(started_waiter, return_exceptions=True)
                    if waiter in completed:
                        await waiter
                        return
                if not dispatch_started.done():
                    waiter.cancel()
                    cancel = getattr(submitted, "cancel", None)
                    if callable(cancel):
                        cancel()
                    raise TimeoutError("The operation update timed out before SDK-loop dispatch.")
            if caller_deadline is None:
                await waiter
                return
            remaining = caller_deadline - monotonic()
            if remaining <= 0:
                cancel = getattr(submitted, "cancel", None)
                if callable(cancel):
                    cancel()
                raise TimeoutError("The operation update timed out.")
            await wait_for(waiter, timeout=remaining)
        except CancelledError:
            cancel = getattr(submitted, "cancel", None)
            if callable(cancel):
                cancel()
            waiter.cancel()
            await gather(waiter, return_exceptions=True)
            raise
        except (AsyncTimeoutError, TimeoutError) as error:
            if waiter.done() and not waiter.cancelled():
                terminal_error = waiter.exception()
                if terminal_error is error:
                    raise
            cancel = getattr(submitted, "cancel", None)
            if callable(cancel):
                cancel()
            raise TimeoutError("The operation update timed out.") from None

    async def _update_internal(
        self,
        *,
        request_deadline: float | None = None,
        authorization_deadline: float | None = None,
        **kwargs: Unpack[RequestKwargs],
    ) -> None:
        """Fetch and store one operation update on the SDK event loop.

        Updates are serialized for this operation. A pending response therefore
        cannot arrive after a newer terminal response and regress the stored
        operation state. Once a terminal response is stored, later queued
        updates return without making another request.

        :param request_deadline: Absolute monotonic request deadline captured
            before SDK-loop dispatch.
        :param authorization_deadline: Absolute monotonic authorization
            deadline captured before SDK-loop dispatch.
        :param kwargs: Request options for the operation service.
        """
        async with self._update_lock:
            if self.done():
                return

            if request_deadline is not None:
                request_timeout = request_deadline - monotonic()
                if request_timeout <= 0:
                    raise TimeoutError("The operation update timed out before request dispatch.")
                kwargs["timeout"] = request_timeout
            if authorization_deadline is not None:
                authorization_timeout = authorization_deadline - monotonic()
                if authorization_timeout <= 0:
                    raise TimeoutError("The operation update authorization timed out before dispatch.")
                kwargs["auth_timeout"] = authorization_timeout

            req = self._service.get(
                self._get_request_obj(id=self.id),
                **kwargs,
            )
            new_op = await req
            self._set_new_operation(cast(OperationPb, new_op._operation))

    def sync_wait(
        self,
        interval: float | timedelta = 1,
        timeout: float | None = None,
        poll_iteration_timeout: float | None | UnsetType = Unset,
        poll_per_retry_timeout: float | None | UnsetType = Unset,
        poll_retries: int | None = None,
        **kwargs: Unpack[RequestKwargsForOperation],
    ) -> None:
        """Synchronously wait for the operation to complete.

        This helper wraps :meth:`wait` and executes it in the channel's
        synchronous runner so callers that are not coroutine-based can wait
        for operation completion.

        See :meth:`wait` for parameter details.
        """
        self._check_process()
        if self.done():
            return None
        metadata = kwargs.get("metadata")
        if metadata is not None:
            kwargs["metadata"] = Metadata(metadata)
        auth_options = kwargs.get("auth_options")
        if auth_options is not None:
            kwargs["auth_options"] = dict(auth_options)
        _validate_timeout(timeout, "timeout")
        submitted_at = monotonic()
        run_timeout = None if timeout is None else timeout + 0.2
        return self._channel.run_sync(
            self._wait_from_submission(
                submitted_at,
                interval=interval,
                timeout=timeout,
                poll_iteration_timeout=poll_iteration_timeout,
                poll_per_retry_timeout=poll_per_retry_timeout,
                poll_retries=poll_retries,
                **kwargs,
            ),
            run_timeout,
        )

    def sync_update(
        self,
        **kwargs: Unpack[RequestKwargs],
    ) -> None:
        """Synchronously perform a single update of the operation state.

        This wraps the coroutine :meth:`update` and runs it via the channel's
        synchronous runner. An applicable authorization budget bounds the
        whole authorized flow; otherwise the request budget bounds SDK-loop
        queueing. Legacy channels whose provider is discoverable only on
        their owner loop enforce both clocks internally. A small safety margin
        accommodates scheduling overhead. Mutable metadata and authorization
        options are copied before the method dispatches work.

        :param kwargs: additional request keyword arguments
            see :class:`nebius.aio.request_kwargs.RequestKwargs` for details.
        :raises ValueError: If ``timeout`` or ``auth_timeout`` is NaN or
            infinite. Use ``None`` for an unlimited timeout.
        """
        self._check_process()
        metadata = kwargs.get("metadata")
        if metadata is not None:
            kwargs["metadata"] = Metadata(metadata)
        auth_options = kwargs.get("auth_options")
        if auth_options is not None:
            kwargs["auth_options"] = dict(auth_options)
        timeout_option = kwargs.get("timeout", Unset)
        timeout = DEFAULT_TIMEOUT if isinstance(timeout_option, UnsetType) else timeout_option
        auth_timeout_option = kwargs.get("auth_timeout", Unset)
        auth_timeout = DEFAULT_AUTH_TIMEOUT if isinstance(auth_timeout_option, UnsetType) else auth_timeout_option
        _validate_timeout(timeout, "timeout")
        _validate_timeout(auth_timeout, "auth_timeout")
        authorization_applies = _authorization_deadline_applies(
            self._channel,
            cast(dict[str, str], kwargs.get("auth_options") or {}),
        )
        run_limit = (
            auth_timeout if authorization_applies is True else timeout if authorization_applies is False else None
        )
        run_timeout = None if run_limit is None else max(0.0, run_limit) + 0.2
        submitted_at = monotonic()
        return self._channel.run_sync(
            self._update_from_submission(
                submitted_at,
                **kwargs,
            ),
            run_timeout,
        )

    async def wait(
        self,
        interval: float | timedelta = 1,
        timeout: float | None = None,
        poll_iteration_timeout: float | UnsetType | None = Unset,
        poll_per_retry_timeout: float | UnsetType | None = Unset,
        poll_retries: int | None = None,
        **kwargs: Unpack[RequestKwargsForOperation],
    ) -> None:
        """Asynchronously wait until the operation reaches a terminal state.

        The method repeatedly invokes :meth:`update` at the specified
        ``interval`` until the operation is done or the overall ``timeout`` is
        reached. Certain transient errors are treated as ignorable and will
        be retried.

        :param interval: Positive, finite polling interval (seconds or
            timedelta). This value is ignored when the operation is already
            terminal.
        :type interval: `float` or `timedelta`
        :param timeout: overall timeout (seconds) for waiting, or `None` for
            infinite timeout, default infinite.
        :type timeout: optional `float`
        :param poll_iteration_timeout: timeout used for each polling iteration, will be
            passed as the ``timeout`` to each :meth:`update` call.
        :type poll_iteration_timeout: optional `float` or `None`
        :param poll_per_retry_timeout: per-retry timeout for polling requests, will
            be passed as the ``per_retry_timeout`` to each :meth:`update` call.
        :type poll_per_retry_timeout: optional `float` or `None`, will be passed as the
            ``per_retry_timeout`` to each :meth:`update` call.
        :param poll_retries: retry count used for polling requests, will be passed as
            the ``retries`` to each :meth:`update` call.
        :param kwargs: additional request keyword arguments
            see :class:`nebius.aio.request_kwargs.RequestKwargsForOperation` for
            details. Mutable metadata and authorization options are copied
            before polling is submitted to the SDK event loop.

        :raises TimeoutError: when the overall timeout is exceeded
        :raises ValueError: When an unfinished operation receives a
            non-positive/non-finite polling interval or a non-finite overall
            timeout. Use ``None`` for an unlimited timeout.
        """
        self._check_process()
        await self._wait_from_submission(
            monotonic(),
            interval=interval,
            timeout=timeout,
            poll_iteration_timeout=poll_iteration_timeout,
            poll_per_retry_timeout=poll_per_retry_timeout,
            poll_retries=poll_retries,
            **kwargs,
        )

    async def _wait_from_submission(
        self,
        submitted_at: float,
        interval: float | timedelta = 1,
        timeout: float | None = None,
        poll_iteration_timeout: float | UnsetType | None = Unset,
        poll_per_retry_timeout: float | UnsetType | None = Unset,
        poll_retries: int | None = None,
        **kwargs: Unpack[RequestKwargsForOperation],
    ) -> None:
        """Submit polling with a caller-captured monotonic start time.

        :param submitted_at: Monotonic time when the caller submitted the
            wait. The overall timeout includes all later dispatch delay.
        :param interval: Positive delay between polling attempts.
        :param timeout: Overall wait limit, or ``None`` for no limit.
        :param poll_iteration_timeout: Limit for one polling request.
        :param poll_per_retry_timeout: Limit for each retry.
        :param poll_retries: Retry count for each polling request.
        :param kwargs: Additional request options for the operation service.
        """
        # Preserve the historical terminal fast path. In particular,
        # asyncio.wait_for(..., 0) cannot start a newly submitted coroutine,
        # even when that coroutine would immediately observe terminal state.
        if self.done():
            return
        _validate_timeout(timeout, "timeout")
        if isinstance(interval, timedelta):
            interval = interval.total_seconds()
        if not isfinite(interval) or interval <= 0:
            raise ValueError("The interval value must be a finite positive number of seconds.")
        metadata = kwargs.get("metadata")
        if metadata is not None:
            kwargs["metadata"] = Metadata(metadata)
        auth_options = kwargs.get("auth_options")
        if auth_options is not None:
            kwargs["auth_options"] = dict(auth_options)
        deadline = None if timeout is None else submitted_at + max(timeout, 0)
        submit = getattr(self._channel, "run_async", None)
        wait = self._wait_internal(
            interval=interval,
            timeout=timeout,
            deadline=deadline,
            poll_iteration_timeout=poll_iteration_timeout,
            poll_per_retry_timeout=poll_per_retry_timeout,
            poll_retries=poll_retries,
            **kwargs,
        )
        try:
            submitted = submit(wait) if callable(submit) else wait
        except BaseException:
            dispose_unstarted_awaitable(wait)
            raise
        if timeout is None:
            await submitted
            return
        if deadline is None:  # pragma: no cover - narrowed by ``timeout`` above
            raise RuntimeError("The finite operation timeout has no deadline.")
        completed = getattr(submitted, "done", None)
        if callable(completed) and completed():
            # A terminal submission wins even if result publication consumed
            # the final fraction of the caller-side budget.
            await submitted
            return
        remaining = max(0.0, deadline - monotonic())
        try:
            # Bound dispatch to the SDK loop as well as polling performed on
            # it. ``wait_for`` propagates cancellation to the one submitted
            # wait when the caller-side deadline expires.
            await wait_for(submitted, timeout=remaining)
        except (AsyncTimeoutError, TimeoutError) as error:
            raise TimeoutError("The operation wait timed out.") from error

    async def _wait_internal(
        self,
        interval: float | timedelta = 1,
        timeout: float | None = None,
        deadline: float | None = None,
        poll_iteration_timeout: float | UnsetType | None = Unset,
        poll_per_retry_timeout: float | UnsetType | None = Unset,
        poll_retries: int | None = None,
        **kwargs: Unpack[RequestKwargsForOperation],
    ) -> None:
        """Poll the operation on the SDK event loop until it is complete.

        A local timeout and a service ``DEADLINE_EXCEEDED`` response are
        transient for one polling iteration. Other errors stop the wait.

        :param interval: Delay between polling attempts, in seconds or as a
            time delta.
        :param timeout: Overall wait limit in seconds. Use ``None`` for no
            limit.
        :param deadline: Absolute monotonic deadline captured before dispatch
            to the SDK loop. This includes runtime queueing and update-lock
            acquisition in the overall timeout.
        :param poll_iteration_timeout: Timeout for one update request.
        :param poll_per_retry_timeout: Timeout for each retry of an update
            request.
        :param poll_retries: Retry count for each update request.
        :param kwargs: Additional request options for the operation service.
        :raises TimeoutError: If the overall wait limit expires.
        """
        if deadline is None and timeout is not None:
            deadline = monotonic() + max(timeout, 0)
        if poll_iteration_timeout is None:
            if timeout is not None:
                poll_iteration_timeout = min(5, timeout)
        if isinstance(interval, timedelta):
            interval = interval.total_seconds()

        from .service_error import RequestError as ServiceRequestError

        def _is_ignorable(err: Exception) -> bool:
            """Return whether one polling error is transient."""
            if isinstance(err, TimeoutError):
                return True
            if isinstance(err, ServiceRequestError):
                try:
                    return bool(err.status.code == StatusCode.DEADLINE_EXCEEDED)
                except Exception:  # pragma: no cover - defensive
                    return False
            return False

        async def _safe_update() -> None:
            """Run one update and ignore only transient polling errors."""
            try:
                update_kwargs: dict[str, Any] = {
                    **kwargs,
                    "timeout": poll_iteration_timeout,
                    "per_retry_timeout": poll_per_retry_timeout,
                }
                if poll_retries is not None:
                    update_kwargs["retries"] = poll_retries
                update = self._update_internal(**cast(RequestKwargs, update_kwargs))
                if deadline is None:
                    await update
                else:
                    remaining = deadline - monotonic()
                    if remaining <= 0:
                        update.close()
                        raise TimeoutError("The operation wait timed out.")
                    await wait_for(update, timeout=remaining)
            except Exception as e:
                if deadline is not None and monotonic() >= deadline:
                    raise TimeoutError("The operation wait timed out.") from e
                if not _is_ignorable(e):
                    raise

        if not self.done():
            await _safe_update()
        while not self.done():
            if deadline is not None:
                remaining = deadline - monotonic()
                if remaining <= 0:
                    raise TimeoutError("The operation wait timed out.")
                await sleep(min(interval, remaining))
            else:
                await sleep(interval)
            if deadline is not None and monotonic() >= deadline:
                raise TimeoutError("The operation wait timed out.")
            await _safe_update()

    def _set_new_operation(self, operation: OperationPb) -> None:
        """Replace the wrapped operation object with a new instance.

        The replacement is only allowed when the new operation has the same
        protobuf class as the currently wrapped object; otherwise an
        :class:`SDKError` is raised.
        """
        self._check_process()
        with self._state_lock:
            if isinstance(operation, self._operation.__class__):
                self._operation = operation
                return
        raise SDKError(f"The SDK does not support operation type {type(operation)}.")

    @property
    def id(self) -> str:
        """Return the operation identifier (string)."""
        return self._operation_snapshot().id

    @property
    def description(self) -> str:
        """Return the operation description as provided by the service."""
        return self._operation_snapshot().description

    @property
    def created_at(self) -> datetime:
        """Return the operation creation timestamp.

        If the underlying protobuf does not expose a creation time this helper
        returns the current time in the local timezone.
        :rtype: datetime
        """
        ca = self._operation_snapshot().created_at
        if ca is None:
            return datetime.now(local_timezone)
        return ca

    @property
    def created_by(self) -> str:
        """Return the identity that created the operation (string)."""
        return self._operation_snapshot().created_by

    @property
    def finished_at(self) -> datetime | None:
        """Return the completion time or ``None`` if the operation is not finished."""
        return self._operation_snapshot().finished_at

    @property
    def resource_id(self) -> str:
        """Return the resource id associated with the operation."""
        return self._operation_snapshot().resource_id

    def successful(self) -> bool:
        """Return True when the operation completed successfully."""
        s = self.status()
        return s is not None and s.code == StatusCode.OK

    def raw(self) -> OperationPb:
        """Return the underlying operation protobuf object.

        Use this to access version-specific fields that are not exposed by the
        normalized wrapper. The returned object preserves the existing mutable
        compatibility surface; mutating it concurrently bypasses this wrapper's
        snapshot and locking guarantees. Callers must serialize such mutation.

        :return: Current mutable operation protobuf object.
        """
        return self._operation_snapshot()


def _check_presence(message: object, field: str) -> bool:
    checker = getattr(message, "check_presence", None)
    if checker is None:
        return True
    try:
        return bool(checker(field))
    except Exception:
        return False


def _get_timestamp(message: object, field: str) -> datetime | None:
    if not _check_presence(message, field):
        return None
    value = getattr(message, field, None)
    if value is None:
        return None
    return cast(datetime, value)


def _get_work_done(message: object) -> ProgressTracker.WorkDone | None:
    if not _check_presence(message, "work_done"):
        return None
    return getattr(message, "work_done", None)


class _ProgressTrackerWrapper:
    def __init__(self, operation: Operation[OperationPb]) -> None:
        self._operation = operation

    def _tracker(self) -> object | None:
        return self._tracker_from(self._operation._operation_snapshot())

    @staticmethod
    def _tracker_from(op_proto: object) -> object | None:
        """Return a tracker from one stable operation snapshot."""
        if not _check_presence(op_proto, "progress_tracker"):
            return None
        return getattr(op_proto, "progress_tracker", None)

    def description(self) -> str:
        tracker = self._tracker()
        if tracker is None:
            return ""
        return getattr(tracker, "description", "")

    def started_at(self) -> datetime | None:
        tracker = self._tracker()
        if tracker is None:
            return None
        return _get_timestamp(tracker, "started_at")

    def finished_at(self) -> datetime | None:
        tracker = self._tracker()
        if tracker is None:
            return None
        return _get_timestamp(tracker, "finished_at")

    def work_done(self) -> ProgressTracker.WorkDone | None:
        tracker = self._tracker()
        if tracker is None:
            return None
        return _get_work_done(tracker)

    def work_fraction(self) -> float | None:
        operation = self._operation._operation_snapshot()
        if operation.status is not None:
            return 1.0
        tracker = self._tracker_from(operation)
        if tracker is None:
            return None
        work_done = _get_work_done(tracker)
        if work_done is None:
            return None
        total = getattr(work_done, "total_tick_count", 0)
        if total <= 0:
            return None
        done = getattr(work_done, "done_tick_count", 0)
        return float(done) / float(total)

    def estimated_finished_at(self) -> datetime | None:
        operation = self._operation._operation_snapshot()
        tracker = self._tracker_from(operation)
        if tracker is None:
            return _get_timestamp(operation, "finished_at")
        finished = _get_timestamp(tracker, "finished_at")
        if finished is not None:
            return finished
        operation_finished = _get_timestamp(operation, "finished_at")
        if operation_finished is not None:
            return operation_finished
        return _get_timestamp(tracker, "estimated_finished_at")

    def time_fraction(self) -> float | None:
        operation = self._operation._operation_snapshot()
        if operation.status is not None:
            return 1.0
        tracker = self._tracker_from(operation)
        if tracker is None:
            return None
        started_at = _get_timestamp(tracker, "started_at")
        if started_at is None:
            return None
        estimated_finished_at = _get_timestamp(tracker, "estimated_finished_at")
        if estimated_finished_at is None:
            return None
        now = datetime.now(local_timezone)
        if now < started_at:
            return 0.0
        if now > estimated_finished_at:
            return 1.0
        total_duration = (estimated_finished_at - started_at).total_seconds()
        elapsed_duration = (now - started_at).total_seconds()
        if total_duration <= 0 or elapsed_duration < 0:
            return None
        return elapsed_duration / total_duration

    def steps(self) -> Sequence[CurrentStep]:
        tracker = self._tracker()
        if tracker is None:
            return []
        steps = getattr(tracker, "steps", [])
        return [CurrentStep(step) for step in steps]

    def __repr__(self) -> str:
        parts = [f"{self.description()}"]
        started = self.started_at()
        if started is not None:
            parts.append(f"started_at: {started}")
        finished = self.finished_at()
        if finished is not None:
            parts.append(f"finished_at: {finished}")
        eta = self.estimated_finished_at()
        if eta is not None:
            parts.append(f"eta: {eta}")
        work = self.work_done()
        if work is not None and work.total_tick_count:
            parts.append(f"work_done: {work.done_tick_count}/{work.total_tick_count}")
        steps = self.steps()
        if steps:
            parts.append("steps: [" + ", ".join(repr(step) for step in steps) + "]")
        return "OperationProgressTracker(" + ", ".join(parts) + ")"


def wrap_progress_tracker(
    operation: Operation[OperationPb] | None,
) -> OperationProgressTracker | None:
    """Return a progress tracker wrapper for an operation if available.

    This helper is exposed as :meth:`Operation.progress_tracker` and performs
    the presence checks needed to avoid accessing default/absent fields on
    protobuf wrappers.

    Example
    -------
    Using the helper directly::

        tracker = wrap_progress_tracker(operation)
        if tracker is not None:
            print(tracker.description())

    """
    if operation is None:
        return None
    op_proto = operation._operation_snapshot()
    if not _check_presence(op_proto, "progress_tracker"):
        return None
    tracker = getattr(op_proto, "progress_tracker", None)
    if tracker is None:
        return None
    return _ProgressTrackerWrapper(operation)
