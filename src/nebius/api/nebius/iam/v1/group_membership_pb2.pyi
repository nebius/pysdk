from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from nebius.api.nebius.iam.v1 import service_account_pb2 as _service_account_pb2
from nebius.api.nebius.iam.v1 import tenant_user_account_pb2 as _tenant_user_account_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class GroupMembership(_message.Message):
    __slots__ = ["metadata", "spec", "status", "revoke_at"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    REVOKE_AT_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: GroupMembershipSpec
    status: GroupMembershipStatus
    revoke_at: _timestamp_pb2.Timestamp
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[GroupMembershipSpec, _Mapping]] = ..., status: _Optional[_Union[GroupMembershipStatus, _Mapping]] = ..., revoke_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class GroupMembershipSpec(_message.Message):
    __slots__ = ["member_id"]
    MEMBER_ID_FIELD_NUMBER: _ClassVar[int]
    member_id: str
    def __init__(self, member_id: _Optional[str] = ...) -> None: ...

class GroupMembershipStatus(_message.Message):
    __slots__ = ["tenant_user_account_status", "service_account_status"]
    TENANT_USER_ACCOUNT_STATUS_FIELD_NUMBER: _ClassVar[int]
    SERVICE_ACCOUNT_STATUS_FIELD_NUMBER: _ClassVar[int]
    tenant_user_account_status: _tenant_user_account_pb2.TenantUserAccountStatus
    service_account_status: _service_account_pb2.ServiceAccountStatus
    def __init__(self, tenant_user_account_status: _Optional[_Union[_tenant_user_account_pb2.TenantUserAccountStatus, _Mapping]] = ..., service_account_status: _Optional[_Union[_service_account_pb2.ServiceAccountStatus, _Mapping]] = ...) -> None: ...

class GroupMemberKind(_message.Message):
    __slots__ = ["kind"]
    class Kind(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        KIND_UNSPECIFIED: _ClassVar[GroupMemberKind.Kind]
        ORDINARY_TENANT_USER_ACCOUNT: _ClassVar[GroupMemberKind.Kind]
        INVITED_TENANT_USER_ACCOUNT: _ClassVar[GroupMemberKind.Kind]
        SERVICE_ACCOUNT: _ClassVar[GroupMemberKind.Kind]
    KIND_UNSPECIFIED: GroupMemberKind.Kind
    ORDINARY_TENANT_USER_ACCOUNT: GroupMemberKind.Kind
    INVITED_TENANT_USER_ACCOUNT: GroupMemberKind.Kind
    SERVICE_ACCOUNT: GroupMemberKind.Kind
    KIND_FIELD_NUMBER: _ClassVar[int]
    kind: GroupMemberKind.Kind
    def __init__(self, kind: _Optional[_Union[GroupMemberKind.Kind, str]] = ...) -> None: ...

class GroupMembershipWithAttributes(_message.Message):
    __slots__ = ["group_membership", "group_member_kind", "user_attributes", "service_account_attributes", "error"]
    GROUP_MEMBERSHIP_FIELD_NUMBER: _ClassVar[int]
    GROUP_MEMBER_KIND_FIELD_NUMBER: _ClassVar[int]
    USER_ATTRIBUTES_FIELD_NUMBER: _ClassVar[int]
    SERVICE_ACCOUNT_ATTRIBUTES_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    group_membership: GroupMembership
    group_member_kind: GroupMemberKind
    user_attributes: _tenant_user_account_pb2.UserAttributes
    service_account_attributes: _service_account_pb2.ServiceAccountAttributes
    error: _tenant_user_account_pb2.Error
    def __init__(self, group_membership: _Optional[_Union[GroupMembership, _Mapping]] = ..., group_member_kind: _Optional[_Union[GroupMemberKind, _Mapping]] = ..., user_attributes: _Optional[_Union[_tenant_user_account_pb2.UserAttributes, _Mapping]] = ..., service_account_attributes: _Optional[_Union[_service_account_pb2.ServiceAccountAttributes, _Mapping]] = ..., error: _Optional[_Union[_tenant_user_account_pb2.Error, _Mapping]] = ...) -> None: ...
