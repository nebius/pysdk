from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class State(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = []
    STATE_UNSPECIFIED: _ClassVar[State]
    STATE_SCHEDULED: _ClassVar[State]
    STATE_IN_PROGRESS: _ClassVar[State]
    STATE_FINISHED: _ClassVar[State]
    STATE_ERROR: _ClassVar[State]
    STATE_CANCELLED: _ClassVar[State]
STATE_UNSPECIFIED: State
STATE_SCHEDULED: State
STATE_IN_PROGRESS: State
STATE_FINISHED: State
STATE_ERROR: State
STATE_CANCELLED: State

class Maintenance(_message.Message):
    __slots__ = ["metadata", "spec", "status"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: MaintenanceSpec
    status: MaintenanceStatus
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[MaintenanceSpec, _Mapping]] = ..., status: _Optional[_Union[MaintenanceStatus, _Mapping]] = ...) -> None: ...

class MaintenanceSpec(_message.Message):
    __slots__ = ["scheduled_at"]
    SCHEDULED_AT_FIELD_NUMBER: _ClassVar[int]
    scheduled_at: _timestamp_pb2.Timestamp
    def __init__(self, scheduled_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class MaintenanceStatus(_message.Message):
    __slots__ = ["affected_resources", "started_at", "finished_at", "state", "reschedulable"]
    AFFECTED_RESOURCES_FIELD_NUMBER: _ClassVar[int]
    STARTED_AT_FIELD_NUMBER: _ClassVar[int]
    FINISHED_AT_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    RESCHEDULABLE_FIELD_NUMBER: _ClassVar[int]
    affected_resources: _containers.RepeatedCompositeFieldContainer[Resource]
    started_at: _timestamp_pb2.Timestamp
    finished_at: _timestamp_pb2.Timestamp
    state: State
    reschedulable: bool
    def __init__(self, affected_resources: _Optional[_Iterable[_Union[Resource, _Mapping]]] = ..., started_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., finished_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., state: _Optional[_Union[State, str]] = ..., reschedulable: bool = ...) -> None: ...

class Resource(_message.Message):
    __slots__ = ["id", "parent_id"]
    ID_FIELD_NUMBER: _ClassVar[int]
    PARENT_ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    parent_id: str
    def __init__(self, id: _Optional[str] = ..., parent_id: _Optional[str] = ...) -> None: ...
