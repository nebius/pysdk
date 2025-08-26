from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Disk(_message.Message):
    __slots__ = ["metadata", "spec", "status"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: DiskSpec
    status: DiskStatus
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[DiskSpec, _Mapping]] = ..., status: _Optional[_Union[DiskStatus, _Mapping]] = ...) -> None: ...

class DiskSpec(_message.Message):
    __slots__ = ["size_bytes", "size_kibibytes", "size_mebibytes", "size_gibibytes", "block_size_bytes", "type", "source_image_id", "source_image_family", "disk_encryption"]
    class DiskType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        UNSPECIFIED: _ClassVar[DiskSpec.DiskType]
        NETWORK_SSD: _ClassVar[DiskSpec.DiskType]
        NETWORK_HDD: _ClassVar[DiskSpec.DiskType]
        NETWORK_SSD_NON_REPLICATED: _ClassVar[DiskSpec.DiskType]
        NETWORK_SSD_IO_M3: _ClassVar[DiskSpec.DiskType]
    UNSPECIFIED: DiskSpec.DiskType
    NETWORK_SSD: DiskSpec.DiskType
    NETWORK_HDD: DiskSpec.DiskType
    NETWORK_SSD_NON_REPLICATED: DiskSpec.DiskType
    NETWORK_SSD_IO_M3: DiskSpec.DiskType
    SIZE_BYTES_FIELD_NUMBER: _ClassVar[int]
    SIZE_KIBIBYTES_FIELD_NUMBER: _ClassVar[int]
    SIZE_MEBIBYTES_FIELD_NUMBER: _ClassVar[int]
    SIZE_GIBIBYTES_FIELD_NUMBER: _ClassVar[int]
    BLOCK_SIZE_BYTES_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    SOURCE_IMAGE_ID_FIELD_NUMBER: _ClassVar[int]
    SOURCE_IMAGE_FAMILY_FIELD_NUMBER: _ClassVar[int]
    DISK_ENCRYPTION_FIELD_NUMBER: _ClassVar[int]
    size_bytes: int
    size_kibibytes: int
    size_mebibytes: int
    size_gibibytes: int
    block_size_bytes: int
    type: DiskSpec.DiskType
    source_image_id: str
    source_image_family: SourceImageFamily
    disk_encryption: DiskEncryption
    def __init__(self, size_bytes: _Optional[int] = ..., size_kibibytes: _Optional[int] = ..., size_mebibytes: _Optional[int] = ..., size_gibibytes: _Optional[int] = ..., block_size_bytes: _Optional[int] = ..., type: _Optional[_Union[DiskSpec.DiskType, str]] = ..., source_image_id: _Optional[str] = ..., source_image_family: _Optional[_Union[SourceImageFamily, _Mapping]] = ..., disk_encryption: _Optional[_Union[DiskEncryption, _Mapping]] = ...) -> None: ...

class SourceImageFamily(_message.Message):
    __slots__ = ["image_family", "parent_id"]
    IMAGE_FAMILY_FIELD_NUMBER: _ClassVar[int]
    PARENT_ID_FIELD_NUMBER: _ClassVar[int]
    image_family: str
    parent_id: str
    def __init__(self, image_family: _Optional[str] = ..., parent_id: _Optional[str] = ...) -> None: ...

class DiskStatus(_message.Message):
    __slots__ = ["state", "state_description", "read_write_attachment", "read_only_attachments", "source_image_id", "size_bytes", "reconciling", "block_size_bytes", "source_image_cpu_architecture"]
    class State(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        UNSPECIFIED: _ClassVar[DiskStatus.State]
        CREATING: _ClassVar[DiskStatus.State]
        READY: _ClassVar[DiskStatus.State]
        UPDATING: _ClassVar[DiskStatus.State]
        DELETING: _ClassVar[DiskStatus.State]
        ERROR: _ClassVar[DiskStatus.State]
        BROKEN: _ClassVar[DiskStatus.State]
    UNSPECIFIED: DiskStatus.State
    CREATING: DiskStatus.State
    READY: DiskStatus.State
    UPDATING: DiskStatus.State
    DELETING: DiskStatus.State
    ERROR: DiskStatus.State
    BROKEN: DiskStatus.State
    class SourceImageCPUArchitecture(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        SOURCE_IMAGE_CPU_UNSPECIFIED: _ClassVar[DiskStatus.SourceImageCPUArchitecture]
        AMD64: _ClassVar[DiskStatus.SourceImageCPUArchitecture]
        ARM64: _ClassVar[DiskStatus.SourceImageCPUArchitecture]
    SOURCE_IMAGE_CPU_UNSPECIFIED: DiskStatus.SourceImageCPUArchitecture
    AMD64: DiskStatus.SourceImageCPUArchitecture
    ARM64: DiskStatus.SourceImageCPUArchitecture
    STATE_FIELD_NUMBER: _ClassVar[int]
    STATE_DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    READ_WRITE_ATTACHMENT_FIELD_NUMBER: _ClassVar[int]
    READ_ONLY_ATTACHMENTS_FIELD_NUMBER: _ClassVar[int]
    SOURCE_IMAGE_ID_FIELD_NUMBER: _ClassVar[int]
    SIZE_BYTES_FIELD_NUMBER: _ClassVar[int]
    RECONCILING_FIELD_NUMBER: _ClassVar[int]
    BLOCK_SIZE_BYTES_FIELD_NUMBER: _ClassVar[int]
    SOURCE_IMAGE_CPU_ARCHITECTURE_FIELD_NUMBER: _ClassVar[int]
    state: DiskStatus.State
    state_description: str
    read_write_attachment: str
    read_only_attachments: _containers.RepeatedScalarFieldContainer[str]
    source_image_id: str
    size_bytes: int
    reconciling: bool
    block_size_bytes: int
    source_image_cpu_architecture: DiskStatus.SourceImageCPUArchitecture
    def __init__(self, state: _Optional[_Union[DiskStatus.State, str]] = ..., state_description: _Optional[str] = ..., read_write_attachment: _Optional[str] = ..., read_only_attachments: _Optional[_Iterable[str]] = ..., source_image_id: _Optional[str] = ..., size_bytes: _Optional[int] = ..., reconciling: bool = ..., block_size_bytes: _Optional[int] = ..., source_image_cpu_architecture: _Optional[_Union[DiskStatus.SourceImageCPUArchitecture, str]] = ...) -> None: ...

class DiskEncryption(_message.Message):
    __slots__ = ["type"]
    class DiskEncryptionType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        DISK_ENCRYPTION_UNSPECIFIED: _ClassVar[DiskEncryption.DiskEncryptionType]
        DISK_ENCRYPTION_MANAGED: _ClassVar[DiskEncryption.DiskEncryptionType]
    DISK_ENCRYPTION_UNSPECIFIED: DiskEncryption.DiskEncryptionType
    DISK_ENCRYPTION_MANAGED: DiskEncryption.DiskEncryptionType
    TYPE_FIELD_NUMBER: _ClassVar[int]
    type: DiskEncryption.DiskEncryptionType
    def __init__(self, type: _Optional[_Union[DiskEncryption.DiskEncryptionType, str]] = ...) -> None: ...
