from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ResourceAffinityComputeV1(_message.Message):
    __slots__ = ["fabric", "platform"]
    FABRIC_FIELD_NUMBER: _ClassVar[int]
    PLATFORM_FIELD_NUMBER: _ClassVar[int]
    fabric: str
    platform: str
    def __init__(self, fabric: _Optional[str] = ..., platform: _Optional[str] = ...) -> None: ...

class ResourceAffinity(_message.Message):
    __slots__ = ["compute_v1"]
    COMPUTE_V1_FIELD_NUMBER: _ClassVar[int]
    compute_v1: ResourceAffinityComputeV1
    def __init__(self, compute_v1: _Optional[_Union[ResourceAffinityComputeV1, _Mapping]] = ...) -> None: ...
