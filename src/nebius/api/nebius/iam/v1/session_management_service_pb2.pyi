from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class RevokeSessionRequest(_message.Message):
    __slots__ = ["service_account_id", "all_my_active", "tenant_user_account_id"]
    SERVICE_ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    ALL_MY_ACTIVE_FIELD_NUMBER: _ClassVar[int]
    TENANT_USER_ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    service_account_id: str
    all_my_active: bool
    tenant_user_account_id: str
    def __init__(self, service_account_id: _Optional[str] = ..., all_my_active: bool = ..., tenant_user_account_id: _Optional[str] = ...) -> None: ...

class RevokeSessionResponse(_message.Message):
    __slots__ = []
    def __init__(self) -> None: ...
