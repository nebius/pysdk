from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.billing.v1alpha1 import billing_report_exporter_pb2 as _billing_report_exporter_pb2
from nebius.api.nebius.common.v1 import error_pb2 as _error_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class OneTimeExportState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = []
    ONE_TIME_EXPORT_STATE_UNSPECIFIED: _ClassVar[OneTimeExportState]
    ONE_TIME_EXPORT_STATE_SCHEDULED: _ClassVar[OneTimeExportState]
    ONE_TIME_EXPORT_STATE_RUNNING: _ClassVar[OneTimeExportState]
    ONE_TIME_EXPORT_STATE_SUCCESS: _ClassVar[OneTimeExportState]
    ONE_TIME_EXPORT_STATE_FAILED: _ClassVar[OneTimeExportState]
    ONE_TIME_EXPORT_STATE_ARCHIVED: _ClassVar[OneTimeExportState]
ONE_TIME_EXPORT_STATE_UNSPECIFIED: OneTimeExportState
ONE_TIME_EXPORT_STATE_SCHEDULED: OneTimeExportState
ONE_TIME_EXPORT_STATE_RUNNING: OneTimeExportState
ONE_TIME_EXPORT_STATE_SUCCESS: OneTimeExportState
ONE_TIME_EXPORT_STATE_FAILED: OneTimeExportState
ONE_TIME_EXPORT_STATE_ARCHIVED: OneTimeExportState

class OneTimeExport(_message.Message):
    __slots__ = ["metadata", "spec", "status"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: OneTimeExportSpec
    status: OneTimeExportStatus
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[OneTimeExportSpec, _Mapping]] = ..., status: _Optional[_Union[OneTimeExportStatus, _Mapping]] = ...) -> None: ...

class OneTimeExportSpec(_message.Message):
    __slots__ = ["format", "start_period", "end_period"]
    FORMAT_FIELD_NUMBER: _ClassVar[int]
    START_PERIOD_FIELD_NUMBER: _ClassVar[int]
    END_PERIOD_FIELD_NUMBER: _ClassVar[int]
    format: _billing_report_exporter_pb2.ExportFormat
    start_period: str
    end_period: str
    def __init__(self, format: _Optional[_Union[_billing_report_exporter_pb2.ExportFormat, str]] = ..., start_period: _Optional[str] = ..., end_period: _Optional[str] = ...) -> None: ...

class OneTimeExportStatus(_message.Message):
    __slots__ = ["state", "download_url", "expires_at", "state_details"]
    STATE_FIELD_NUMBER: _ClassVar[int]
    DOWNLOAD_URL_FIELD_NUMBER: _ClassVar[int]
    EXPIRES_AT_FIELD_NUMBER: _ClassVar[int]
    STATE_DETAILS_FIELD_NUMBER: _ClassVar[int]
    state: OneTimeExportState
    download_url: str
    expires_at: _timestamp_pb2.Timestamp
    state_details: OneTimeExportStateDetails
    def __init__(self, state: _Optional[_Union[OneTimeExportState, str]] = ..., download_url: _Optional[str] = ..., expires_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., state_details: _Optional[_Union[OneTimeExportStateDetails, _Mapping]] = ...) -> None: ...

class OneTimeExportStateDetails(_message.Message):
    __slots__ = ["error"]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    error: _error_pb2.ServiceError
    def __init__(self, error: _Optional[_Union[_error_pb2.ServiceError, _Mapping]] = ...) -> None: ...
