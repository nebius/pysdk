from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class DiskSpec(_message.Message):
    __slots__ = ["size_bytes", "size_kibibytes", "size_mebibytes", "size_gibibytes", "block_size_bytes", "type"]
    class DiskType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        UNSPECIFIED: _ClassVar[DiskSpec.DiskType]
        NETWORK_SSD: _ClassVar[DiskSpec.DiskType]
        NETWORK_HDD: _ClassVar[DiskSpec.DiskType]
        NETWORK_SSD_IO_M3: _ClassVar[DiskSpec.DiskType]
        NETWORK_SSD_NON_REPLICATED: _ClassVar[DiskSpec.DiskType]
    UNSPECIFIED: DiskSpec.DiskType
    NETWORK_SSD: DiskSpec.DiskType
    NETWORK_HDD: DiskSpec.DiskType
    NETWORK_SSD_IO_M3: DiskSpec.DiskType
    NETWORK_SSD_NON_REPLICATED: DiskSpec.DiskType
    SIZE_BYTES_FIELD_NUMBER: _ClassVar[int]
    SIZE_KIBIBYTES_FIELD_NUMBER: _ClassVar[int]
    SIZE_MEBIBYTES_FIELD_NUMBER: _ClassVar[int]
    SIZE_GIBIBYTES_FIELD_NUMBER: _ClassVar[int]
    BLOCK_SIZE_BYTES_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    size_bytes: int
    size_kibibytes: int
    size_mebibytes: int
    size_gibibytes: int
    block_size_bytes: int
    type: DiskSpec.DiskType
    def __init__(self, size_bytes: _Optional[int] = ..., size_kibibytes: _Optional[int] = ..., size_mebibytes: _Optional[int] = ..., size_gibibytes: _Optional[int] = ..., block_size_bytes: _Optional[int] = ..., type: _Optional[_Union[DiskSpec.DiskType, str]] = ...) -> None: ...

class ResourcesSpec(_message.Message):
    __slots__ = ["platform", "preset"]
    PLATFORM_FIELD_NUMBER: _ClassVar[int]
    PRESET_FIELD_NUMBER: _ClassVar[int]
    platform: str
    preset: str
    def __init__(self, platform: _Optional[str] = ..., preset: _Optional[str] = ...) -> None: ...
