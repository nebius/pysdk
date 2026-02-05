from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.audit.v2 import audit_event_service_pb2 as _audit_event_service_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class AuditEventExportState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = []
    AUDIT_EVENT_EXPORT_STATE_UNSPECIFIED: _ClassVar[AuditEventExportState]
    AUDIT_EVENT_EXPORT_STATE_RUNNING: _ClassVar[AuditEventExportState]
    AUDIT_EVENT_EXPORT_STATE_CANCELED: _ClassVar[AuditEventExportState]
    AUDIT_EVENT_EXPORT_STATE_DONE: _ClassVar[AuditEventExportState]
    AUDIT_EVENT_EXPORT_STATE_FAILED: _ClassVar[AuditEventExportState]
AUDIT_EVENT_EXPORT_STATE_UNSPECIFIED: AuditEventExportState
AUDIT_EVENT_EXPORT_STATE_RUNNING: AuditEventExportState
AUDIT_EVENT_EXPORT_STATE_CANCELED: AuditEventExportState
AUDIT_EVENT_EXPORT_STATE_DONE: AuditEventExportState
AUDIT_EVENT_EXPORT_STATE_FAILED: AuditEventExportState

class AuditEventExport(_message.Message):
    __slots__ = ["metadata", "spec", "status"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: AuditEventExportSpec
    status: AuditEventExportStatus
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[AuditEventExportSpec, _Mapping]] = ..., status: _Optional[_Union[AuditEventExportStatus, _Mapping]] = ...) -> None: ...

class AuditEventExportSpec(_message.Message):
    __slots__ = ["params", "nebius_object_storage"]
    PARAMS_FIELD_NUMBER: _ClassVar[int]
    NEBIUS_OBJECT_STORAGE_FIELD_NUMBER: _ClassVar[int]
    params: AuditEventExportParams
    nebius_object_storage: NebiusObjectStorageDestination
    def __init__(self, params: _Optional[_Union[AuditEventExportParams, _Mapping]] = ..., nebius_object_storage: _Optional[_Union[NebiusObjectStorageDestination, _Mapping]] = ...) -> None: ...

class NebiusObjectStorageDestination(_message.Message):
    __slots__ = ["object_prefix", "bucket_by_id"]
    OBJECT_PREFIX_FIELD_NUMBER: _ClassVar[int]
    BUCKET_BY_ID_FIELD_NUMBER: _ClassVar[int]
    object_prefix: str
    bucket_by_id: BucketById
    def __init__(self, object_prefix: _Optional[str] = ..., bucket_by_id: _Optional[_Union[BucketById, _Mapping]] = ...) -> None: ...

class BucketById(_message.Message):
    __slots__ = ["id"]
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class AuditEventExportParams(_message.Message):
    __slots__ = ["to", "filter", "event_type"]
    FROM_FIELD_NUMBER: _ClassVar[int]
    TO_FIELD_NUMBER: _ClassVar[int]
    FILTER_FIELD_NUMBER: _ClassVar[int]
    EVENT_TYPE_FIELD_NUMBER: _ClassVar[int]
    to: _timestamp_pb2.Timestamp
    filter: str
    event_type: _audit_event_service_pb2.EventType
    def __init__(self, to: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., filter: _Optional[str] = ..., event_type: _Optional[_Union[_audit_event_service_pb2.EventType, str]] = ..., **kwargs) -> None: ...

class AuditEventExportStatus(_message.Message):
    __slots__ = ["state", "export_operation_id"]
    STATE_FIELD_NUMBER: _ClassVar[int]
    EXPORT_OPERATION_ID_FIELD_NUMBER: _ClassVar[int]
    state: AuditEventExportState
    export_operation_id: str
    def __init__(self, state: _Optional[_Union[AuditEventExportState, str]] = ..., export_operation_id: _Optional[str] = ...) -> None: ...
