"""Helpers for working with long-running operations.

This module provides an :class:`Operation` wrapper that normalizes different
versions of the service operation protobuf and exposes convenient helpers for
polling, synchronous waiting, and inspecting operation metadata.

The wrapper accepts operation protobufs from either the current v1 API or an
older v1alpha1 variant and routes calls to the corresponding operation
service client.
"""

from __future__ import annotations

from asyncio import sleep
from collections.abc import Sequence
from datetime import datetime, timedelta
from time import time
from typing import TYPE_CHECKING, Generic, Protocol, TypeVar, cast

from grpc import StatusCode
from typing_extensions import Unpack

from nebius.aio.abc import ClientChannelInterface
from nebius.aio.request import DEFAULT_TIMEOUT
from nebius.aio.request_kwargs import RequestKwargs, RequestKwargsForOperation
from nebius.base.error import SDKError
from nebius.base.protos.unset import Unset, UnsetType
from nebius.base.protos.well_known import local_timezone

from .constant_channel import Constant
from .request_status import RequestStatus

if TYPE_CHECKING:
    from nebius.api.nebius.common.v1 import ProgressTracker

OperationPb = TypeVar("OperationPb")
"""
A convenience wrapper around operation protobufs.
Either :class:`nebius.api.nebius.common.v1.Operation` or
:class:`nebius.api.nebius.common.v1alpha1.Operation`, or their protobuf classes.
"""
T = TypeVar("T")


