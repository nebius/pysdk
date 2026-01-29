from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.capacity.v1 import resource_affinity_pb2 as _resource_affinity_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class CapacityBlockGroupSpec(_message.Message):
    __slots__ = []
    def __init__(self) -> None: ...

class CurrentContinuousInterval(_message.Message):
    __slots__ = ["start_time", "end_time", "quantity", "state"]
    class State(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        STATE_UNSPECIFIED: _ClassVar[CurrentContinuousInterval.State]
        STATE_SCHEDULED: _ClassVar[CurrentContinuousInterval.State]
        STATE_ACTIVE: _ClassVar[CurrentContinuousInterval.State]
        STATE_EXPIRED: _ClassVar[CurrentContinuousInterval.State]
    STATE_UNSPECIFIED: CurrentContinuousInterval.State
    STATE_SCHEDULED: CurrentContinuousInterval.State
    STATE_ACTIVE: CurrentContinuousInterval.State
    STATE_EXPIRED: CurrentContinuousInterval.State
    START_TIME_FIELD_NUMBER: _ClassVar[int]
    END_TIME_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    start_time: _timestamp_pb2.Timestamp
    end_time: _timestamp_pb2.Timestamp
    quantity: int
    state: CurrentContinuousInterval.State
    def __init__(self, start_time: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., end_time: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., quantity: _Optional[int] = ..., state: _Optional[_Union[CurrentContinuousInterval.State, str]] = ...) -> None: ...

class CapacityBlockGroupStatus(_message.Message):
    __slots__ = ["region", "resource_affinity", "service", "state", "current_limit", "usage", "usage_percentage", "next_change_at", "next_change_to", "current_continuous_interval", "usage_state", "reconciling"]
    class State(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        STATE_UNSPECIFIED: _ClassVar[CapacityBlockGroupStatus.State]
        STATE_ALLOCATING: _ClassVar[CapacityBlockGroupStatus.State]
        STATE_ACTIVE: _ClassVar[CapacityBlockGroupStatus.State]
        STATE_SHUTTING: _ClassVar[CapacityBlockGroupStatus.State]
        STATE_INACTIVE: _ClassVar[CapacityBlockGroupStatus.State]
    STATE_UNSPECIFIED: CapacityBlockGroupStatus.State
    STATE_ALLOCATING: CapacityBlockGroupStatus.State
    STATE_ACTIVE: CapacityBlockGroupStatus.State
    STATE_SHUTTING: CapacityBlockGroupStatus.State
    STATE_INACTIVE: CapacityBlockGroupStatus.State
    class UsageState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        USAGE_STATE_UNSPECIFIED: _ClassVar[CapacityBlockGroupStatus.UsageState]
        USAGE_STATE_USED: _ClassVar[CapacityBlockGroupStatus.UsageState]
        USAGE_STATE_NOT_USED: _ClassVar[CapacityBlockGroupStatus.UsageState]
        USAGE_STATE_UNKNOWN: _ClassVar[CapacityBlockGroupStatus.UsageState]
    USAGE_STATE_UNSPECIFIED: CapacityBlockGroupStatus.UsageState
    USAGE_STATE_USED: CapacityBlockGroupStatus.UsageState
    USAGE_STATE_NOT_USED: CapacityBlockGroupStatus.UsageState
    USAGE_STATE_UNKNOWN: CapacityBlockGroupStatus.UsageState
    REGION_FIELD_NUMBER: _ClassVar[int]
    RESOURCE_AFFINITY_FIELD_NUMBER: _ClassVar[int]
    SERVICE_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    CURRENT_LIMIT_FIELD_NUMBER: _ClassVar[int]
    USAGE_FIELD_NUMBER: _ClassVar[int]
    USAGE_PERCENTAGE_FIELD_NUMBER: _ClassVar[int]
    NEXT_CHANGE_AT_FIELD_NUMBER: _ClassVar[int]
    NEXT_CHANGE_TO_FIELD_NUMBER: _ClassVar[int]
    CURRENT_CONTINUOUS_INTERVAL_FIELD_NUMBER: _ClassVar[int]
    USAGE_STATE_FIELD_NUMBER: _ClassVar[int]
    RECONCILING_FIELD_NUMBER: _ClassVar[int]
    region: str
    resource_affinity: _resource_affinity_pb2.ResourceAffinity
    service: str
    state: CapacityBlockGroupStatus.State
    current_limit: int
    usage: int
    usage_percentage: str
    next_change_at: _timestamp_pb2.Timestamp
    next_change_to: int
    current_continuous_interval: CurrentContinuousInterval
    usage_state: CapacityBlockGroupStatus.UsageState
    reconciling: bool
    def __init__(self, region: _Optional[str] = ..., resource_affinity: _Optional[_Union[_resource_affinity_pb2.ResourceAffinity, _Mapping]] = ..., service: _Optional[str] = ..., state: _Optional[_Union[CapacityBlockGroupStatus.State, str]] = ..., current_limit: _Optional[int] = ..., usage: _Optional[int] = ..., usage_percentage: _Optional[str] = ..., next_change_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., next_change_to: _Optional[int] = ..., current_continuous_interval: _Optional[_Union[CurrentContinuousInterval, _Mapping]] = ..., usage_state: _Optional[_Union[CapacityBlockGroupStatus.UsageState, str]] = ..., reconciling: bool = ...) -> None: ...

class CapacityBlockGroup(_message.Message):
    __slots__ = ["metadata", "spec", "status"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: CapacityBlockGroupSpec
    status: CapacityBlockGroupStatus
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[CapacityBlockGroupSpec, _Mapping]] = ..., status: _Optional[_Union[CapacityBlockGroupStatus, _Mapping]] = ...) -> None: ...
