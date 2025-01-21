from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ServiceError(_message.Message):
    __slots__ = ["service", "code", "bad_request", "bad_resource_state", "resource_not_found", "resource_already_exists", "out_of_range", "permission_denied", "resource_conflict", "operation_aborted", "too_many_requests", "quota_failure", "not_enough_resources", "internal_error", "retry_type"]
    class RetryType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        UNSPECIFIED: _ClassVar[ServiceError.RetryType]
        CALL: _ClassVar[ServiceError.RetryType]
        UNIT_OF_WORK: _ClassVar[ServiceError.RetryType]
        NOTHING: _ClassVar[ServiceError.RetryType]
    UNSPECIFIED: ServiceError.RetryType
    CALL: ServiceError.RetryType
    UNIT_OF_WORK: ServiceError.RetryType
    NOTHING: ServiceError.RetryType
    SERVICE_FIELD_NUMBER: _ClassVar[int]
    CODE_FIELD_NUMBER: _ClassVar[int]
    BAD_REQUEST_FIELD_NUMBER: _ClassVar[int]
    BAD_RESOURCE_STATE_FIELD_NUMBER: _ClassVar[int]
    RESOURCE_NOT_FOUND_FIELD_NUMBER: _ClassVar[int]
    RESOURCE_ALREADY_EXISTS_FIELD_NUMBER: _ClassVar[int]
    OUT_OF_RANGE_FIELD_NUMBER: _ClassVar[int]
    PERMISSION_DENIED_FIELD_NUMBER: _ClassVar[int]
    RESOURCE_CONFLICT_FIELD_NUMBER: _ClassVar[int]
    OPERATION_ABORTED_FIELD_NUMBER: _ClassVar[int]
    TOO_MANY_REQUESTS_FIELD_NUMBER: _ClassVar[int]
    QUOTA_FAILURE_FIELD_NUMBER: _ClassVar[int]
    NOT_ENOUGH_RESOURCES_FIELD_NUMBER: _ClassVar[int]
    INTERNAL_ERROR_FIELD_NUMBER: _ClassVar[int]
    RETRY_TYPE_FIELD_NUMBER: _ClassVar[int]
    service: str
    code: str
    bad_request: BadRequest
    bad_resource_state: BadResourceState
    resource_not_found: ResourceNotFound
    resource_already_exists: ResourceAlreadyExists
    out_of_range: OutOfRange
    permission_denied: PermissionDenied
    resource_conflict: ResourceConflict
    operation_aborted: OperationAborted
    too_many_requests: TooManyRequests
    quota_failure: QuotaFailure
    not_enough_resources: NotEnoughResources
    internal_error: InternalError
    retry_type: ServiceError.RetryType
    def __init__(self, service: _Optional[str] = ..., code: _Optional[str] = ..., bad_request: _Optional[_Union[BadRequest, _Mapping]] = ..., bad_resource_state: _Optional[_Union[BadResourceState, _Mapping]] = ..., resource_not_found: _Optional[_Union[ResourceNotFound, _Mapping]] = ..., resource_already_exists: _Optional[_Union[ResourceAlreadyExists, _Mapping]] = ..., out_of_range: _Optional[_Union[OutOfRange, _Mapping]] = ..., permission_denied: _Optional[_Union[PermissionDenied, _Mapping]] = ..., resource_conflict: _Optional[_Union[ResourceConflict, _Mapping]] = ..., operation_aborted: _Optional[_Union[OperationAborted, _Mapping]] = ..., too_many_requests: _Optional[_Union[TooManyRequests, _Mapping]] = ..., quota_failure: _Optional[_Union[QuotaFailure, _Mapping]] = ..., not_enough_resources: _Optional[_Union[NotEnoughResources, _Mapping]] = ..., internal_error: _Optional[_Union[InternalError, _Mapping]] = ..., retry_type: _Optional[_Union[ServiceError.RetryType, str]] = ...) -> None: ...

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

class NotEnoughResources(_message.Message):
    __slots__ = ["violations"]
    class Violation(_message.Message):
        __slots__ = ["resource_type", "message", "requested"]
        RESOURCE_TYPE_FIELD_NUMBER: _ClassVar[int]
        MESSAGE_FIELD_NUMBER: _ClassVar[int]
        REQUESTED_FIELD_NUMBER: _ClassVar[int]
        resource_type: str
        message: str
        requested: str
        def __init__(self, resource_type: _Optional[str] = ..., message: _Optional[str] = ..., requested: _Optional[str] = ...) -> None: ...
    VIOLATIONS_FIELD_NUMBER: _ClassVar[int]
    violations: _containers.RepeatedCompositeFieldContainer[NotEnoughResources.Violation]
    def __init__(self, violations: _Optional[_Iterable[_Union[NotEnoughResources.Violation, _Mapping]]] = ...) -> None: ...
