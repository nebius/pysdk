from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class Authorization(_message.Message):
    __slots__ = ["authorized"]
    AUTHORIZED_FIELD_NUMBER: _ClassVar[int]
    authorized: bool
    def __init__(self, authorized: bool = ...) -> None: ...
