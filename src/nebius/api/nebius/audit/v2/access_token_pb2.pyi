from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class AccessToken(_message.Message):
    __slots__ = ["masked_token"]
    MASKED_TOKEN_FIELD_NUMBER: _ClassVar[int]
    masked_token: str
    def __init__(self, masked_token: _Optional[str] = ...) -> None: ...
