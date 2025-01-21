from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class PythonConfig(_message.Message):
    __slots__ = ["requirements", "file_uris"]
    REQUIREMENTS_FIELD_NUMBER: _ClassVar[int]
    FILE_URIS_FIELD_NUMBER: _ClassVar[int]
    requirements: _containers.RepeatedScalarFieldContainer[str]
    file_uris: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, requirements: _Optional[_Iterable[str]] = ..., file_uris: _Optional[_Iterable[str]] = ...) -> None: ...

class JavaConfig(_message.Message):
    __slots__ = ["entrypoint_class"]
    ENTRYPOINT_CLASS_FIELD_NUMBER: _ClassVar[int]
    entrypoint_class: str
    def __init__(self, entrypoint_class: _Optional[str] = ...) -> None: ...
