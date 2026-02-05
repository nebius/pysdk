# type: ignore
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest


@pytest.mark.asyncio
async def test_operation_progress_tracker_updates() -> None:
    import grpc.aio
    from google.protobuf.timestamp_pb2 import Timestamp
    from google.rpc.status_pb2 import Status as StatusPb

    import nebius.api.nebius.common.v1.operation_pb2 as operation_pb2
    import nebius.api.nebius.common.v1.progress_tracker_pb2 as progress_pb2
    from nebius.aio.channel import Channel, NoCredentials
    from nebius.aio.operation import Operation
    from nebius.api.nebius.common.v1.operation_service_pb2_grpc import (
        OperationServiceServicer,
        add_OperationServiceServicer_to_server,
    )
    from nebius.base.options import INSECURE
    from nebius.base.protos.well_known import local_timezone

    def ts(dt: datetime) -> Timestamp:
        stamp = Timestamp()
        stamp.FromDatetime(dt.astimezone(timezone.utc))
        return stamp

    def to_local(dt: datetime) -> datetime:
        return dt.astimezone(local_timezone)

    def op_with_tracker(
        tracker: progress_pb2.ProgressTracker | None = None,
        *,
        status: StatusPb | None = None,
        finished_at: datetime | None = None,
    ) -> operation_pb2.Operation:
        op = operation_pb2.Operation(id="op-1")
        if tracker is not None:
            op.progress_tracker.CopyFrom(tracker)
        if status is not None:
            op.status.CopyFrom(status)
        if finished_at is not None:
            op.finished_at.CopyFrom(ts(finished_at))
        return op

    base_now = datetime.now(timezone.utc)
    started_past = base_now - timedelta(seconds=120)
    started_now = base_now - timedelta(seconds=5)
    started_future = base_now + timedelta(seconds=60)
    estimate_future = base_now + timedelta(seconds=120)
    estimate_past = base_now - timedelta(seconds=10)
    estimate_updated = base_now + timedelta(seconds=30)
    finished_time = base_now + timedelta(seconds=1)

    op0 = operation_pb2.Operation(id="op-1")

    op1 = op_with_tracker(progress_pb2.ProgressTracker())

    op2 = op_with_tracker(
        progress_pb2.ProgressTracker(
            description="phase-1",
            started_at=ts(started_now),
            work_done=progress_pb2.ProgressTracker.WorkDone(
                total_tick_count=10,
                done_tick_count=2,
            ),
        )
    )

    op3 = op_with_tracker(
        progress_pb2.ProgressTracker(
            description="phase-1-est",
            started_at=ts(started_future),
            estimated_finished_at=ts(estimate_future),
        )
    )

    step_a = progress_pb2.ProgressTracker.Step(
        description="step-a",
        started_at=ts(started_past),
        work_done=progress_pb2.ProgressTracker.WorkDone(
            total_tick_count=4,
            done_tick_count=1,
        ),
    )
    step_b = progress_pb2.ProgressTracker.Step(
        description="step-b",
        started_at=ts(started_past),
    )
    tracker4 = progress_pb2.ProgressTracker(
        description="phase-2",
        started_at=ts(started_past),
        estimated_finished_at=ts(estimate_past),
    )
    tracker4.steps.extend([step_a, step_b])
    op4 = op_with_tracker(tracker4)

    step_a_updated = progress_pb2.ProgressTracker.Step(
        description="step-a",
        started_at=ts(started_past),
        finished_at=ts(base_now - timedelta(seconds=5)),
        work_done=progress_pb2.ProgressTracker.WorkDone(
            total_tick_count=4,
            done_tick_count=4,
        ),
    )
    step_b_updated = progress_pb2.ProgressTracker.Step(
        description="step-b updated",
        started_at=ts(started_past),
        work_done=progress_pb2.ProgressTracker.WorkDone(
            total_tick_count=2,
            done_tick_count=1,
        ),
    )
    tracker5 = progress_pb2.ProgressTracker(
        description="phase-2 updated",
        started_at=ts(started_past),
        estimated_finished_at=ts(estimate_updated),
        work_done=progress_pb2.ProgressTracker.WorkDone(
            total_tick_count=10,
            done_tick_count=7,
        ),
    )
    tracker5.steps.extend([step_a_updated, step_b_updated])
    op5 = op_with_tracker(tracker5)

    step_a_done = progress_pb2.ProgressTracker.Step(
        description="step-a",
        started_at=ts(started_past),
        finished_at=ts(finished_time),
        work_done=progress_pb2.ProgressTracker.WorkDone(
            total_tick_count=4,
            done_tick_count=4,
        ),
    )
    step_b_done = progress_pb2.ProgressTracker.Step(
        description="step-b updated",
        started_at=ts(started_past),
        finished_at=ts(finished_time),
        work_done=progress_pb2.ProgressTracker.WorkDone(
            total_tick_count=2,
            done_tick_count=2,
        ),
    )
    tracker6 = progress_pb2.ProgressTracker(
        description="done",
        started_at=ts(started_past),
        finished_at=ts(finished_time),
        work_done=progress_pb2.ProgressTracker.WorkDone(
            total_tick_count=10,
            done_tick_count=10,
        ),
    )
    tracker6.steps.extend([step_a_done, step_b_done])
    op6 = op_with_tracker(tracker6, status=StatusPb(code=0), finished_at=finished_time)

    class MockOperationService(OperationServiceServicer):
        def __init__(self, responses: list[operation_pb2.Operation]) -> None:
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
    add_OperationServiceServicer_to_server(
        MockOperationService([op1, op2, op3, op4, op5, op6]),
        srv,
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
    import nebius.api.nebius.common.v1alpha1.operation_pb2 as operation_pb2
    from nebius.aio.channel import Channel, NoCredentials
    from nebius.aio.operation import Operation
    from nebius.base.options import INSECURE

    channel = None
    try:
        channel = Channel(
            domain="localhost",
            options=[(INSECURE, True)],
            credentials=NoCredentials(),
        )
        op = operation_pb2.Operation(id="mlflow-op-1")
        operation = Operation(
            ".nebius.msp.mlflow.v1alpha1.ClusterService.Create",
            channel,
            op,
        )
        assert operation.progress_tracker() is None
    finally:
        if channel is not None:
            await channel.close()
