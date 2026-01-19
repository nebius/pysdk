from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.iam.v1 import service_account_pb2 as _service_account_pb2
from nebius.api.nebius.iam.v1 import tenant_user_account_pb2 as _tenant_user_account_pb2
from nebius.api.nebius.iam.v1 import user_account_pb2 as _user_account_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class GetProfileRequest(_message.Message):
    __slots__ = []
    def __init__(self) -> None: ...

class GetProfileResponse(_message.Message):
    __slots__ = ["user_profile", "service_account_profile", "anonymous_profile"]
    USER_PROFILE_FIELD_NUMBER: _ClassVar[int]
    SERVICE_ACCOUNT_PROFILE_FIELD_NUMBER: _ClassVar[int]
    ANONYMOUS_PROFILE_FIELD_NUMBER: _ClassVar[int]
    user_profile: UserProfile
    service_account_profile: ServiceAccountProfile
    anonymous_profile: AnonymousAccount
    def __init__(self, user_profile: _Optional[_Union[UserProfile, _Mapping]] = ..., service_account_profile: _Optional[_Union[ServiceAccountProfile, _Mapping]] = ..., anonymous_profile: _Optional[_Union[AnonymousAccount, _Mapping]] = ...) -> None: ...

class UserProfile(_message.Message):
    __slots__ = ["id", "federation_info", "attributes", "retrieving_error", "tenants"]
    ID_FIELD_NUMBER: _ClassVar[int]
    FEDERATION_INFO_FIELD_NUMBER: _ClassVar[int]
    ATTRIBUTES_FIELD_NUMBER: _ClassVar[int]
    RETRIEVING_ERROR_FIELD_NUMBER: _ClassVar[int]
    TENANTS_FIELD_NUMBER: _ClassVar[int]
    id: str
    federation_info: _user_account_pb2.UserAccountExternalId
    attributes: _tenant_user_account_pb2.UserAttributes
    retrieving_error: _tenant_user_account_pb2.Error
    tenants: _containers.RepeatedCompositeFieldContainer[UserTenantInfo]
    def __init__(self, id: _Optional[str] = ..., federation_info: _Optional[_Union[_user_account_pb2.UserAccountExternalId, _Mapping]] = ..., attributes: _Optional[_Union[_tenant_user_account_pb2.UserAttributes, _Mapping]] = ..., retrieving_error: _Optional[_Union[_tenant_user_account_pb2.Error, _Mapping]] = ..., tenants: _Optional[_Iterable[_Union[UserTenantInfo, _Mapping]]] = ...) -> None: ...

class UserTenantInfo(_message.Message):
    __slots__ = ["tenant_id", "tenant_user_account_id"]
    TENANT_ID_FIELD_NUMBER: _ClassVar[int]
    TENANT_USER_ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    tenant_id: str
    tenant_user_account_id: str
    def __init__(self, tenant_id: _Optional[str] = ..., tenant_user_account_id: _Optional[str] = ...) -> None: ...

class ServiceAccountProfile(_message.Message):
    __slots__ = ["info"]
    INFO_FIELD_NUMBER: _ClassVar[int]
    info: _service_account_pb2.ServiceAccount
    def __init__(self, info: _Optional[_Union[_service_account_pb2.ServiceAccount, _Mapping]] = ...) -> None: ...

class AnonymousAccount(_message.Message):
    __slots__ = []
    def __init__(self) -> None: ...
