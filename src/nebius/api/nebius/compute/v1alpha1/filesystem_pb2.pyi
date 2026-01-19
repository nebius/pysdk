from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Filesystem(_message.Message):
    __slots__ = ["metadata", "spec", "status"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: FilesystemSpec
    status: FilesystemStatus
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[FilesystemSpec, _Mapping]] = ..., status: _Optional[_Union[FilesystemStatus, _Mapping]] = ...) -> None: ...

class FilesystemSpec(_message.Message):
    __slots__ = ["size_bytes", "size_kibibytes", "size_mebibytes", "size_gibibytes", "block_size_bytes", "type"]
    class FilesystemType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        UNSPECIFIED: _ClassVar[FilesystemSpec.FilesystemType]
        NETWORK_SSD: _ClassVar[FilesystemSpec.FilesystemType]
        NETWORK_HDD: _ClassVar[FilesystemSpec.FilesystemType]
        WEKA: _ClassVar[FilesystemSpec.FilesystemType]
        VAST: _ClassVar[FilesystemSpec.FilesystemType]
    UNSPECIFIED: FilesystemSpec.FilesystemType
    NETWORK_SSD: FilesystemSpec.FilesystemType
    NETWORK_HDD: FilesystemSpec.FilesystemType
    WEKA: FilesystemSpec.FilesystemType
    VAST: FilesystemSpec.FilesystemType
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
    type: FilesystemSpec.FilesystemType
    def __init__(self, size_bytes: _Optional[int] = ..., size_kibibytes: _Optional[int] = ..., size_mebibytes: _Optional[int] = ..., size_gibibytes: _Optional[int] = ..., block_size_bytes: _Optional[int] = ..., type: _Optional[_Union[FilesystemSpec.FilesystemType, str]] = ...) -> None: ...

class FilesystemStatus(_message.Message):
    __slots__ = ["state", "state_description", "read_write_attachments", "read_only_attachments", "size_bytes", "reconciling"]
    class State(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        UNSPECIFIED: _ClassVar[FilesystemStatus.State]
        CREATING: _ClassVar[FilesystemStatus.State]
        READY: _ClassVar[FilesystemStatus.State]
        UPDATING: _ClassVar[FilesystemStatus.State]
        DELETING: _ClassVar[FilesystemStatus.State]
        ERROR: _ClassVar[FilesystemStatus.State]
    UNSPECIFIED: FilesystemStatus.State
    CREATING: FilesystemStatus.State
    READY: FilesystemStatus.State
    UPDATING: FilesystemStatus.State
    DELETING: FilesystemStatus.State
    ERROR: FilesystemStatus.State
    STATE_FIELD_NUMBER: _ClassVar[int]
    STATE_DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    READ_WRITE_ATTACHMENTS_FIELD_NUMBER: _ClassVar[int]
    READ_ONLY_ATTACHMENTS_FIELD_NUMBER: _ClassVar[int]
    SIZE_BYTES_FIELD_NUMBER: _ClassVar[int]
    RECONCILING_FIELD_NUMBER: _ClassVar[int]
    state: FilesystemStatus.State
    state_description: str
    read_write_attachments: _containers.RepeatedScalarFieldContainer[str]
    read_only_attachments: _containers.RepeatedScalarFieldContainer[str]
    size_bytes: int
    reconciling: bool
    def __init__(self, state: _Optional[_Union[FilesystemStatus.State, str]] = ..., state_description: _Optional[str] = ..., read_write_attachments: _Optional[_Iterable[str]] = ..., read_only_attachments: _Optional[_Iterable[str]] = ..., size_bytes: _Optional[int] = ..., reconciling: bool = ...) -> None: ...
