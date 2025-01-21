from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class UserAccountExternalId(_message.Message):
    __slots__ = ["federation_user_account_id", "federation_id"]
    FEDERATION_USER_ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    FEDERATION_ID_FIELD_NUMBER: _ClassVar[int]
    federation_user_account_id: str
    federation_id: str
    def __init__(self, federation_user_account_id: _Optional[str] = ..., federation_id: _Optional[str] = ...) -> None: ...
