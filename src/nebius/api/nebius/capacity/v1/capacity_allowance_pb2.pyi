from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class CapacityAllowance(_message.Message):
    __slots__ = ["metadata", "spec", "status"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: CapacityAllowanceSpec
    status: CapacityAllowanceStatus
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[CapacityAllowanceSpec, _Mapping]] = ..., status: _Optional[_Union[CapacityAllowanceStatus, _Mapping]] = ...) -> None: ...

class CapacityAllowanceSpec(_message.Message):
    __slots__ = ["capacity_block_group_id", "limit"]
    CAPACITY_BLOCK_GROUP_ID_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    capacity_block_group_id: str
    limit: int
    def __init__(self, capacity_block_group_id: _Optional[str] = ..., limit: _Optional[int] = ...) -> None: ...

class CapacityAllowanceStatus(_message.Message):
    __slots__ = ["state", "usage", "usage_percentage", "usage_state", "unit", "reconciling"]
    class State(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        STATE_UNSPECIFIED: _ClassVar[CapacityAllowanceStatus.State]
        STATE_PROVISIONING: _ClassVar[CapacityAllowanceStatus.State]
        STATE_ACTIVE: _ClassVar[CapacityAllowanceStatus.State]
        STATE_CONTAINER_DELETED: _ClassVar[CapacityAllowanceStatus.State]
    STATE_UNSPECIFIED: CapacityAllowanceStatus.State
    STATE_PROVISIONING: CapacityAllowanceStatus.State
    STATE_ACTIVE: CapacityAllowanceStatus.State
    STATE_CONTAINER_DELETED: CapacityAllowanceStatus.State
    class UsageState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        USAGE_STATE_UNSPECIFIED: _ClassVar[CapacityAllowanceStatus.UsageState]
        USAGE_STATE_USED: _ClassVar[CapacityAllowanceStatus.UsageState]
        USAGE_STATE_NOT_USED: _ClassVar[CapacityAllowanceStatus.UsageState]
        USAGE_STATE_UNKNOWN: _ClassVar[CapacityAllowanceStatus.UsageState]
    USAGE_STATE_UNSPECIFIED: CapacityAllowanceStatus.UsageState
    USAGE_STATE_USED: CapacityAllowanceStatus.UsageState
    USAGE_STATE_NOT_USED: CapacityAllowanceStatus.UsageState
    USAGE_STATE_UNKNOWN: CapacityAllowanceStatus.UsageState
    STATE_FIELD_NUMBER: _ClassVar[int]
    USAGE_FIELD_NUMBER: _ClassVar[int]
    USAGE_PERCENTAGE_FIELD_NUMBER: _ClassVar[int]
    USAGE_STATE_FIELD_NUMBER: _ClassVar[int]
    UNIT_FIELD_NUMBER: _ClassVar[int]
    RECONCILING_FIELD_NUMBER: _ClassVar[int]
    state: CapacityAllowanceStatus.State
    usage: int
    usage_percentage: str
    usage_state: CapacityAllowanceStatus.UsageState
    unit: str
    reconciling: bool
    def __init__(self, state: _Optional[_Union[CapacityAllowanceStatus.State, str]] = ..., usage: _Optional[int] = ..., usage_percentage: _Optional[str] = ..., usage_state: _Optional[_Union[CapacityAllowanceStatus.UsageState, str]] = ..., unit: _Optional[str] = ..., reconciling: bool = ...) -> None: ...
