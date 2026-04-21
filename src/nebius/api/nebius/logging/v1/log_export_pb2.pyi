from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from nebius.api.nebius.common.v1 import operation_pb2 as _operation_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class OrderBy(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = []
    ORDER_BY_UNSPECIFIED: _ClassVar[OrderBy]
    ORDER_BY_ASC: _ClassVar[OrderBy]
    ORDER_BY_DESC: _ClassVar[OrderBy]

class LogsExportFormat(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = []
    EXPORT_FORMAT_UNSUPPORTED: _ClassVar[LogsExportFormat]
    JSON_GZIP: _ClassVar[LogsExportFormat]
    PARQUET: _ClassVar[LogsExportFormat]
ORDER_BY_UNSPECIFIED: OrderBy
ORDER_BY_ASC: OrderBy
ORDER_BY_DESC: OrderBy
EXPORT_FORMAT_UNSUPPORTED: LogsExportFormat
JSON_GZIP: LogsExportFormat
PARQUET: LogsExportFormat

class ExportStatus(_message.Message):
    __slots__ = ["operation", "result_path"]
    OPERATION_FIELD_NUMBER: _ClassVar[int]
    RESULT_PATH_FIELD_NUMBER: _ClassVar[int]
    operation: _operation_pb2.Operation
    result_path: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, operation: _Optional[_Union[_operation_pb2.Operation, _Mapping]] = ..., result_path: _Optional[_Iterable[str]] = ...) -> None: ...

class ExportFilter(_message.Message):
    __slots__ = ["to", "match_expression"]
    FROM_FIELD_NUMBER: _ClassVar[int]
    TO_FIELD_NUMBER: _ClassVar[int]
    MATCH_EXPRESSION_FIELD_NUMBER: _ClassVar[int]
    to: _timestamp_pb2.Timestamp
    match_expression: str
    def __init__(self, to: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., match_expression: _Optional[str] = ..., **kwargs) -> None: ...

class LogsExport(_message.Message):
    __slots__ = ["filter", "export_labels", "format"]
    FILTER_FIELD_NUMBER: _ClassVar[int]
    EXPORT_LABELS_FIELD_NUMBER: _ClassVar[int]
    FORMAT_FIELD_NUMBER: _ClassVar[int]
    filter: ExportFilter
    export_labels: _containers.RepeatedScalarFieldContainer[str]
    format: LogsExportFormat
    def __init__(self, filter: _Optional[_Union[ExportFilter, _Mapping]] = ..., export_labels: _Optional[_Iterable[str]] = ..., format: _Optional[_Union[LogsExportFormat, str]] = ...) -> None: ...

class NebiusObjectStorageBucketByName(_message.Message):
    __slots__ = ["name", "parent_id"]
    NAME_FIELD_NUMBER: _ClassVar[int]
    PARENT_ID_FIELD_NUMBER: _ClassVar[int]
    name: str
    parent_id: str
    def __init__(self, name: _Optional[str] = ..., parent_id: _Optional[str] = ...) -> None: ...

class NebiusObjectStorageDestination(_message.Message):
    __slots__ = ["id", "by_name", "object_prefix"]
    ID_FIELD_NUMBER: _ClassVar[int]
    BY_NAME_FIELD_NUMBER: _ClassVar[int]
    OBJECT_PREFIX_FIELD_NUMBER: _ClassVar[int]
    id: str
    by_name: NebiusObjectStorageBucketByName
    object_prefix: str
    def __init__(self, id: _Optional[str] = ..., by_name: _Optional[_Union[NebiusObjectStorageBucketByName, _Mapping]] = ..., object_prefix: _Optional[str] = ...) -> None: ...

class ExportParams(_message.Message):
    __slots__ = ["log", "nebius_object_storage"]
    LOG_FIELD_NUMBER: _ClassVar[int]
    NEBIUS_OBJECT_STORAGE_FIELD_NUMBER: _ClassVar[int]
    log: LogsExport
    nebius_object_storage: NebiusObjectStorageDestination
    def __init__(self, log: _Optional[_Union[LogsExport, _Mapping]] = ..., nebius_object_storage: _Optional[_Union[NebiusObjectStorageDestination, _Mapping]] = ...) -> None: ...
