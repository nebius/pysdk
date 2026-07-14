# type: ignore
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest


@pytest.mark.asyncio
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
        )
    )

    op3 = op_with_tracker(
        ProgressTracker(
            description="phase-1-est",
            started_at=started_future,
            estimated_finished_at=estimate_future,
        )
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


@pytest.mark.asyncio
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
