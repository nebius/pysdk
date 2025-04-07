from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class Request(_message.Message):
    __slots__ = ["request_id", "idempotency_id", "trace_id"]
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    IDEMPOTENCY_ID_FIELD_NUMBER: _ClassVar[int]
    TRACE_ID_FIELD_NUMBER: _ClassVar[int]
    request_id: str
    idempotency_id: str
    trace_id: str
    def __init__(self, request_id: _Optional[str] = ..., idempotency_id: _Optional[str] = ..., trace_id: _Optional[str] = ...) -> None: ...
