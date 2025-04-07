from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class Subject(_message.Message):
    __slots__ = ["service_account_id", "tenant_user_id", "name"]
    SERVICE_ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    TENANT_USER_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    service_account_id: str
    tenant_user_id: str
    name: str
    def __init__(self, service_account_id: _Optional[str] = ..., tenant_user_id: _Optional[str] = ..., name: _Optional[str] = ...) -> None: ...
