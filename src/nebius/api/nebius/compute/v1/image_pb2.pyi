from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Image(_message.Message):
    __slots__ = ["metadata", "spec", "status"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: ImageSpec
    status: ImageStatus
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[ImageSpec, _Mapping]] = ..., status: _Optional[_Union[ImageStatus, _Mapping]] = ...) -> None: ...

class ImageSpec(_message.Message):
    __slots__ = ["description", "image_family", "version", "cpu_architecture"]
    class CPUArchitecture(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        UNSPECIFIED: _ClassVar[ImageSpec.CPUArchitecture]
        AMD64: _ClassVar[ImageSpec.CPUArchitecture]
        ARM64: _ClassVar[ImageSpec.CPUArchitecture]
    UNSPECIFIED: ImageSpec.CPUArchitecture
    AMD64: ImageSpec.CPUArchitecture
    ARM64: ImageSpec.CPUArchitecture
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    IMAGE_FAMILY_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    CPU_ARCHITECTURE_FIELD_NUMBER: _ClassVar[int]
    description: str
    image_family: str
    version: str
    cpu_architecture: ImageSpec.CPUArchitecture
    def __init__(self, description: _Optional[str] = ..., image_family: _Optional[str] = ..., version: _Optional[str] = ..., cpu_architecture: _Optional[_Union[ImageSpec.CPUArchitecture, str]] = ...) -> None: ...

class ImageStatus(_message.Message):
    __slots__ = ["state", "state_description", "storage_size_bytes", "min_disk_size_bytes", "reconciling"]
    class State(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        UNSPECIFIED: _ClassVar[ImageStatus.State]
        CREATING: _ClassVar[ImageStatus.State]
        READY: _ClassVar[ImageStatus.State]
        UPDATING: _ClassVar[ImageStatus.State]
        DELETING: _ClassVar[ImageStatus.State]
        ERROR: _ClassVar[ImageStatus.State]
    UNSPECIFIED: ImageStatus.State
    CREATING: ImageStatus.State
    READY: ImageStatus.State
    UPDATING: ImageStatus.State
    DELETING: ImageStatus.State
    ERROR: ImageStatus.State
    STATE_FIELD_NUMBER: _ClassVar[int]
    STATE_DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    STORAGE_SIZE_BYTES_FIELD_NUMBER: _ClassVar[int]
    MIN_DISK_SIZE_BYTES_FIELD_NUMBER: _ClassVar[int]
    RECONCILING_FIELD_NUMBER: _ClassVar[int]
    state: ImageStatus.State
    state_description: str
    storage_size_bytes: int
    min_disk_size_bytes: int
    reconciling: bool
    def __init__(self, state: _Optional[_Union[ImageStatus.State, str]] = ..., state_description: _Optional[str] = ..., storage_size_bytes: _Optional[int] = ..., min_disk_size_bytes: _Optional[int] = ..., reconciling: bool = ...) -> None: ...
