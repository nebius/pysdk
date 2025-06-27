from google.protobuf import timestamp_pb2 as _timestamp_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class MaintenanceEvent(_message.Message):
    __slots__ = ["id", "spec", "status"]
    ID_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    id: str
    spec: MaintenanceEventSpec
    status: MaintenanceEventStatus
    def __init__(self, id: _Optional[str] = ..., spec: _Optional[_Union[MaintenanceEventSpec, _Mapping]] = ..., status: _Optional[_Union[MaintenanceEventStatus, _Mapping]] = ...) -> None: ...

class MaintenanceEventSpec(_message.Message):
    __slots__ = ["is_planned"]
    IS_PLANNED_FIELD_NUMBER: _ClassVar[int]
    is_planned: bool
    def __init__(self, is_planned: bool = ...) -> None: ...

class MaintenanceEventStatus(_message.Message):
    __slots__ = ["maintenance_id", "created_at", "finished_at", "sla_deadline_ts", "support_center_ticket_id"]
    MAINTENANCE_ID_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    FINISHED_AT_FIELD_NUMBER: _ClassVar[int]
    SLA_DEADLINE_TS_FIELD_NUMBER: _ClassVar[int]
    SUPPORT_CENTER_TICKET_ID_FIELD_NUMBER: _ClassVar[int]
    maintenance_id: str
    created_at: _timestamp_pb2.Timestamp
    finished_at: _timestamp_pb2.Timestamp
    sla_deadline_ts: _timestamp_pb2.Timestamp
    support_center_ticket_id: str
    def __init__(self, maintenance_id: _Optional[str] = ..., created_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., finished_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., sla_deadline_ts: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., support_center_ticket_id: _Optional[str] = ...) -> None: ...
