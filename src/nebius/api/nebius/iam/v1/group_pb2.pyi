from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Group(_message.Message):
    __slots__ = ["metadata", "spec", "status"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: GroupSpec
    status: GroupStatus
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[GroupSpec, _Mapping]] = ..., status: _Optional[_Union[GroupStatus, _Mapping]] = ...) -> None: ...

class GroupSpec(_message.Message):
    __slots__ = []
    def __init__(self) -> None: ...

class GroupStatus(_message.Message):
    __slots__ = ["state", "members_count", "service_accounts_count", "tenant_user_accounts_count"]
    class State(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        UNSPECIFIED: _ClassVar[GroupStatus.State]
        ACTIVE: _ClassVar[GroupStatus.State]
    UNSPECIFIED: GroupStatus.State
    ACTIVE: GroupStatus.State
    STATE_FIELD_NUMBER: _ClassVar[int]
    MEMBERS_COUNT_FIELD_NUMBER: _ClassVar[int]
    SERVICE_ACCOUNTS_COUNT_FIELD_NUMBER: _ClassVar[int]
    TENANT_USER_ACCOUNTS_COUNT_FIELD_NUMBER: _ClassVar[int]
    state: GroupStatus.State
    members_count: int
    service_accounts_count: int
    tenant_user_accounts_count: int
    def __init__(self, state: _Optional[_Union[GroupStatus.State, str]] = ..., members_count: _Optional[int] = ..., service_accounts_count: _Optional[int] = ..., tenant_user_accounts_count: _Optional[int] = ...) -> None: ...
