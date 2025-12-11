from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Platform(_message.Message):
    __slots__ = ["metadata", "spec", "status"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: PlatformSpec
    status: PlatformStatus
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[PlatformSpec, _Mapping]] = ..., status: _Optional[_Union[PlatformStatus, _Mapping]] = ...) -> None: ...

class PlatformSpec(_message.Message):
    __slots__ = ["presets", "gpu_count_quota_type", "human_readable_name", "allow_preset_change", "short_human_readable_name", "gpu_memory_gibibytes", "gpu_memory_gigabytes"]
    PRESETS_FIELD_NUMBER: _ClassVar[int]
    GPU_COUNT_QUOTA_TYPE_FIELD_NUMBER: _ClassVar[int]
    HUMAN_READABLE_NAME_FIELD_NUMBER: _ClassVar[int]
    ALLOW_PRESET_CHANGE_FIELD_NUMBER: _ClassVar[int]
    SHORT_HUMAN_READABLE_NAME_FIELD_NUMBER: _ClassVar[int]
    GPU_MEMORY_GIBIBYTES_FIELD_NUMBER: _ClassVar[int]
    GPU_MEMORY_GIGABYTES_FIELD_NUMBER: _ClassVar[int]
    presets: _containers.RepeatedCompositeFieldContainer[Preset]
    gpu_count_quota_type: str
    human_readable_name: str
    allow_preset_change: bool
    short_human_readable_name: str
    gpu_memory_gibibytes: int
    gpu_memory_gigabytes: int
    def __init__(self, presets: _Optional[_Iterable[_Union[Preset, _Mapping]]] = ..., gpu_count_quota_type: _Optional[str] = ..., human_readable_name: _Optional[str] = ..., allow_preset_change: bool = ..., short_human_readable_name: _Optional[str] = ..., gpu_memory_gibibytes: _Optional[int] = ..., gpu_memory_gigabytes: _Optional[int] = ...) -> None: ...

class Preset(_message.Message):
    __slots__ = ["name", "resources", "allow_gpu_clustering"]
    NAME_FIELD_NUMBER: _ClassVar[int]
    RESOURCES_FIELD_NUMBER: _ClassVar[int]
    ALLOW_GPU_CLUSTERING_FIELD_NUMBER: _ClassVar[int]
    name: str
    resources: PresetResources
    allow_gpu_clustering: bool
    def __init__(self, name: _Optional[str] = ..., resources: _Optional[_Union[PresetResources, _Mapping]] = ..., allow_gpu_clustering: bool = ...) -> None: ...

class PresetResources(_message.Message):
    __slots__ = ["vcpu_count", "memory_gibibytes", "gpu_count", "gpu_memory_gibibytes"]
    VCPU_COUNT_FIELD_NUMBER: _ClassVar[int]
    MEMORY_GIBIBYTES_FIELD_NUMBER: _ClassVar[int]
    GPU_COUNT_FIELD_NUMBER: _ClassVar[int]
    GPU_MEMORY_GIBIBYTES_FIELD_NUMBER: _ClassVar[int]
    vcpu_count: int
    memory_gibibytes: int
    gpu_count: int
    gpu_memory_gibibytes: int
    def __init__(self, vcpu_count: _Optional[int] = ..., memory_gibibytes: _Optional[int] = ..., gpu_count: _Optional[int] = ..., gpu_memory_gibibytes: _Optional[int] = ...) -> None: ...

class PlatformStatus(_message.Message):
    __slots__ = ["allowed_for_preemptibles"]
    ALLOWED_FOR_PREEMPTIBLES_FIELD_NUMBER: _ClassVar[int]
    allowed_for_preemptibles: bool
    def __init__(self, allowed_for_preemptibles: bool = ...) -> None: ...
