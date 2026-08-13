# type: ignore
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest


@pytest.mark.asyncio()
async def test_operation_progress_tracker_updates() -> None:
    import grpc.aio
    from nebius.aio.channel import Channel, NoCredentials
    from nebius.aio.operation import Operation
    from nebius.api.google.rpc import Status
    from nebius.api.nebius.common.v1 import (
        Operation as OperationMessage,
    )
    from nebius.api.nebius.common.v1 import (
        OperationServiceClient,
        ProgressTracker,
    )
    from nebius.base.options import INSECURE
    from nebius.base.protos.well_known import local_timezone

    from tests.grpc_service import add_service

    def to_local(dt: datetime) -> datetime:
        return dt.astimezone(local_timezone)

    def op_with_tracker(
        tracker: ProgressTracker | None = None,
        *,
        status: Status | None = None,
        finished_at: datetime | None = None,
    ) -> OperationMessage:
        op = OperationMessage(id="op-1")
        if tracker is not None:
            op.progress_tracker = tracker
        if status is not None:
            op.status = status
        if finished_at is not None:
            op.finished_at = finished_at
        return op

    base_now = datetime.now(timezone.utc)
    started_past = base_now - timedelta(seconds=120)
    started_now = base_now - timedelta(seconds=5)
    started_future = base_now + timedelta(seconds=60)
    estimate_future = base_now + timedelta(seconds=120)
    estimate_past = base_now - timedelta(seconds=10)
    estimate_updated = base_now + timedelta(seconds=30)
    finished_time = base_now + timedelta(seconds=1)

    op0 = OperationMessage(id="op-1")

    op1 = op_with_tracker(ProgressTracker())

    op2 = op_with_tracker(
        ProgressTracker(
            description="phase-1",
            started_at=started_now,
            work_done=ProgressTracker.WorkDone(
                total_tick_count=10,
                done_tick_count=2,
            ),
        ),
    )

    op3 = op_with_tracker(
        ProgressTracker(
            description="phase-1-est",
            started_at=started_future,
            estimated_finished_at=estimate_future,
        ),
    )

    step_a = ProgressTracker.Step(
        description="step-a",
        started_at=started_past,
        work_done=ProgressTracker.WorkDone(
            total_tick_count=4,
            done_tick_count=1,
        ),
    )
    step_b = ProgressTracker.Step(
        description="step-b",
        started_at=started_past,
    )
    tracker4 = ProgressTracker(
        description="phase-2",
        started_at=started_past,
        estimated_finished_at=estimate_past,
    )
    tracker4.steps.extend([step_a, step_b])
    op4 = op_with_tracker(tracker4)

    step_a_updated = ProgressTracker.Step(
        description="step-a",
        started_at=started_past,
        finished_at=base_now - timedelta(seconds=5),
        work_done=ProgressTracker.WorkDone(
            total_tick_count=4,
            done_tick_count=4,
        ),
    )
    step_b_updated = ProgressTracker.Step(
        description="step-b updated",
        started_at=started_past,
        work_done=ProgressTracker.WorkDone(
            total_tick_count=2,
            done_tick_count=1,
        ),
    )
    tracker5 = ProgressTracker(
        description="phase-2 updated",
        started_at=started_past,
        estimated_finished_at=estimate_updated,
        work_done=ProgressTracker.WorkDone(
            total_tick_count=10,
            done_tick_count=7,
        ),
    )
    tracker5.steps.extend([step_a_updated, step_b_updated])
    op5 = op_with_tracker(tracker5)

    step_a_done = ProgressTracker.Step(
        description="step-a",
        started_at=started_past,
        finished_at=finished_time,
        work_done=ProgressTracker.WorkDone(
            total_tick_count=4,
            done_tick_count=4,
        ),
    )
    step_b_done = ProgressTracker.Step(
        description="step-b updated",
        started_at=started_past,
        finished_at=finished_time,
        work_done=ProgressTracker.WorkDone(
            total_tick_count=2,
            done_tick_count=2,
        ),
    )
    tracker6 = ProgressTracker(
        description="done",
        started_at=started_past,
        finished_at=finished_time,
        work_done=ProgressTracker.WorkDone(
            total_tick_count=10,
            done_tick_count=10,
        ),
    )
    tracker6.steps.extend([step_a_done, step_b_done])
    op6 = op_with_tracker(tracker6, status=Status(code=0), finished_at=finished_time)

    class MockOperationService:
        def __init__(self, responses: list[OperationMessage]) -> None:
            self._responses = responses
            self._index = 0

        async def Get(self, request, context):  # noqa: N802
            assert request.id == "op-1"
            if self._index < len(self._responses):
                response = self._responses[self._index]
                self._index += 1
                return response
            return self._responses[-1]

    srv = grpc.aio.server()
    port = srv.add_insecure_port("[::]:0")
    add_service(
        srv,
        OperationServiceClient,
        MockOperationService([op1, op2, op3, op4, op5, op6]),
    )
    await srv.start()

    channel = None
    try:
        channel = Channel(
            domain=f"localhost:{port}",
            options=[(INSECURE, True)],
            credentials=NoCredentials(),
        )
        operation = Operation(".nebius.common.v1.OperationService.Get", channel, op0)

        assert operation.progress_tracker() is None

        await operation.update()
        tracker = operation.progress_tracker()
        assert tracker is not None
        assert tracker.description() == ""
        assert tracker.started_at() is None
        assert tracker.estimated_finished_at() is None
        assert tracker.work_fraction() is None
        assert tracker.time_fraction() is None
        assert tracker.steps() == []

        await operation.update()
        tracker = operation.progress_tracker()
        assert tracker is not None
        assert tracker.description() == "phase-1"
        assert tracker.started_at() == to_local(started_now)
        assert tracker.estimated_finished_at() is None
        assert tracker.work_fraction() == pytest.approx(0.2)
        assert tracker.time_fraction() is None
        assert tracker.steps() == []

        await operation.update()
        tracker = operation.progress_tracker()
        assert tracker is not None
        assert tracker.description() == "phase-1-est"
        assert tracker.started_at() == to_local(started_future)
        assert tracker.estimated_finished_at() == to_local(estimate_future)
        assert tracker.work_fraction() is None
        assert tracker.time_fraction() == 0.0

        await operation.update()
        tracker = operation.progress_tracker()
        assert tracker is not None
        assert tracker.description() == "phase-2"
        assert tracker.estimated_finished_at() == to_local(estimate_past)
        assert tracker.time_fraction() == 1.0
        assert tracker.work_fraction() is None
        steps = tracker.steps()
        assert len(steps) == 2
        assert steps[0].description() == "step-a"
        assert steps[0].work_fraction() == pytest.approx(0.25)
        assert steps[1].description() == "step-b"
        assert steps[1].work_fraction() is None

        await operation.update()
        tracker = operation.progress_tracker()
        assert tracker is not None
        assert tracker.description() == "phase-2 updated"
        assert tracker.estimated_finished_at() == to_local(estimate_updated)
        assert tracker.work_fraction() == pytest.approx(0.7)
        time_fraction = tracker.time_fraction()
        assert time_fraction is not None
        assert 0.0 <= time_fraction <= 1.0
        steps = tracker.steps()
        assert len(steps) == 2
        assert steps[0].work_fraction() == pytest.approx(1.0)
        assert steps[0].finished_at() is not None
        assert steps[1].description() == "step-b updated"
        assert steps[1].work_fraction() == pytest.approx(0.5)

        await operation.update()
        tracker = operation.progress_tracker()
        assert tracker is not None
        assert operation.done() is True
        assert tracker.description() == "done"
        assert tracker.work_fraction() == 1.0
        assert tracker.time_fraction() == 1.0
        assert tracker.estimated_finished_at() == to_local(finished_time)
        assert operation.finished_at == to_local(finished_time)
        steps = tracker.steps()
        assert len(steps) == 2
        assert steps[0].work_fraction() == pytest.approx(1.0)
        assert steps[1].work_fraction() == pytest.approx(1.0)
    finally:
        if channel is not None:
            await channel.close()
        await srv.stop(0)


