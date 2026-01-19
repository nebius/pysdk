from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class Payload(_message.Message):
    __slots__ = ["key", "string_value", "binary_value"]
    KEY_FIELD_NUMBER: _ClassVar[int]
    STRING_VALUE_FIELD_NUMBER: _ClassVar[int]
    BINARY_VALUE_FIELD_NUMBER: _ClassVar[int]
    key: str
    string_value: str
    binary_value: bytes
    def __init__(self, key: _Optional[str] = ..., string_value: _Optional[str] = ..., binary_value: _Optional[bytes] = ...) -> None: ...
