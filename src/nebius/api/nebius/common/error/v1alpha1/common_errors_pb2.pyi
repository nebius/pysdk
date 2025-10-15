from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class BadRequest(_message.Message):
    __slots__ = ["violations"]
    class Violation(_message.Message):
        __slots__ = ["field", "message"]
        FIELD_FIELD_NUMBER: _ClassVar[int]
        MESSAGE_FIELD_NUMBER: _ClassVar[int]
        field: str
        message: str
        def __init__(self, field: _Optional[str] = ..., message: _Optional[str] = ...) -> None: ...
    VIOLATIONS_FIELD_NUMBER: _ClassVar[int]
    violations: _containers.RepeatedCompositeFieldContainer[BadRequest.Violation]
    def __init__(self, violations: _Optional[_Iterable[_Union[BadRequest.Violation, _Mapping]]] = ...) -> None: ...

class BadResourceState(_message.Message):
    __slots__ = ["resource_id", "message"]
    RESOURCE_ID_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    resource_id: str
    message: str
    def __init__(self, resource_id: _Optional[str] = ..., message: _Optional[str] = ...) -> None: ...

class ResourceNotFound(_message.Message):
    __slots__ = ["resource_id"]
    RESOURCE_ID_FIELD_NUMBER: _ClassVar[int]
    resource_id: str
    def __init__(self, resource_id: _Optional[str] = ...) -> None: ...

class ResourceAlreadyExists(_message.Message):
    __slots__ = ["resource_id"]
    RESOURCE_ID_FIELD_NUMBER: _ClassVar[int]
    resource_id: str
    def __init__(self, resource_id: _Optional[str] = ...) -> None: ...

class ResourceConflict(_message.Message):
    __slots__ = ["resource_id", "message"]
    RESOURCE_ID_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    resource_id: str
    message: str
    def __init__(self, resource_id: _Optional[str] = ..., message: _Optional[str] = ...) -> None: ...

class OperationAborted(_message.Message):
    __slots__ = ["operation_id", "aborted_by_operation_id", "resource_id"]
    OPERATION_ID_FIELD_NUMBER: _ClassVar[int]
    ABORTED_BY_OPERATION_ID_FIELD_NUMBER: _ClassVar[int]
    RESOURCE_ID_FIELD_NUMBER: _ClassVar[int]
    operation_id: str
    aborted_by_operation_id: str
    resource_id: str
    def __init__(self, operation_id: _Optional[str] = ..., aborted_by_operation_id: _Optional[str] = ..., resource_id: _Optional[str] = ...) -> None: ...

class OutOfRange(_message.Message):
    __slots__ = ["requested", "limit"]
    REQUESTED_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    requested: str
    limit: str
    def __init__(self, requested: _Optional[str] = ..., limit: _Optional[str] = ...) -> None: ...

class PermissionDenied(_message.Message):
    __slots__ = ["resource_id"]
    RESOURCE_ID_FIELD_NUMBER: _ClassVar[int]
    resource_id: str
    def __init__(self, resource_id: _Optional[str] = ...) -> None: ...

class InternalError(_message.Message):
    __slots__ = ["request_id", "trace_id"]
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    TRACE_ID_FIELD_NUMBER: _ClassVar[int]
    request_id: str
    trace_id: str
    def __init__(self, request_id: _Optional[str] = ..., trace_id: _Optional[str] = ...) -> None: ...

class TooManyRequests(_message.Message):
    __slots__ = ["violation"]
    VIOLATION_FIELD_NUMBER: _ClassVar[int]
    violation: str
    def __init__(self, violation: _Optional[str] = ...) -> None: ...

class QuotaFailure(_message.Message):
    __slots__ = ["violations"]
    class Violation(_message.Message):
        __slots__ = ["quota", "message", "limit", "requested"]
        QUOTA_FIELD_NUMBER: _ClassVar[int]
        MESSAGE_FIELD_NUMBER: _ClassVar[int]
        LIMIT_FIELD_NUMBER: _ClassVar[int]
        REQUESTED_FIELD_NUMBER: _ClassVar[int]
        quota: str
        message: str
        limit: str
        requested: str
        def __init__(self, quota: _Optional[str] = ..., message: _Optional[str] = ..., limit: _Optional[str] = ..., requested: _Optional[str] = ...) -> None: ...
    VIOLATIONS_FIELD_NUMBER: _ClassVar[int]
    violations: _containers.RepeatedCompositeFieldContainer[QuotaFailure.Violation]
    def __init__(self, violations: _Optional[_Iterable[_Union[QuotaFailure.Violation, _Mapping]]] = ...) -> None: ...