@pytest.mark.asyncio()
async def test_operation_progress_tracker_mlflow_cluster_operation() -> None:
    from nebius.aio.channel import Channel, NoCredentials
    from nebius.aio.operation import Operation
    from nebius.api.nebius.common.v1alpha1 import Operation as OperationMessage
    from nebius.base.options import INSECURE

    channel = None
    try:
        channel = Channel(
            domain="localhost",
            options=[(INSECURE, True)],
            credentials=NoCredentials(),
        )
        op = OperationMessage(id="mlflow-op-1")
        operation = Operation(
            ".nebius.msp.mlflow.v1alpha1.ClusterService.Create",
            channel,
            op,
        )
        assert operation.progress_tracker() is None
    finally:
        if channel is not None:
            await channel.close()


@pytest.mark.asyncio()
async def test_concurrent_operation_updates_are_serialized() -> None:
    """A late pending response cannot overwrite a terminal update."""
    from nebius.aio.channel import Channel, NoCredentials
    from nebius.aio.operation import Operation
    from nebius.api.google.rpc import Status
    from nebius.api.nebius.common.v1 import Operation as OperationMessage

    channel = Channel(credentials=NoCredentials())
    operation = Operation(
        ".nebius.common.v1.OperationService.Get",
        channel,
        OperationMessage(id="op-1"),
    )
    first_entered = asyncio.Event()
    release_first = asyncio.Event()
    second_started = asyncio.Event()
    pending = OperationMessage(id="op-1")
    terminal = OperationMessage(id="op-1", status=Status(code=0))

    class Response:
        def __init__(self, value: OperationMessage) -> None:
            self._operation = value

    class Service:
        def __init__(self) -> None:
            self.calls = 0

        def get(self, request, **kwargs):
            self.calls += 1
            call = self.calls

            async def result() -> Response:
                if call == 1:
                    first_entered.set()
                    await release_first.wait()
                    return Response(pending)
                second_started.set()
                return Response(terminal)

            return result()

    operation._service = Service()
    try:
        first = asyncio.create_task(operation._update_internal())
        await first_entered.wait()
        second = asyncio.create_task(operation._update_internal())
        await asyncio.sleep(0)
        assert not second_started.is_set()
        release_first.set()
        await asyncio.gather(first, second)
        assert operation.done()
    finally:
        await channel.close()


