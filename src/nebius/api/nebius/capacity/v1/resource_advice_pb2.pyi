from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ResourceAdvice(_message.Message):
    __slots__ = ["metadata", "spec", "status"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: ResourceAdviceSpec
    status: ResourceAdviceStatus
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[ResourceAdviceSpec, _Mapping]] = ..., status: _Optional[_Union[ResourceAdviceStatus, _Mapping]] = ...) -> None: ...

class ResourceAdviceSpec(_message.Message):
    __slots__ = ["region", "fabric", "compute_instance"]
    REGION_FIELD_NUMBER: _ClassVar[int]
    FABRIC_FIELD_NUMBER: _ClassVar[int]
    COMPUTE_INSTANCE_FIELD_NUMBER: _ClassVar[int]
    region: str
    fabric: str
    compute_instance: ComputeInstanceDetails
    def __init__(self, region: _Optional[str] = ..., fabric: _Optional[str] = ..., compute_instance: _Optional[_Union[ComputeInstanceDetails, _Mapping]] = ...) -> None: ...

class ComputeInstanceDetails(_message.Message):
    __slots__ = ["platform", "preset", "gpu_memory_gigabytes"]
    class Preset(_message.Message):
        __slots__ = ["name", "resources"]
        class Resources(_message.Message):
            __slots__ = ["vcpu_count", "memory_gibibytes", "gpu_count"]
            VCPU_COUNT_FIELD_NUMBER: _ClassVar[int]
            MEMORY_GIBIBYTES_FIELD_NUMBER: _ClassVar[int]
            GPU_COUNT_FIELD_NUMBER: _ClassVar[int]
            vcpu_count: int
            memory_gibibytes: int
            gpu_count: int
            def __init__(self, vcpu_count: _Optional[int] = ..., memory_gibibytes: _Optional[int] = ..., gpu_count: _Optional[int] = ...) -> None: ...
        NAME_FIELD_NUMBER: _ClassVar[int]
        RESOURCES_FIELD_NUMBER: _ClassVar[int]
        name: str
        resources: ComputeInstanceDetails.Preset.Resources
        def __init__(self, name: _Optional[str] = ..., resources: _Optional[_Union[ComputeInstanceDetails.Preset.Resources, _Mapping]] = ...) -> None: ...
    PLATFORM_FIELD_NUMBER: _ClassVar[int]
    PRESET_FIELD_NUMBER: _ClassVar[int]
    GPU_MEMORY_GIGABYTES_FIELD_NUMBER: _ClassVar[int]
    platform: str
    preset: ComputeInstanceDetails.Preset
    gpu_memory_gigabytes: int
    def __init__(self, platform: _Optional[str] = ..., preset: _Optional[_Union[ComputeInstanceDetails.Preset, _Mapping]] = ..., gpu_memory_gigabytes: _Optional[int] = ...) -> None: ...

class ResourceAdviceStatus(_message.Message):
    __slots__ = ["reserved", "on_demand", "preemptible"]
    class Availability(_message.Message):
        __slots__ = ["data_state", "available", "limit", "availability_level", "effective_at"]
        class DataState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
            __slots__ = []
            DATA_STATE_UNSPECIFIED: _ClassVar[ResourceAdviceStatus.Availability.DataState]
            DATA_STATE_FRESH: _ClassVar[ResourceAdviceStatus.Availability.DataState]
            DATA_STATE_STALE: _ClassVar[ResourceAdviceStatus.Availability.DataState]
            DATA_STATE_UNKNOWN: _ClassVar[ResourceAdviceStatus.Availability.DataState]
        DATA_STATE_UNSPECIFIED: ResourceAdviceStatus.Availability.DataState
        DATA_STATE_FRESH: ResourceAdviceStatus.Availability.DataState
        DATA_STATE_STALE: ResourceAdviceStatus.Availability.DataState
        DATA_STATE_UNKNOWN: ResourceAdviceStatus.Availability.DataState
        class AvailabilityLevel(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
            __slots__ = []
            AVAILABILITY_LEVEL_UNSPECIFIED: _ClassVar[ResourceAdviceStatus.Availability.AvailabilityLevel]
            AVAILABILITY_LEVEL_HIGH: _ClassVar[ResourceAdviceStatus.Availability.AvailabilityLevel]
            AVAILABILITY_LEVEL_MEDIUM: _ClassVar[ResourceAdviceStatus.Availability.AvailabilityLevel]
            AVAILABILITY_LEVEL_LOW: _ClassVar[ResourceAdviceStatus.Availability.AvailabilityLevel]
            AVAILABILITY_LEVEL_LIMIT_REACHED: _ClassVar[ResourceAdviceStatus.Availability.AvailabilityLevel]
            AVAILABILITY_LEVEL_UNKNOWN: _ClassVar[ResourceAdviceStatus.Availability.AvailabilityLevel]
        AVAILABILITY_LEVEL_UNSPECIFIED: ResourceAdviceStatus.Availability.AvailabilityLevel
        AVAILABILITY_LEVEL_HIGH: ResourceAdviceStatus.Availability.AvailabilityLevel
        AVAILABILITY_LEVEL_MEDIUM: ResourceAdviceStatus.Availability.AvailabilityLevel
        AVAILABILITY_LEVEL_LOW: ResourceAdviceStatus.Availability.AvailabilityLevel
        AVAILABILITY_LEVEL_LIMIT_REACHED: ResourceAdviceStatus.Availability.AvailabilityLevel
        AVAILABILITY_LEVEL_UNKNOWN: ResourceAdviceStatus.Availability.AvailabilityLevel
        DATA_STATE_FIELD_NUMBER: _ClassVar[int]
        AVAILABLE_FIELD_NUMBER: _ClassVar[int]
        LIMIT_FIELD_NUMBER: _ClassVar[int]
        AVAILABILITY_LEVEL_FIELD_NUMBER: _ClassVar[int]
        EFFECTIVE_AT_FIELD_NUMBER: _ClassVar[int]
        data_state: ResourceAdviceStatus.Availability.DataState
        available: int
        limit: int
        availability_level: ResourceAdviceStatus.Availability.AvailabilityLevel
        effective_at: _timestamp_pb2.Timestamp
        def __init__(self, data_state: _Optional[_Union[ResourceAdviceStatus.Availability.DataState, str]] = ..., available: _Optional[int] = ..., limit: _Optional[int] = ..., availability_level: _Optional[_Union[ResourceAdviceStatus.Availability.AvailabilityLevel, str]] = ..., effective_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...
    RESERVED_FIELD_NUMBER: _ClassVar[int]
    ON_DEMAND_FIELD_NUMBER: _ClassVar[int]
    PREEMPTIBLE_FIELD_NUMBER: _ClassVar[int]
    reserved: ResourceAdviceStatus.Availability
    on_demand: ResourceAdviceStatus.Availability
    preemptible: ResourceAdviceStatus.Availability
    def __init__(self, reserved: _Optional[_Union[ResourceAdviceStatus.Availability, _Mapping]] = ..., on_demand: _Optional[_Union[ResourceAdviceStatus.Availability, _Mapping]] = ..., preemptible: _Optional[_Union[ResourceAdviceStatus.Availability, _Mapping]] = ...) -> None: ...
