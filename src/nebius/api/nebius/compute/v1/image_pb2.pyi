from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

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
    __slots__ = ["description", "image_family", "version", "source_disk_id", "cpu_architecture", "image_family_human_readable", "recommended_platforms", "unsupported_platforms"]
    class CPUArchitecture(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        UNSPECIFIED: _ClassVar[ImageSpec.CPUArchitecture]
        AMD64: _ClassVar[ImageSpec.CPUArchitecture]
        ARM64: _ClassVar[ImageSpec.CPUArchitecture]
    UNSPECIFIED: ImageSpec.CPUArchitecture
    AMD64: ImageSpec.CPUArchitecture
    ARM64: ImageSpec.CPUArchitecture
    class UnsupportedPlatformsEntry(_message.Message):
        __slots__ = ["key", "value"]
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    IMAGE_FAMILY_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    SOURCE_DISK_ID_FIELD_NUMBER: _ClassVar[int]
    CPU_ARCHITECTURE_FIELD_NUMBER: _ClassVar[int]
    IMAGE_FAMILY_HUMAN_READABLE_FIELD_NUMBER: _ClassVar[int]
    RECOMMENDED_PLATFORMS_FIELD_NUMBER: _ClassVar[int]
    UNSUPPORTED_PLATFORMS_FIELD_NUMBER: _ClassVar[int]
    description: str
    image_family: str
    version: str
    source_disk_id: str
    cpu_architecture: ImageSpec.CPUArchitecture
    image_family_human_readable: str
    recommended_platforms: _containers.RepeatedScalarFieldContainer[str]
    unsupported_platforms: _containers.ScalarMap[str, str]
    def __init__(self, description: _Optional[str] = ..., image_family: _Optional[str] = ..., version: _Optional[str] = ..., source_disk_id: _Optional[str] = ..., cpu_architecture: _Optional[_Union[ImageSpec.CPUArchitecture, str]] = ..., image_family_human_readable: _Optional[str] = ..., recommended_platforms: _Optional[_Iterable[str]] = ..., unsupported_platforms: _Optional[_Mapping[str, str]] = ...) -> None: ...

class ImageStatus(_message.Message):
    __slots__ = ["state", "state_description", "storage_size_bytes", "min_disk_size_bytes", "reconciling", "image_family_deprecation"]
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
    class ImageFamilyDeprecationStatus(_message.Message):
        __slots__ = ["deprecated_at", "message"]
        DEPRECATED_AT_FIELD_NUMBER: _ClassVar[int]
        MESSAGE_FIELD_NUMBER: _ClassVar[int]
        deprecated_at: _timestamp_pb2.Timestamp
        message: str
        def __init__(self, deprecated_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., message: _Optional[str] = ...) -> None: ...
    STATE_FIELD_NUMBER: _ClassVar[int]
    STATE_DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    STORAGE_SIZE_BYTES_FIELD_NUMBER: _ClassVar[int]
    MIN_DISK_SIZE_BYTES_FIELD_NUMBER: _ClassVar[int]
    RECONCILING_FIELD_NUMBER: _ClassVar[int]
    IMAGE_FAMILY_DEPRECATION_FIELD_NUMBER: _ClassVar[int]
    state: ImageStatus.State
    state_description: str
    storage_size_bytes: int
    min_disk_size_bytes: int
    reconciling: bool
    image_family_deprecation: ImageStatus.ImageFamilyDeprecationStatus
    def __init__(self, state: _Optional[_Union[ImageStatus.State, str]] = ..., state_description: _Optional[str] = ..., storage_size_bytes: _Optional[int] = ..., min_disk_size_bytes: _Optional[int] = ..., reconciling: bool = ..., image_family_deprecation: _Optional[_Union[ImageStatus.ImageFamilyDeprecationStatus, _Mapping]] = ...) -> None: ...