@pytest.mark.asyncio()
async def test_operation_wait_timeout_bounds_update_lock_acquisition() -> None:
    """Overall timeout includes waiting behind a serialized update."""
    from threading import Event
    from time import monotonic

    from nebius.aio.channel import Channel, NoCredentials
    from nebius.aio.operation import Operation
    from nebius.api.nebius.common.v1 import Operation as OperationMessage

    channel = Channel(credentials=NoCredentials())
    operation = Operation(
        ".nebius.common.v1.OperationService.Get",
        channel,
        OperationMessage(id="op-timeout"),
    )
    lock_held = Event()

    async def hold_update_lock() -> None:
        async with operation._update_lock:
            lock_held.set()
            await asyncio.Event().wait()

    blocker = channel.run_async(hold_update_lock())
    assert await asyncio.to_thread(lock_held.wait, 5)
    started = monotonic()
    try:
        with pytest.raises(TimeoutError, match="operation wait timed out"):
            await operation.wait(timeout=0.05)
        assert monotonic() - started < 0.5
    finally:
        blocker.cancel()
        await channel.close()


@pytest.mark.asyncio()
async def test_operation_wait_timeout_includes_synchronous_admission_delay() -> None:
    """Expired admission time cannot grant polling a fresh timeout."""
    from threading import Event
    from time import sleep

    from nebius.aio.channel import Channel, NoCredentials
    from nebius.aio.operation import Operation
    from nebius.api.nebius.common.v1 import Operation as OperationMessage

    channel = Channel(credentials=NoCredentials())
    operation = Operation(
        ".nebius.common.v1.OperationService.Get",
        channel,
        OperationMessage(id="op-admission-timeout"),
    )
    wait_started = Event()

    async def pending_wait(**kwargs: object) -> None:
        wait_started.set()
        await asyncio.Event().wait()

    def delayed_submission(awaitable: object):
        sleep(0.05)
        return awaitable

    operation._wait_internal = pending_wait  # type: ignore[method-assign]
    channel.run_async = delayed_submission  # type: ignore[method-assign]
    try:
        with pytest.raises(TimeoutError, match="operation wait timed out"):
            await operation.wait(timeout=0.01)
        assert not wait_started.is_set()
    finally:
        del channel.run_async
        await channel.close()


