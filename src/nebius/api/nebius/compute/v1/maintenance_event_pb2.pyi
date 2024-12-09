from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class MaintenanceEventStatus(_message.Message):
    __slots__ = ("maintenance_id", "state", "operation_id", "finished_at", "sla_deadline_ts", "ticket_id")
    class State(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        PENDING: _ClassVar[MaintenanceEventStatus.State]
        IN_PROGRESS: _ClassVar[MaintenanceEventStatus.State]
        COMPLETED: _ClassVar[MaintenanceEventStatus.State]
        CANCELLED: _ClassVar[MaintenanceEventStatus.State]
    PENDING: MaintenanceEventStatus.State
    IN_PROGRESS: MaintenanceEventStatus.State
    COMPLETED: MaintenanceEventStatus.State
    CANCELLED: MaintenanceEventStatus.State
    MAINTENANCE_ID_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    OPERATION_ID_FIELD_NUMBER: _ClassVar[int]
    FINISHED_AT_FIELD_NUMBER: _ClassVar[int]
    SLA_DEADLINE_TS_FIELD_NUMBER: _ClassVar[int]
    TICKET_ID_FIELD_NUMBER: _ClassVar[int]
    maintenance_id: str
    state: MaintenanceEventStatus.State
    operation_id: str
    finished_at: _timestamp_pb2.Timestamp
    sla_deadline_ts: _timestamp_pb2.Timestamp
    ticket_id: str
    def __init__(self, maintenance_id: _Optional[str] = ..., state: _Optional[_Union[MaintenanceEventStatus.State, str]] = ..., operation_id: _Optional[str] = ..., finished_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., sla_deadline_ts: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., ticket_id: _Optional[str] = ...) -> None: ...