class CurrentStep:
    """Wrapper describing a step of an operation progress tracker.

    This class wraps a ``ProgressTracker.Step`` instance and exposes
    convenient accessors that normalize missing fields as ``None``.

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
        parts = [f"CurrentStep({self.description()}"]
        started = self.started_at()
        if started is not None:
            parts.append(f"started_at: {started}")
        finished = self.finished_at()
        if finished is not None:
            parts.append(f"finished_at: {finished}")
        work = self.work_done()
        if work is not None and work.total_tick_count:
            parts.append(f"work_done: {work.done_tick_count}/{work.total_tick_count}")
        return ", ".join(parts) + ")"


class OperationProgressTracker(Protocol):
    """Protocol describing operation-level progress tracking.

    This protocol mirrors the server-side ``ProgressTracker`` object and adds
    convenience helpers for time and work fractions.

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
    """A convenience wrapper around operation protobufs.

    The :class:`Operation` wrapper normalizes
    :class:`nebius.api.nebius.common.v1.Operation`
    and :class:`nebius.api.nebius.common.v1alpha1.Operation` representations and
    provides helpers to:

    - inspect operation metadata (id, resource_id, timestamps),
    - poll/update the operation state via the corresponding operation
      service, and
    - wait for completion either asynchronously or synchronously.

    The wrapper stores an operation service client bound to a
    :class:`nebius.aio.constant_channel.Constant` that points at the provided
    ``source_method`` and reuses the provided ``channel`` for network/auth
    behaviors.

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

        sdk = SDK(config_reader=Config())
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

        sdk = SDK(config_reader=Config())
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
        source_method: str,
        channel: ClientChannelInterface,
        operation: OperationPb,
    ) -> None:
        """Create an operation wrapper from the operation protobuf."""
        from nebius.api.nebius.common.v1 import (
            GetOperationRequest,
            Operation,
            OperationServiceClient,
        )
        from nebius.api.nebius.common.v1alpha1 import (
            GetOperationRequest as OldGet,
        )
        from nebius.api.nebius.common.v1alpha1 import (
            Operation as Old,
        )
        from nebius.api.nebius.common.v1alpha1 import (
            OperationServiceClient as OldClient,
        )

        self._channel = channel
        _operation: OperationPb | Operation | Old = operation
        if isinstance(_operation, Operation.__PB2_CLASS__):
            _operation = Operation(_operation)
        if isinstance(_operation, Old.__PB2_CLASS__):
            _operation = Old(_operation)

        if isinstance(_operation, Operation):
            self._service: OperationServiceClient | OldClient = OperationServiceClient(
                Constant(source_method, channel)
            )
            self._get_request_obj: type[GetOperationRequest | OldGet] = (
                GetOperationRequest
            )
        elif isinstance(_operation, Old):
            self._service = OldClient(Constant(source_method, channel))
            self._get_request_obj = OldGet
        else:
            raise SDKError(f"Operation type {type(_operation)} not supported.")

        self._operation: Operation | Old = _operation

    def __repr__(self) -> str:
        """Return a compact string representation useful for debugging."""
        parts = [
            f"Operation({self.id}",
            f"resource_id: {self.resource_id}",
            f"status: {self.status()}",
        ]
        tracker = self.progress_tracker()
        if tracker is not None:
            work = tracker.work_done()
            if work is not None and work.total_tick_count:
                parts.append(
                    f"work_done: {work.done_tick_count}/{work.total_tick_count}"
                )
            eta = tracker.estimated_finished_at()
            if eta is not None:
                parts.append(f"eta: {eta}")
        return ", ".join(parts) + ")"

    def status(self) -> RequestStatus | None:
        """Return the operation's current status object or ``None``.

        :rtype: :class:`RequestStatus` or nothing
        """
        return self._operation.status

    def progress_tracker(self) -> OperationProgressTracker | None:
        """Return an operation progress tracker when available.

        This helper returns ``None`` when the operation does not expose a
        progress tracker (for example, v1alpha1 operations or services that do
        not provide progress details).

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
        """
        if self.done():
            return

        req = self._service.get(
            self._get_request_obj(id=self.id),  # type: ignore
            **kwargs,
        )
        new_op = await req
        self._set_new_operation(new_op._operation)  # type: ignore

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
        run_timeout = None if timeout is None else timeout + 0.2
        return self._channel.run_sync(
            self.wait(
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
        synchronous runner. A small safety margin is added to the provided
        timeout to allow for scheduling overhead.

        :param kwargs: additional request keyword arguments
            see :class:`nebius.aio.request_kwargs.RequestKwargs` for details.
        """
        timeout = kwargs.get("timeout", Unset)
        run_timeout: float | None = None
        if isinstance(timeout, (int, float)):
            run_timeout = timeout + 0.2
        elif isinstance(timeout, UnsetType):
            run_timeout = DEFAULT_TIMEOUT + 0.2
        return self._channel.run_sync(
            self.update(
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
        reached. Certain transient errors (deadline exceeded) are treated as
        ignorable and will be retried.

        :param interval: polling interval (seconds or timedelta)
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
            details.

        :raises TimeoutError: when the overall timeout is exceeded
        """

        start = time()
        if poll_iteration_timeout is None:
            if timeout is not None:
                poll_iteration_timeout = min(5, timeout)
        if isinstance(interval, timedelta):
            interval = interval.total_seconds()
        from nebius.aio.service_error import RequestError as ServiceRequestError

        def _is_ignorable(err: Exception) -> bool:
            # TimeoutError raised locally or RequestError with DEADLINE_EXCEEDED
            if isinstance(err, TimeoutError):
                return True
            if isinstance(err, ServiceRequestError):
                try:
                    return err.status.code == StatusCode.DEADLINE_EXCEEDED
                except Exception:  # pragma: no cover - defensive
                    return False
            return False

        async def _safe_update() -> None:
            try:
                await self.update(
                    timeout=poll_iteration_timeout,
                    per_retry_timeout=poll_per_retry_timeout,
                    retries=poll_retries,
                    **kwargs,
                )
            except Exception as e:  # noqa: S110
                if not _is_ignorable(e):
                    raise

        if not self.done():
            await _safe_update()
        while not self.done():
            current_time = time()
            if timeout is not None and current_time > timeout + start:
                raise TimeoutError("Operation wait timeout")
            await sleep(interval)
            await _safe_update()

    def _set_new_operation(self, operation: OperationPb) -> None:
        """Replace the wrapped operation object with a new instance.

        The replacement is only allowed when the new operation has the same
        protobuf class as the currently wrapped object; otherwise an
        :class:`SDKError` is raised.
        """
        if isinstance(operation, self._operation.__class__):
            self._operation = operation  # type: ignore
        else:
            raise SDKError(f"Operation type {type(operation)} not supported.")

    @property
    def id(self) -> str:
        """Return the operation identifier (string)."""
        return self._operation.id

    @property
    def description(self) -> str:
        """Return the operation description as provided by the service."""
        return self._operation.description

    @property
    def created_at(self) -> datetime:
        """Return the operation creation timestamp.

        If the underlying protobuf does not expose a creation time this helper
        returns the current time in the local timezone.
        :rtype: datetime
        """
        ca = self._operation.created_at
        if ca is None:  # type: ignore[unused-ignore]
            return datetime.now(local_timezone)
        return ca

    @property
    def created_by(self) -> str:
        """Return the identity that created the operation (string)."""
        return self._operation.created_by

    @property
    def finished_at(self) -> datetime | None:
        """Return the completion timestamp for the operation or ``None`` if
        the operation hasn't finished yet.
        """
        return self._operation.finished_at

    @property
    def resource_id(self) -> str:
        """Return the resource id associated with the operation."""
        return self._operation.resource_id

    def successful(self) -> bool:
        """Return True when the operation completed successfully."""
        s = self.status()
        return s is not None and s.code == StatusCode.OK

    def raw(self) -> OperationPb:
        """Return the underlying operation protobuf object.

        Use this to access version-specific fields that are not exposed by the
        normalized wrapper.
        """
        return self._operation  # type: ignore


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
        op_proto = getattr(self._operation, "_operation", None)
        if op_proto is None:
            return None
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
        if self._operation.done():
            return 1.0
        tracker = self._tracker()
        if tracker is None:
            return None
        work_done = self.work_done()
        if work_done is None:
            return None
        total = getattr(work_done, "total_tick_count", 0)
        if total <= 0:
            return None
        done = getattr(work_done, "done_tick_count", 0)
        return float(done) / float(total)

    def estimated_finished_at(self) -> datetime | None:
        tracker = self._tracker()
        if tracker is None:
            return _get_timestamp(self._operation._operation, "finished_at")
        finished = _get_timestamp(tracker, "finished_at")
        if finished is not None:
            return finished
        operation_finished = _get_timestamp(self._operation._operation, "finished_at")
        if operation_finished is not None:
            return operation_finished
        return _get_timestamp(tracker, "estimated_finished_at")

    def time_fraction(self) -> float | None:
        if self._operation.done():
            return 1.0
        tracker = self._tracker()
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
        parts = [f"OperationProgressTracker({self.description()}"]
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
        return ", ".join(parts) + ")"


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
    op_proto = getattr(operation, "_operation", None)
    if op_proto is None:
        return None
    if not _check_presence(op_proto, "progress_tracker"):
        return None
    tracker = getattr(op_proto, "progress_tracker", None)
    if tracker is None:
        return None
    return _ProgressTrackerWrapper(operation)
