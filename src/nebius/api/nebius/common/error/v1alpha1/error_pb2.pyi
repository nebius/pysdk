from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.common.error.v1alpha1 import common_errors_pb2 as _common_errors_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ServiceError(_message.Message):
    __slots__ = ["service", "code", "bad_request", "bad_resource_state", "resource_not_found", "resource_already_exists", "out_of_range", "permission_denied", "resource_conflict", "operation_aborted", "too_many_requests", "quota_failure", "internal_error", "retry_type"]
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
    INTERNAL_ERROR_FIELD_NUMBER: _ClassVar[int]
    RETRY_TYPE_FIELD_NUMBER: _ClassVar[int]
    service: str
    code: str
    bad_request: _common_errors_pb2.BadRequest
    bad_resource_state: _common_errors_pb2.BadResourceState
    resource_not_found: _common_errors_pb2.ResourceNotFound
    resource_already_exists: _common_errors_pb2.ResourceAlreadyExists
    out_of_range: _common_errors_pb2.OutOfRange
    permission_denied: _common_errors_pb2.PermissionDenied
    resource_conflict: _common_errors_pb2.ResourceConflict
    operation_aborted: _common_errors_pb2.OperationAborted
    too_many_requests: _common_errors_pb2.TooManyRequests
    quota_failure: _common_errors_pb2.QuotaFailure
    internal_error: _common_errors_pb2.InternalError
    retry_type: ServiceError.RetryType
    def __init__(self, service: _Optional[str] = ..., code: _Optional[str] = ..., bad_request: _Optional[_Union[_common_errors_pb2.BadRequest, _Mapping]] = ..., bad_resource_state: _Optional[_Union[_common_errors_pb2.BadResourceState, _Mapping]] = ..., resource_not_found: _Optional[_Union[_common_errors_pb2.ResourceNotFound, _Mapping]] = ..., resource_already_exists: _Optional[_Union[_common_errors_pb2.ResourceAlreadyExists, _Mapping]] = ..., out_of_range: _Optional[_Union[_common_errors_pb2.OutOfRange, _Mapping]] = ..., permission_denied: _Optional[_Union[_common_errors_pb2.PermissionDenied, _Mapping]] = ..., resource_conflict: _Optional[_Union[_common_errors_pb2.ResourceConflict, _Mapping]] = ..., operation_aborted: _Optional[_Union[_common_errors_pb2.OperationAborted, _Mapping]] = ..., too_many_requests: _Optional[_Union[_common_errors_pb2.TooManyRequests, _Mapping]] = ..., quota_failure: _Optional[_Union[_common_errors_pb2.QuotaFailure, _Mapping]] = ..., internal_error: _Optional[_Union[_common_errors_pb2.InternalError, _Mapping]] = ..., retry_type: _Optional[_Union[ServiceError.RetryType, str]] = ...) -> None: ...
