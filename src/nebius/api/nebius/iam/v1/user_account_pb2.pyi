from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class UserAccountExternalId(_message.Message):
    __slots__ = ["federation_user_account_id", "federation_id"]
    FEDERATION_USER_ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    FEDERATION_ID_FIELD_NUMBER: _ClassVar[int]
    federation_user_account_id: str
    federation_id: str
    def __init__(self, federation_user_account_id: _Optional[str] = ..., federation_id: _Optional[str] = ...) -> None: ...

class UserAccountStatus(_message.Message):
    __slots__ = ["state"]
    class State(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        STATE_UNSPECIFIED: _ClassVar[UserAccountStatus.State]
        ACTIVE: _ClassVar[UserAccountStatus.State]
        INACTIVE: _ClassVar[UserAccountStatus.State]
        DELETING: _ClassVar[UserAccountStatus.State]
    STATE_UNSPECIFIED: UserAccountStatus.State
    ACTIVE: UserAccountStatus.State
    INACTIVE: UserAccountStatus.State
    DELETING: UserAccountStatus.State
    STATE_FIELD_NUMBER: _ClassVar[int]
    state: UserAccountStatus.State
    def __init__(self, state: _Optional[_Union[UserAccountStatus.State, str]] = ...) -> None: ...
