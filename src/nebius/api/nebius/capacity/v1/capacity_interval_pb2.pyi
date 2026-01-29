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

class CapacityIntervalSpec(_message.Message):
    __slots__ = []
    def __init__(self) -> None: ...

class CapacityIntervalStatus(_message.Message):
    __slots__ = ["container_id", "region", "resource_affinity", "service", "quantity", "start_time", "end_time", "state", "reconciling"]
    class State(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        STATE_UNSPECIFIED: _ClassVar[CapacityIntervalStatus.State]
        STATE_SCHEDULED: _ClassVar[CapacityIntervalStatus.State]
        STATE_ACTIVE: _ClassVar[CapacityIntervalStatus.State]
        STATE_EXPIRED: _ClassVar[CapacityIntervalStatus.State]
    STATE_UNSPECIFIED: CapacityIntervalStatus.State
    STATE_SCHEDULED: CapacityIntervalStatus.State
    STATE_ACTIVE: CapacityIntervalStatus.State
    STATE_EXPIRED: CapacityIntervalStatus.State
    CONTAINER_ID_FIELD_NUMBER: _ClassVar[int]
    REGION_FIELD_NUMBER: _ClassVar[int]
    RESOURCE_AFFINITY_FIELD_NUMBER: _ClassVar[int]
    SERVICE_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_FIELD_NUMBER: _ClassVar[int]
    START_TIME_FIELD_NUMBER: _ClassVar[int]
    END_TIME_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    RECONCILING_FIELD_NUMBER: _ClassVar[int]
    container_id: str
    region: str
    resource_affinity: _resource_affinity_pb2.ResourceAffinity
    service: str
    quantity: int
    start_time: _timestamp_pb2.Timestamp
    end_time: _timestamp_pb2.Timestamp
    state: CapacityIntervalStatus.State
    reconciling: bool
    def __init__(self, container_id: _Optional[str] = ..., region: _Optional[str] = ..., resource_affinity: _Optional[_Union[_resource_affinity_pb2.ResourceAffinity, _Mapping]] = ..., service: _Optional[str] = ..., quantity: _Optional[int] = ..., start_time: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., end_time: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., state: _Optional[_Union[CapacityIntervalStatus.State, str]] = ..., reconciling: bool = ...) -> None: ...

class CapacityInterval(_message.Message):
    __slots__ = ["metadata", "spec", "status"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: CapacityIntervalSpec
    status: CapacityIntervalStatus
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[CapacityIntervalSpec, _Mapping]] = ..., status: _Optional[_Union[CapacityIntervalStatus, _Mapping]] = ...) -> None: ...
