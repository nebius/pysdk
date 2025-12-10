from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Tenant(_message.Message):
    __slots__ = ["metadata", "spec", "status"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: TenantSpec
    status: TenantStatus
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[TenantSpec, _Mapping]] = ..., status: _Optional[_Union[TenantStatus, _Mapping]] = ...) -> None: ...

class TenantSpec(_message.Message):
    __slots__ = []
    def __init__(self) -> None: ...

class TenantStatus(_message.Message):
    __slots__ = ["tenant_state"]
    class TenantState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        STATE_UNSPECIFIED: _ClassVar[TenantStatus.TenantState]
        CREATING: _ClassVar[TenantStatus.TenantState]
        ACTIVE: _ClassVar[TenantStatus.TenantState]
        CREATED: _ClassVar[TenantStatus.TenantState]
        ACTIVATING: _ClassVar[TenantStatus.TenantState]
        PARKING: _ClassVar[TenantStatus.TenantState]
        PARKED: _ClassVar[TenantStatus.TenantState]
    STATE_UNSPECIFIED: TenantStatus.TenantState
    CREATING: TenantStatus.TenantState
    ACTIVE: TenantStatus.TenantState
    CREATED: TenantStatus.TenantState
    ACTIVATING: TenantStatus.TenantState
    PARKING: TenantStatus.TenantState
    PARKED: TenantStatus.TenantState
    TENANT_STATE_FIELD_NUMBER: _ClassVar[int]
    tenant_state: TenantStatus.TenantState
    def __init__(self, tenant_state: _Optional[_Union[TenantStatus.TenantState, str]] = ...) -> None: ...
