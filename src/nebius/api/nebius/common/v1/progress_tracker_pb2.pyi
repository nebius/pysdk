from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ProgressTracker(_message.Message):
    __slots__ = ["description", "started_at", "estimated_finished_at", "finished_at", "work_done", "steps"]
    class WorkDone(_message.Message):
        __slots__ = ["total_tick_count", "done_tick_count"]
        TOTAL_TICK_COUNT_FIELD_NUMBER: _ClassVar[int]
        DONE_TICK_COUNT_FIELD_NUMBER: _ClassVar[int]
        total_tick_count: int
        done_tick_count: int
        def __init__(self, total_tick_count: _Optional[int] = ..., done_tick_count: _Optional[int] = ...) -> None: ...
    class Step(_message.Message):
        __slots__ = ["description", "started_at", "finished_at", "work_done"]
        DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
        STARTED_AT_FIELD_NUMBER: _ClassVar[int]
        FINISHED_AT_FIELD_NUMBER: _ClassVar[int]
        WORK_DONE_FIELD_NUMBER: _ClassVar[int]
        description: str
        started_at: _timestamp_pb2.Timestamp
        finished_at: _timestamp_pb2.Timestamp
        work_done: ProgressTracker.WorkDone
        def __init__(self, description: _Optional[str] = ..., started_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., finished_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., work_done: _Optional[_Union[ProgressTracker.WorkDone, _Mapping]] = ...) -> None: ...
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    STARTED_AT_FIELD_NUMBER: _ClassVar[int]
    ESTIMATED_FINISHED_AT_FIELD_NUMBER: _ClassVar[int]
    FINISHED_AT_FIELD_NUMBER: _ClassVar[int]
    WORK_DONE_FIELD_NUMBER: _ClassVar[int]
    STEPS_FIELD_NUMBER: _ClassVar[int]
    description: str
    started_at: _timestamp_pb2.Timestamp
    estimated_finished_at: _timestamp_pb2.Timestamp
    finished_at: _timestamp_pb2.Timestamp
    work_done: ProgressTracker.WorkDone
    steps: _containers.RepeatedCompositeFieldContainer[ProgressTracker.Step]
    def __init__(self, description: _Optional[str] = ..., started_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., estimated_finished_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., finished_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., work_done: _Optional[_Union[ProgressTracker.WorkDone, _Mapping]] = ..., steps: _Optional[_Iterable[_Union[ProgressTracker.Step, _Mapping]]] = ...) -> None: ...
