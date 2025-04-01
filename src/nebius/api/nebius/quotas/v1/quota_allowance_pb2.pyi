from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class QuotaAllowanceSpec(_message.Message):
    __slots__ = ["limit", "region"]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    REGION_FIELD_NUMBER: _ClassVar[int]
    limit: int
    region: str
    def __init__(self, limit: _Optional[int] = ..., region: _Optional[str] = ...) -> None: ...

class QuotaAllowanceStatus(_message.Message):
    __slots__ = ["state", "usage", "service", "description", "service_description", "unit", "usage_percentage", "usage_state"]
    class State(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        STATE_UNSPECIFIED: _ClassVar[QuotaAllowanceStatus.State]
        STATE_PROVISIONING: _ClassVar[QuotaAllowanceStatus.State]
        STATE_ACTIVE: _ClassVar[QuotaAllowanceStatus.State]
        STATE_DELETED: _ClassVar[QuotaAllowanceStatus.State]
    STATE_UNSPECIFIED: QuotaAllowanceStatus.State
    STATE_PROVISIONING: QuotaAllowanceStatus.State
    STATE_ACTIVE: QuotaAllowanceStatus.State
    STATE_DELETED: QuotaAllowanceStatus.State
    class UsageState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        USAGE_STATE_UNSPECIFIED: _ClassVar[QuotaAllowanceStatus.UsageState]
        USAGE_STATE_USED: _ClassVar[QuotaAllowanceStatus.UsageState]
        USAGE_STATE_NOT_USED: _ClassVar[QuotaAllowanceStatus.UsageState]
        USAGE_STATE_UNKNOWN: _ClassVar[QuotaAllowanceStatus.UsageState]
    USAGE_STATE_UNSPECIFIED: QuotaAllowanceStatus.UsageState
    USAGE_STATE_USED: QuotaAllowanceStatus.UsageState
    USAGE_STATE_NOT_USED: QuotaAllowanceStatus.UsageState
    USAGE_STATE_UNKNOWN: QuotaAllowanceStatus.UsageState
    STATE_FIELD_NUMBER: _ClassVar[int]
    USAGE_FIELD_NUMBER: _ClassVar[int]
    SERVICE_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    SERVICE_DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    UNIT_FIELD_NUMBER: _ClassVar[int]
    USAGE_PERCENTAGE_FIELD_NUMBER: _ClassVar[int]
    USAGE_STATE_FIELD_NUMBER: _ClassVar[int]
    state: QuotaAllowanceStatus.State
    usage: int
    service: str
    description: str
    service_description: str
    unit: str
    usage_percentage: str
    usage_state: QuotaAllowanceStatus.UsageState
    def __init__(self, state: _Optional[_Union[QuotaAllowanceStatus.State, str]] = ..., usage: _Optional[int] = ..., service: _Optional[str] = ..., description: _Optional[str] = ..., service_description: _Optional[str] = ..., unit: _Optional[str] = ..., usage_percentage: _Optional[str] = ..., usage_state: _Optional[_Union[QuotaAllowanceStatus.UsageState, str]] = ...) -> None: ...

class QuotaAllowance(_message.Message):
    __slots__ = ["metadata", "spec", "status"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: QuotaAllowanceSpec
    status: QuotaAllowanceStatus
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[QuotaAllowanceSpec, _Mapping]] = ..., status: _Optional[_Union[QuotaAllowanceStatus, _Mapping]] = ...) -> None: ...
