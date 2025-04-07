from google.rpc import code_pb2 as _code_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Response(_message.Message):
    __slots__ = ["status_code", "error_message"]
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    status_code: _code_pb2.Code
    error_message: str
    def __init__(self, status_code: _Optional[_Union[_code_pb2.Code, str]] = ..., error_message: _Optional[str] = ...) -> None: ...
