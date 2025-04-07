from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.audit.v2 import audit_event_pb2 as _audit_event_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ListAuditEventRequest(_message.Message):
    __slots__ = ["parent_id", "page_size", "start", "end", "page_token", "filter"]
    PARENT_ID_FIELD_NUMBER: _ClassVar[int]
    PAGE_SIZE_FIELD_NUMBER: _ClassVar[int]
    START_FIELD_NUMBER: _ClassVar[int]
    END_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    FILTER_FIELD_NUMBER: _ClassVar[int]
    parent_id: str
    page_size: int
    start: _timestamp_pb2.Timestamp
    end: _timestamp_pb2.Timestamp
    page_token: str
    filter: str
    def __init__(self, parent_id: _Optional[str] = ..., page_size: _Optional[int] = ..., start: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., end: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., page_token: _Optional[str] = ..., filter: _Optional[str] = ...) -> None: ...

class ListAuditEventResponse(_message.Message):
    __slots__ = ["items", "next_page_token"]
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[_audit_event_pb2.AuditEvent]
    next_page_token: str
    def __init__(self, items: _Optional[_Iterable[_Union[_audit_event_pb2.AuditEvent, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...
