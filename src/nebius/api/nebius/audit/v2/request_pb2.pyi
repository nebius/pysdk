from google.protobuf import struct_pb2 as _struct_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Request(_message.Message):
    __slots__ = ["request_id", "parameters", "idempotency_id", "trace_id"]
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    PARAMETERS_FIELD_NUMBER: _ClassVar[int]
    IDEMPOTENCY_ID_FIELD_NUMBER: _ClassVar[int]
    TRACE_ID_FIELD_NUMBER: _ClassVar[int]
    request_id: str
    parameters: _struct_pb2.Struct
    idempotency_id: str
    trace_id: str
    def __init__(self, request_id: _Optional[str] = ..., parameters: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., idempotency_id: _Optional[str] = ..., trace_id: _Optional[str] = ...) -> None: ...
