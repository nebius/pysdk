from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Template(_message.Message):
    __slots__ = ["status", "spec"]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    status: TemplateStatus
    spec: TemplateSpec
    def __init__(self, status: _Optional[_Union[TemplateStatus, _Mapping]] = ..., spec: _Optional[_Union[TemplateSpec, _Mapping]] = ...) -> None: ...

class TemplateStatus(_message.Message):
    __slots__ = ["preset_details"]
    PRESET_DETAILS_FIELD_NUMBER: _ClassVar[int]
    preset_details: PresetDetails
    def __init__(self, preset_details: _Optional[_Union[PresetDetails, _Mapping]] = ...) -> None: ...

class TemplateSpec(_message.Message):
    __slots__ = ["resources", "hosts", "disk", "role"]
    RESOURCES_FIELD_NUMBER: _ClassVar[int]
    HOSTS_FIELD_NUMBER: _ClassVar[int]
    DISK_FIELD_NUMBER: _ClassVar[int]
    ROLE_FIELD_NUMBER: _ClassVar[int]
    resources: ResourcesSpec
    hosts: Host
    disk: Disk
    role: str
    def __init__(self, resources: _Optional[_Union[ResourcesSpec, _Mapping]] = ..., hosts: _Optional[_Union[Host, _Mapping]] = ..., disk: _Optional[_Union[Disk, _Mapping]] = ..., role: _Optional[str] = ...) -> None: ...

class ResourcesSpec(_message.Message):
    __slots__ = ["platform", "preset"]
    PLATFORM_FIELD_NUMBER: _ClassVar[int]
    PRESET_FIELD_NUMBER: _ClassVar[int]
    platform: str
    preset: str
    def __init__(self, platform: _Optional[str] = ..., preset: _Optional[str] = ...) -> None: ...

class PresetDetails(_message.Message):
    __slots__ = ["cpu_count", "memory_gibibytes", "gpu_count"]
    CPU_COUNT_FIELD_NUMBER: _ClassVar[int]
    MEMORY_GIBIBYTES_FIELD_NUMBER: _ClassVar[int]
    GPU_COUNT_FIELD_NUMBER: _ClassVar[int]
    cpu_count: int
    memory_gibibytes: int
    gpu_count: int
    def __init__(self, cpu_count: _Optional[int] = ..., memory_gibibytes: _Optional[int] = ..., gpu_count: _Optional[int] = ...) -> None: ...

class Range(_message.Message):
    __slots__ = ["min", "max", "step", "value"]
    MIN_FIELD_NUMBER: _ClassVar[int]
    MAX_FIELD_NUMBER: _ClassVar[int]
    STEP_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    min: int
    max: int
    step: int
    value: int
    def __init__(self, min: _Optional[int] = ..., max: _Optional[int] = ..., step: _Optional[int] = ..., value: _Optional[int] = ...) -> None: ...

class Disk(_message.Message):
    __slots__ = ["type", "size_gibibytes"]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    SIZE_GIBIBYTES_FIELD_NUMBER: _ClassVar[int]
    type: str
    size_gibibytes: Range
    def __init__(self, type: _Optional[str] = ..., size_gibibytes: _Optional[_Union[Range, _Mapping]] = ...) -> None: ...

class DiskSpec(_message.Message):
    __slots__ = ["type", "size_gibibytes"]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    SIZE_GIBIBYTES_FIELD_NUMBER: _ClassVar[int]
    type: str
    size_gibibytes: int
    def __init__(self, type: _Optional[str] = ..., size_gibibytes: _Optional[int] = ...) -> None: ...

class Host(_message.Message):
    __slots__ = ["count"]
    COUNT_FIELD_NUMBER: _ClassVar[int]
    count: Range
    def __init__(self, count: _Optional[_Union[Range, _Mapping]] = ...) -> None: ...

class HostSpec(_message.Message):
    __slots__ = ["count"]
    COUNT_FIELD_NUMBER: _ClassVar[int]
    count: int
    def __init__(self, count: _Optional[int] = ...) -> None: ...