@pytest.mark.asyncio()
@pytest.mark.parametrize(
    ("timeout", "auth_timeout", "authorization_enabled"),
    ((0.05, 5, False), (5, 0.05, True), (0.05, 5, True)),
    ids=("request-timeout", "authorization-timeout", "authorized-dispatch"),
)
async def test_operation_update_timeout_includes_sdk_loop_queueing(
    timeout: float,
    auth_timeout: float,
    authorization_enabled: bool,
) -> None:
    """Direct update budgets expire before a late service request starts."""
    from threading import Event

    from nebius.aio.channel import Channel, NoCredentials
    from nebius.aio.operation import Operation
    from nebius.aio.token.static import Bearer as StaticBearer
    from nebius.api.nebius.common.v1 import Operation as OperationMessage

    credentials = StaticBearer("token") if authorization_enabled else NoCredentials()
    channel = Channel(credentials=credentials)
    operation = Operation(
        ".nebius.common.v1.OperationService.Get",
        channel,
        OperationMessage(id="op-update-timeout"),
    )
    loop_blocked = Event()
    release_loop = Event()
    request_started = Event()

    class Service:
        def get(self, request, **kwargs):
            request_started.set()
            raise AssertionError("An expired update must not issue an RPC.")

    operation._service = Service()

    async def block_sdk_loop() -> None:
        loop_blocked.set()
        release_loop.wait(timeout=5)

    blocker = channel.run_async(block_sdk_loop())
    assert await asyncio.to_thread(loop_blocked.wait, 5)
    try:
        with pytest.raises(TimeoutError, match="operation update timed out"):
            await operation.update(timeout=timeout, auth_timeout=auth_timeout)
        release_loop.set()
        await blocker
        await asyncio.sleep(0.05)
        assert not request_started.is_set()
    finally:
        release_loop.set()
        await channel.close()


@pytest.mark.asyncio()
async def test_authorized_operation_request_timeout_is_not_an_outer_deadline() -> None:
    """An authorized update may authenticate longer than its request budget."""
    from nebius.aio.channel import Channel
    from nebius.aio.operation import Operation
    from nebius.aio.token.static import Bearer as StaticBearer
    from nebius.api.nebius.common.v1 import Operation as OperationMessage

    channel = Channel(credentials=StaticBearer("token"))
    operation = Operation(
        ".nebius.common.v1.OperationService.Get",
        channel,
        OperationMessage(id="op-independent-auth-clock"),
    )

    async def slow_authorized_update(**kwargs: object) -> None:
        await asyncio.sleep(0.08)

    operation._update_internal = slow_authorized_update  # type: ignore[method-assign]
    try:
        await operation.update(timeout=0.02, auth_timeout=0.5)
    finally:
        await channel.close()


@pytest.mark.asyncio()
@pytest.mark.parametrize("value", (float("nan"), float("inf"), float("-inf")))
@pytest.mark.parametrize("parameter", ("timeout", "auth_timeout"))
async def test_operation_update_rejects_non_finite_timeouts(
    value: float,
    parameter: str,
) -> None:
    """Operation update deadlines require a finite value or ``None``."""
    from nebius.aio.channel import Channel, NoCredentials
    from nebius.aio.operation import Operation
    from nebius.api.nebius.common.v1 import Operation as OperationMessage

    channel = Channel(credentials=NoCredentials())
    operation = Operation(
        ".nebius.common.v1.OperationService.Get",
        channel,
        OperationMessage(id="invalid-timeout"),
    )
    try:
        with pytest.raises(
            ValueError,
            match=f"The {parameter} value must be finite or None",
        ):
            await operation.update(**{parameter: value})
    finally:
        await channel.close()


