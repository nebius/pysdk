from google.protobuf import struct_pb2 as _struct_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ResourceState(_message.Message):
    __slots__ = ["previous", "current"]
    PREVIOUS_FIELD_NUMBER: _ClassVar[int]
    CURRENT_FIELD_NUMBER: _ClassVar[int]
    previous: _struct_pb2.Struct
    current: _struct_pb2.Struct
    def __init__(self, previous: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., current: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ...) -> None: ...
