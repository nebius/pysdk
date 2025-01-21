from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius.msp.v1alpha1.resource import template_pb2 as _template_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Preset(_message.Message):
    __slots__ = ["spec"]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    spec: PresetSpec
    def __init__(self, spec: _Optional[_Union[PresetSpec, _Mapping]] = ...) -> None: ...

class PresetSpec(_message.Message):
    __slots__ = ["flavor", "hosts", "disk", "role"]
    FLAVOR_FIELD_NUMBER: _ClassVar[int]
    HOSTS_FIELD_NUMBER: _ClassVar[int]
    DISK_FIELD_NUMBER: _ClassVar[int]
    ROLE_FIELD_NUMBER: _ClassVar[int]
    flavor: FlavorSpec
    hosts: _template_pb2.Host
    disk: _template_pb2.Disk
    role: str
    def __init__(self, flavor: _Optional[_Union[FlavorSpec, _Mapping]] = ..., hosts: _Optional[_Union[_template_pb2.Host, _Mapping]] = ..., disk: _Optional[_Union[_template_pb2.Disk, _Mapping]] = ..., role: _Optional[str] = ...) -> None: ...

class FlavorSpec(_message.Message):
    __slots__ = ["cpu", "memory"]
    CPU_FIELD_NUMBER: _ClassVar[int]
    MEMORY_FIELD_NUMBER: _ClassVar[int]
    cpu: CpuSpec
    memory: MemorySpec
    def __init__(self, cpu: _Optional[_Union[CpuSpec, _Mapping]] = ..., memory: _Optional[_Union[MemorySpec, _Mapping]] = ...) -> None: ...

class CpuSpec(_message.Message):
    __slots__ = ["count", "generation"]
    COUNT_FIELD_NUMBER: _ClassVar[int]
    GENERATION_FIELD_NUMBER: _ClassVar[int]
    count: int
    generation: int
    def __init__(self, count: _Optional[int] = ..., generation: _Optional[int] = ...) -> None: ...

class MemorySpec(_message.Message):
    __slots__ = ["limit_gibibytes"]
    LIMIT_GIBIBYTES_FIELD_NUMBER: _ClassVar[int]
    limit_gibibytes: int
    def __init__(self, limit_gibibytes: _Optional[int] = ...) -> None: ...