@pytest.mark.asyncio()
@pytest.mark.parametrize("value", (float("nan"), float("inf"), float("-inf")))
async def test_operation_wait_rejects_non_finite_timeout(value: float) -> None:
    """Overall async wait deadlines require a finite value or ``None``."""
    from nebius.aio.channel import Channel, NoCredentials
    from nebius.aio.operation import Operation
    from nebius.api.nebius.common.v1 import Operation as OperationMessage

    channel = Channel(credentials=NoCredentials())
    operation = Operation(
        ".nebius.common.v1.OperationService.Get",
        channel,
        OperationMessage(id="invalid-wait-timeout"),
    )
    try:
        with pytest.raises(
            ValueError,
            match="The timeout value must be finite or None",
        ):
            await operation.wait(timeout=value)
        with pytest.raises(
            ValueError,
            match="The timeout value must be finite or None",
        ):
            operation.sync_wait(timeout=value)
    finally:
        await channel.close()


@pytest.mark.asyncio()
@pytest.mark.parametrize("method", ("update", "wait"))
async def test_operation_disposes_coroutine_on_submission_rejection(
    method: str,
) -> None:
    """An optional scheduler rejection cannot retain an unstarted coroutine."""
    from inspect import CORO_CLOSED, getcoroutinestate

    from nebius.aio.channel import Channel, NoCredentials
    from nebius.aio.operation import Operation
    from nebius.api.nebius.common.v1 import Operation as OperationMessage

    channel = Channel(credentials=NoCredentials())
    operation = Operation(
        ".nebius.common.v1.OperationService.Get",
        channel,
        OperationMessage(id="rejected-submission"),
    )
    rejection = RuntimeError("The test rejected the operation submission.")
    rejected = []
    original_submit = channel.run_async

    def reject(awaitable):
        rejected.append(awaitable)
        raise rejection

    channel.run_async = reject  # type: ignore[method-assign]
    try:
        operation_call = getattr(operation, method)
        with pytest.raises(RuntimeError) as raised:
            await operation_call()
        assert raised.value is rejection
        assert len(rejected) == 1
        assert getcoroutinestate(rejected[0]) == CORO_CLOSED
    finally:
        channel.run_async = original_submit  # type: ignore[method-assign]
        await channel.close()


@pytest.mark.parametrize(
    ("timeout", "auth_timeout", "authorization_enabled"),
    ((0.01, 5, False), (5, 0.01, True), (0.01, None, False)),
    ids=("request-timeout", "authorization-timeout", "unlimited-auth"),
)
def test_operation_sync_update_uses_applicable_queue_deadline(
    timeout: float,
    auth_timeout: float | None,
    authorization_enabled: bool,
) -> None:
    """Synchronous update uses the request or authorization outer budget."""
    from threading import Event
    from time import monotonic

    from nebius.aio.channel import Channel, NoCredentials
    from nebius.aio.operation import Operation
    from nebius.aio.token.static import Bearer as StaticBearer
    from nebius.api.nebius.common.v1 import Operation as OperationMessage

    credentials = StaticBearer("token") if authorization_enabled else NoCredentials()
    channel = Channel(credentials=credentials)
    operation = Operation(
        ".nebius.common.v1.OperationService.Get",
        channel,
        OperationMessage(id="op-sync-update-timeout"),
    )
    loop_blocked = Event()
    release_loop = Event()
    request_started = Event()

    class Service:
        def get(self, request, **kwargs):
            request_started.set()
            raise AssertionError("An expired synchronous update must not issue an RPC.")

    operation._service = Service()

    async def block_sdk_loop() -> None:
        loop_blocked.set()
        release_loop.wait(timeout=5)

    blocker = channel.run_async(block_sdk_loop())
    assert loop_blocked.wait(timeout=5)
    started = monotonic()
    try:
        with pytest.raises(TimeoutError):
            operation.sync_update(timeout=timeout, auth_timeout=auth_timeout)
        assert monotonic() - started < 0.5
        release_loop.set()
        blocker.result(timeout=5)
        assert not request_started.wait(timeout=0.05)
    finally:
        release_loop.set()
        channel.sync_close(timeout=5)


