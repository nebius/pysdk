from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Condition(_message.Message):
    __slots__ = ["type", "status", "last_transition_at", "reason", "severity", "description", "last_transition_error"]
    class Severity(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        NONE: _ClassVar[Condition.Severity]
        INFO: _ClassVar[Condition.Severity]
        ERROR: _ClassVar[Condition.Severity]
    NONE: Condition.Severity
    INFO: Condition.Severity
    ERROR: Condition.Severity
    class Status(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        UNKNOWN: _ClassVar[Condition.Status]
        TRUE: _ClassVar[Condition.Status]
        FALSE: _ClassVar[Condition.Status]
    UNKNOWN: Condition.Status
    TRUE: Condition.Status
    FALSE: Condition.Status
    class TransitionError(_message.Message):
        __slots__ = ["reason", "description"]
        REASON_FIELD_NUMBER: _ClassVar[int]
        DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
        reason: str
        description: str
        def __init__(self, reason: _Optional[str] = ..., description: _Optional[str] = ...) -> None: ...
    TYPE_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    LAST_TRANSITION_AT_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    SEVERITY_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    LAST_TRANSITION_ERROR_FIELD_NUMBER: _ClassVar[int]
    type: str
    status: Condition.Status
    last_transition_at: _timestamp_pb2.Timestamp
    reason: str
    severity: Condition.Severity
    description: str
    last_transition_error: Condition.TransitionError
    def __init__(self, type: _Optional[str] = ..., status: _Optional[_Union[Condition.Status, str]] = ..., last_transition_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., reason: _Optional[str] = ..., severity: _Optional[_Union[Condition.Severity, str]] = ..., description: _Optional[str] = ..., last_transition_error: _Optional[_Union[Condition.TransitionError, _Mapping]] = ...) -> None: ...
