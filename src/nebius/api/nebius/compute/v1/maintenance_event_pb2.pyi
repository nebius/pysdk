from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class MaintenanceEventStatus(_message.Message):
    __slots__ = ("maintenance_id", "state", "operation_id", "created_at", "finished_at", "sla_deadline_ts", "support_center_ticket_id")
    class State(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        STATE_UNSPECIFIED: _ClassVar[MaintenanceEventStatus.State]
        STATE_PENDING: _ClassVar[MaintenanceEventStatus.State]
        STATE_IN_PROGRESS: _ClassVar[MaintenanceEventStatus.State]
        STATE_COMPLETED: _ClassVar[MaintenanceEventStatus.State]
        STATE_CANCELLED: _ClassVar[MaintenanceEventStatus.State]
    STATE_UNSPECIFIED: MaintenanceEventStatus.State
    STATE_PENDING: MaintenanceEventStatus.State
    STATE_IN_PROGRESS: MaintenanceEventStatus.State
    STATE_COMPLETED: MaintenanceEventStatus.State
    STATE_CANCELLED: MaintenanceEventStatus.State
    MAINTENANCE_ID_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    OPERATION_ID_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    FINISHED_AT_FIELD_NUMBER: _ClassVar[int]
    SLA_DEADLINE_TS_FIELD_NUMBER: _ClassVar[int]
    SUPPORT_CENTER_TICKET_ID_FIELD_NUMBER: _ClassVar[int]
    maintenance_id: str
    state: MaintenanceEventStatus.State
    operation_id: str
    created_at: _timestamp_pb2.Timestamp
    finished_at: _timestamp_pb2.Timestamp
    sla_deadline_ts: _timestamp_pb2.Timestamp
    support_center_ticket_id: str
    def __init__(self, maintenance_id: _Optional[str] = ..., state: _Optional[_Union[MaintenanceEventStatus.State, str]] = ..., operation_id: _Optional[str] = ..., created_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., finished_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., sla_deadline_ts: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., support_center_ticket_id: _Optional[str] = ...) -> None: ...