@pytest.mark.parametrize("method", ("sync_update", "sync_wait"))
def test_sync_operation_deadline_starts_before_run_sync_dispatch(method: str) -> None:
    """A sync operation timeout includes delay before SDK-loop dispatch."""
    from time import sleep

    from nebius.aio.channel import Channel, NoCredentials
    from nebius.aio.operation import Operation
    from nebius.api.nebius.common.v1 import Operation as OperationMessage

    channel = Channel(credentials=NoCredentials())
    operation = Operation(
        ".nebius.common.v1.OperationService.Get",
        channel,
        OperationMessage(id=f"{method}-delayed-dispatch"),
    )
    request_started = False

    class Service:
        """Record an unexpected operation service call."""

        def get(self, request, **kwargs):
            """Reject an RPC that starts after the caller deadline."""
            nonlocal request_started
            request_started = True
            raise AssertionError("An expired operation must not issue an RPC.")

    operation._service = Service()
    original_run_sync = channel.run_sync

    def delay_run_sync(awaitable, timeout=None):
        """Delay SDK dispatch without consuming its cleanup allowance."""
        sleep(0.05)
        return original_run_sync(awaitable, timeout)

    channel.run_sync = delay_run_sync  # type: ignore[method-assign]
    try:
        call = getattr(operation, method)
        arguments = {"timeout": 0.02}
        if method == "sync_wait":
            arguments["interval"] = 0.01
        with pytest.raises(TimeoutError):
            call(**arguments)
        assert not request_started
    finally:
        channel.run_sync = original_run_sync  # type: ignore[method-assign]
        channel.sync_close(timeout=5)


@pytest.mark.parametrize("method", ("sync_update", "sync_wait"))
def test_sync_operation_options_are_snapshotted_before_run_sync(method: str) -> None:
    """Sync operation calls fix nested options on the caller thread."""
    from threading import Event, Thread

    from nebius.aio.authorization.options import OPTION_TYPE, Types
    from nebius.aio.channel import Channel
    from nebius.aio.operation import Operation
    from nebius.aio.token.static import Bearer as StaticBearer
    from nebius.api.google.rpc import Status
    from nebius.api.nebius.common.v1 import Operation as OperationMessage

    channel = Channel(credentials=StaticBearer("token"))
    operation = Operation(
        ".nebius.common.v1.OperationService.Get",
        channel,
        OperationMessage(id=f"{method}-snapshot"),
    )
    run_sync_entered = Event()
    release_run_sync = Event()
    received: list[tuple[list[tuple[str, str]], dict[str, str]]] = []
    run_timeouts: list[float | None] = []
    errors: list[BaseException] = []

    class Response:
        def __init__(self) -> None:
            self._operation = OperationMessage(
                id=f"{method}-snapshot",
                status=Status(code=0),
            )

    class Service:
        def get(self, request, **kwargs):
            received.append((list(kwargs["metadata"]), dict(kwargs["auth_options"])))

            async def result() -> Response:
                return Response()

            return result()

    operation._service = Service()
    original_run_sync = channel.run_sync

    def pause_run_sync(awaitable, timeout=None):
        run_timeouts.append(timeout)
        run_sync_entered.set()
        release_run_sync.wait(timeout=5)
        return original_run_sync(awaitable, timeout)

    channel.run_sync = pause_run_sync  # type: ignore[method-assign]
    metadata = [("x-scope", "before")]
    auth_options = {OPTION_TYPE: Types.DISABLE}

    def invoke() -> None:
        try:
            call = getattr(operation, method)
            arguments = {
                "timeout": 5,
                "metadata": metadata,
                "auth_options": auth_options,
            }
            if method == "sync_update":
                arguments["auth_timeout"] = 9
            else:
                arguments["interval"] = 0.01
            call(**arguments)
        except BaseException as error:
            errors.append(error)

    thread = Thread(target=invoke)
    thread.start()
    assert run_sync_entered.wait(timeout=5)
    metadata[0] = ("x-scope", "after")
    auth_options[OPTION_TYPE] = Types.DEFAULT
    release_run_sync.set()
    thread.join(timeout=5)
    try:
        assert not thread.is_alive()
        assert errors == []
        assert received == [([("x-scope", "before")], {OPTION_TYPE: Types.DISABLE})]
        assert run_timeouts == [5.2]
    finally:
        release_run_sync.set()
        channel.run_sync = original_run_sync  # type: ignore[method-assign]
        channel.sync_close(timeout=5)


