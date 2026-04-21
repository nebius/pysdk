from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from google.protobuf import empty_pb2 as _empty_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.common.v1 import operation_pb2 as _operation_pb2
from nebius.api.nebius.logging.v1 import log_export_pb2 as _log_export_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ExportLogsRequest(_message.Message):
    __slots__ = ["params", "parent_id"]
    PARAMS_FIELD_NUMBER: _ClassVar[int]
    PARENT_ID_FIELD_NUMBER: _ClassVar[int]
    params: _log_export_pb2.ExportParams
    parent_id: str
    def __init__(self, params: _Optional[_Union[_log_export_pb2.ExportParams, _Mapping]] = ..., parent_id: _Optional[str] = ...) -> None: ...

class CancelExportLogsRequest(_message.Message):
    __slots__ = ["export_operation_id"]
    EXPORT_OPERATION_ID_FIELD_NUMBER: _ClassVar[int]
    export_operation_id: str
    def __init__(self, export_operation_id: _Optional[str] = ...) -> None: ...

class ListExportsRequest(_message.Message):
    __slots__ = ["parent_id", "page_token", "page_size", "order_by"]
    PARENT_ID_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    PAGE_SIZE_FIELD_NUMBER: _ClassVar[int]
    ORDER_BY_FIELD_NUMBER: _ClassVar[int]
    parent_id: str
    page_token: str
    page_size: int
    order_by: _log_export_pb2.OrderBy
    def __init__(self, parent_id: _Optional[str] = ..., page_token: _Optional[str] = ..., page_size: _Optional[int] = ..., order_by: _Optional[_Union[_log_export_pb2.OrderBy, str]] = ...) -> None: ...

class ListExportsResponse(_message.Message):
    __slots__ = ["exports", "next_page_token"]
    EXPORTS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    exports: _containers.RepeatedCompositeFieldContainer[_log_export_pb2.ExportStatus]
    next_page_token: str
    def __init__(self, exports: _Optional[_Iterable[_Union[_log_export_pb2.ExportStatus, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...

class GetExportInfoRequest(_message.Message):
    __slots__ = ["export_operation_id"]
    EXPORT_OPERATION_ID_FIELD_NUMBER: _ClassVar[int]
    export_operation_id: str
    def __init__(self, export_operation_id: _Optional[str] = ...) -> None: ...
