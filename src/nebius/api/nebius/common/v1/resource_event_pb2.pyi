from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.rpc import status_pb2 as _status_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ResourceEvent(_message.Message):
    __slots__ = ["occurred_at", "level", "code", "message", "error"]
    class Level(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        UNSPECIFIED: _ClassVar[ResourceEvent.Level]
        DEBUG: _ClassVar[ResourceEvent.Level]
        INFO: _ClassVar[ResourceEvent.Level]
        WARN: _ClassVar[ResourceEvent.Level]
        ERROR: _ClassVar[ResourceEvent.Level]
    UNSPECIFIED: ResourceEvent.Level
    DEBUG: ResourceEvent.Level
    INFO: ResourceEvent.Level
    WARN: ResourceEvent.Level
    ERROR: ResourceEvent.Level
    OCCURRED_AT_FIELD_NUMBER: _ClassVar[int]
    LEVEL_FIELD_NUMBER: _ClassVar[int]
    CODE_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    occurred_at: _timestamp_pb2.Timestamp
    level: ResourceEvent.Level
    code: str
    message: str
    error: _status_pb2.Status
    def __init__(self, occurred_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., level: _Optional[_Union[ResourceEvent.Level, str]] = ..., code: _Optional[str] = ..., message: _Optional[str] = ..., error: _Optional[_Union[_status_pb2.Status, _Mapping]] = ...) -> None: ...

class RecurrentResourceEvent(_message.Message):
    __slots__ = ["first_occurred_at", "last_occurrence", "occurrence_count"]
    FIRST_OCCURRED_AT_FIELD_NUMBER: _ClassVar[int]
    LAST_OCCURRENCE_FIELD_NUMBER: _ClassVar[int]
    OCCURRENCE_COUNT_FIELD_NUMBER: _ClassVar[int]
    first_occurred_at: _timestamp_pb2.Timestamp
    last_occurrence: ResourceEvent
    occurrence_count: int
    def __init__(self, first_occurred_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., last_occurrence: _Optional[_Union[ResourceEvent, _Mapping]] = ..., occurrence_count: _Optional[int] = ...) -> None: ...