def test_authorized_sync_operation_request_timeout_is_not_outer_deadline() -> None:
    """A synchronous authorized update retains its independent request clock."""
    from nebius.aio.channel import Channel
    from nebius.aio.operation import Operation
    from nebius.aio.token.static import Bearer as StaticBearer
    from nebius.api.nebius.common.v1 import Operation as OperationMessage

    channel = Channel(credentials=StaticBearer("token"))
    operation = Operation(
        ".nebius.common.v1.OperationService.Get",
        channel,
        OperationMessage(id="op-sync-independent-auth-clock"),
    )

    async def slow_authorized_update(**kwargs: object) -> None:
        await asyncio.sleep(0.08)

    operation._update_internal = slow_authorized_update  # type: ignore[method-assign]
    try:
        operation.sync_update(timeout=0.02, auth_timeout=0.5)
    finally:
        channel.sync_close(timeout=5)


@pytest.mark.asyncio()
async def test_operation_update_snapshots_mutable_request_options() -> None:
    """Queued update metadata and auth options retain submission values."""
    from threading import Event

    from nebius.aio.channel import Channel, NoCredentials
    from nebius.aio.operation import Operation
    from nebius.api.google.rpc import Status
    from nebius.api.nebius.common.v1 import Operation as OperationMessage

    channel = Channel(credentials=NoCredentials())
    operation = Operation(
        ".nebius.common.v1.OperationService.Get",
        channel,
        OperationMessage(id="op-update-snapshot"),
    )
    loop_blocked = Event()
    release_loop = Event()
    received: list[tuple[list[tuple[str, str]], dict[str, str]]] = []

    class Response:
        def __init__(self) -> None:
            self._operation = OperationMessage(
                id="op-update-snapshot",
                status=Status(code=0),
            )

    class Service:
        def get(self, request, **kwargs):
            received.append((list(kwargs["metadata"]), dict(kwargs["auth_options"])))

            async def result() -> Response:
                return Response()

            return result()

    operation._service = Service()

    async def block_sdk_loop() -> None:
        loop_blocked.set()
        release_loop.wait(timeout=5)

    blocker = channel.run_async(block_sdk_loop())
    assert await asyncio.to_thread(loop_blocked.wait, 5)
    metadata = [("x-scope", "before")]
    auth_options = {"scope": "before"}
    update = asyncio.create_task(
        operation.update(
            timeout=5,
            auth_timeout=5,
            metadata=metadata,
            auth_options=auth_options,
        ),
    )
    await asyncio.sleep(0)
    metadata[0] = ("x-scope", "after")
    auth_options["scope"] = "after"
    try:
        release_loop.set()
        await update
        await blocker
        assert received == [([("x-scope", "before")], {"scope": "before"})]
    finally:
        release_loop.set()
        await channel.close()


