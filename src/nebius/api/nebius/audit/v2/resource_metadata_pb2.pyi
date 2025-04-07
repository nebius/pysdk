from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class ResourceMetadata(_message.Message):
    __slots__ = ["id", "name", "type"]
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    id: str
    name: str
    type: str
    def __init__(self, id: _Optional[str] = ..., name: _Optional[str] = ..., type: _Optional[str] = ...) -> None: ...
