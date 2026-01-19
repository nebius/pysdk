from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from nebius.api.nebius.iam.v1 import user_account_pb2 as _user_account_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class TenantUserAccount(_message.Message):
    __slots__ = ["metadata", "spec", "status"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: TenantUserAccountSpec
    status: TenantUserAccountStatus
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[TenantUserAccountSpec, _Mapping]] = ..., status: _Optional[_Union[TenantUserAccountStatus, _Mapping]] = ...) -> None: ...

class TenantUserAccountWithAttributes(_message.Message):
    __slots__ = ["tenant_user_account", "attributes", "error"]
    TENANT_USER_ACCOUNT_FIELD_NUMBER: _ClassVar[int]
    ATTRIBUTES_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    tenant_user_account: TenantUserAccount
    attributes: UserAttributes
    error: Error
    def __init__(self, tenant_user_account: _Optional[_Union[TenantUserAccount, _Mapping]] = ..., attributes: _Optional[_Union[UserAttributes, _Mapping]] = ..., error: _Optional[_Union[Error, _Mapping]] = ...) -> None: ...

class UserAttributes(_message.Message):
    __slots__ = ["sub", "name", "given_name", "family_name", "preferred_username", "picture", "email", "email_verified", "zoneinfo", "locale", "phone_number", "phone_number_verified"]
    SUB_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    GIVEN_NAME_FIELD_NUMBER: _ClassVar[int]
    FAMILY_NAME_FIELD_NUMBER: _ClassVar[int]
    PREFERRED_USERNAME_FIELD_NUMBER: _ClassVar[int]
    PICTURE_FIELD_NUMBER: _ClassVar[int]
    EMAIL_FIELD_NUMBER: _ClassVar[int]
    EMAIL_VERIFIED_FIELD_NUMBER: _ClassVar[int]
    ZONEINFO_FIELD_NUMBER: _ClassVar[int]
    LOCALE_FIELD_NUMBER: _ClassVar[int]
    PHONE_NUMBER_FIELD_NUMBER: _ClassVar[int]
    PHONE_NUMBER_VERIFIED_FIELD_NUMBER: _ClassVar[int]
    sub: str
    name: str
    given_name: str
    family_name: str
    preferred_username: str
    picture: str
    email: str
    email_verified: bool
    zoneinfo: str
    locale: str
    phone_number: str
    phone_number_verified: bool
    def __init__(self, sub: _Optional[str] = ..., name: _Optional[str] = ..., given_name: _Optional[str] = ..., family_name: _Optional[str] = ..., preferred_username: _Optional[str] = ..., picture: _Optional[str] = ..., email: _Optional[str] = ..., email_verified: bool = ..., zoneinfo: _Optional[str] = ..., locale: _Optional[str] = ..., phone_number: _Optional[str] = ..., phone_number_verified: bool = ...) -> None: ...

class Error(_message.Message):
    __slots__ = ["message"]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    message: str
    def __init__(self, message: _Optional[str] = ...) -> None: ...

class TenantUserAccountSpec(_message.Message):
    __slots__ = ["visible_attributes"]
    class VisibleAttributes(_message.Message):
        __slots__ = ["attribute"]
        ATTRIBUTE_FIELD_NUMBER: _ClassVar[int]
        attribute: _containers.RepeatedScalarFieldContainer[str]
        def __init__(self, attribute: _Optional[_Iterable[str]] = ...) -> None: ...
    VISIBLE_ATTRIBUTES_FIELD_NUMBER: _ClassVar[int]
    visible_attributes: TenantUserAccountSpec.VisibleAttributes
    def __init__(self, visible_attributes: _Optional[_Union[TenantUserAccountSpec.VisibleAttributes, _Mapping]] = ...) -> None: ...

class TenantUserAccountStatus(_message.Message):
    __slots__ = ["state", "invitation_id", "federation_id", "user_account_state"]
    class State(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        STATE_UNSPECIFIED: _ClassVar[TenantUserAccountStatus.State]
        ACTIVE: _ClassVar[TenantUserAccountStatus.State]
        INACTIVE: _ClassVar[TenantUserAccountStatus.State]
        BLOCKED: _ClassVar[TenantUserAccountStatus.State]
    STATE_UNSPECIFIED: TenantUserAccountStatus.State
    ACTIVE: TenantUserAccountStatus.State
    INACTIVE: TenantUserAccountStatus.State
    BLOCKED: TenantUserAccountStatus.State
    STATE_FIELD_NUMBER: _ClassVar[int]
    INVITATION_ID_FIELD_NUMBER: _ClassVar[int]
    FEDERATION_ID_FIELD_NUMBER: _ClassVar[int]
    USER_ACCOUNT_STATE_FIELD_NUMBER: _ClassVar[int]
    state: TenantUserAccountStatus.State
    invitation_id: str
    federation_id: str
    user_account_state: _user_account_pb2.UserAccountStatus.State
    def __init__(self, state: _Optional[_Union[TenantUserAccountStatus.State, str]] = ..., invitation_id: _Optional[str] = ..., federation_id: _Optional[str] = ..., user_account_state: _Optional[_Union[_user_account_pb2.UserAccountStatus.State, str]] = ...) -> None: ...