@pytest.mark.asyncio()
async def test_operation_wait_snapshots_mutable_poll_options() -> None:
    """Queued wait metadata and auth options retain submission values."""
    from threading import Event

    from nebius.aio.channel import Channel, NoCredentials
    from nebius.aio.operation import Operation
    from nebius.api.google.rpc import Status
    from nebius.api.nebius.common.v1 import Operation as OperationMessage

    channel = Channel(credentials=NoCredentials())
    operation = Operation(
        ".nebius.common.v1.OperationService.Get",
        channel,
        OperationMessage(id="op-wait-snapshot"),
    )
    loop_blocked = Event()
    release_loop = Event()
    received: list[tuple[list[tuple[str, str]], dict[str, str]]] = []

    class Response:
        def __init__(self) -> None:
            self._operation = OperationMessage(
                id="op-wait-snapshot",
                status=Status(code=0),
            )

    class Service:
        def get(self, request, **kwargs):
            received.append((list(kwargs["metadata"]), dict(kwargs["auth_options"])))

            async def result() -> Response:
                return Response()

            return result()

    operation._service = Service()

    async def block_sdk_loop() -> None:
        loop_blocked.set()
        release_loop.wait(timeout=5)

    blocker = channel.run_async(block_sdk_loop())
    assert await asyncio.to_thread(loop_blocked.wait, 5)
    metadata = [("x-scope", "before")]
    auth_options = {"scope": "before"}
    wait = asyncio.create_task(
        operation.wait(
            interval=0.01,
            timeout=5,
            metadata=metadata,
            auth_options=auth_options,
        ),
    )
    await asyncio.sleep(0)
    metadata[0] = ("x-scope", "after")
    auth_options["scope"] = "after"
    try:
        release_loop.set()
        await wait
        await blocker
        assert received == [([("x-scope", "before")], {"scope": "before"})]
    finally:
        release_loop.set()
        await channel.close()


@pytest.mark.asyncio()
async def test_operation_update_preserves_service_timeout_error() -> None:
    """A service TimeoutError is not rewritten as caller deadline expiry."""
    from nebius.aio.channel import Channel, NoCredentials
    from nebius.aio.operation import Operation
    from nebius.api.nebius.common.v1 import Operation as OperationMessage

    channel = Channel(credentials=NoCredentials())
    operation = Operation(
        ".nebius.common.v1.OperationService.Get",
        channel,
        OperationMessage(id="op-update-application-timeout"),
    )
    application_error = TimeoutError("The operation service timed out.")

    class Service:
        def get(self, request, **kwargs):
            async def result():
                raise application_error

            return result()

    operation._service = Service()
    try:
        with pytest.raises(TimeoutError, match="operation service timed out") as raised:
            await operation.update(timeout=5, auth_timeout=5)
        assert raised.value is application_error
    finally:
        await channel.close()


@pytest.mark.asyncio()
async def test_terminal_operation_wait_accepts_zero_timeout() -> None:
    """A terminal operation returns before applying a zero timeout."""
    from nebius.aio.channel import Channel, NoCredentials
    from nebius.aio.operation import Operation
    from nebius.api.google.rpc import Status
    from nebius.api.nebius.common.v1 import Operation as OperationMessage

    channel = Channel(credentials=NoCredentials())
    operation = Operation(
        ".nebius.common.v1.OperationService.Get",
        channel,
        OperationMessage(id="op-terminal", status=Status(code=0)),
    )
    try:
        await operation.wait(timeout=0)
        await operation.wait(timeout=-1)
    finally:
        await channel.close()


@pytest.mark.asyncio()
@pytest.mark.parametrize("interval", [0, -1, float("nan"), float("inf")])
async def test_unfinished_operation_rejects_invalid_poll_interval(
    interval: float,
) -> None:
    """Invalid intervals fail before dispatching an operation-service RPC."""
    from nebius.aio.channel import Channel, NoCredentials
    from nebius.aio.operation import Operation
    from nebius.api.nebius.common.v1 import Operation as OperationMessage

    channel = Channel(credentials=NoCredentials())
    operation = Operation(
        ".nebius.common.v1.OperationService.Get",
        channel,
        OperationMessage(id="op-invalid-interval"),
    )

    class Service:
        def get(self, request, **kwargs):
            raise AssertionError("An invalid interval must fail before polling.")

    operation._service = Service()
    try:
        with pytest.raises(ValueError, match="finite positive"):
            await operation.wait(interval=interval)
    finally:
        await channel.close()
