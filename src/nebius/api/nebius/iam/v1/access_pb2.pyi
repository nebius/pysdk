from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Account(_message.Message):
    __slots__ = ["user_account", "service_account", "anonymous_account"]
    class UserAccount(_message.Message):
        __slots__ = ["id"]
        ID_FIELD_NUMBER: _ClassVar[int]
        id: str
        def __init__(self, id: _Optional[str] = ...) -> None: ...
    class ServiceAccount(_message.Message):
        __slots__ = ["id"]
        ID_FIELD_NUMBER: _ClassVar[int]
        id: str
        def __init__(self, id: _Optional[str] = ...) -> None: ...
    class AnonymousAccount(_message.Message):
        __slots__ = []
        def __init__(self) -> None: ...
    USER_ACCOUNT_FIELD_NUMBER: _ClassVar[int]
    SERVICE_ACCOUNT_FIELD_NUMBER: _ClassVar[int]
    ANONYMOUS_ACCOUNT_FIELD_NUMBER: _ClassVar[int]
    user_account: Account.UserAccount
    service_account: Account.ServiceAccount
    anonymous_account: Account.AnonymousAccount
    def __init__(self, user_account: _Optional[_Union[Account.UserAccount, _Mapping]] = ..., service_account: _Optional[_Union[Account.ServiceAccount, _Mapping]] = ..., anonymous_account: _Optional[_Union[Account.AnonymousAccount, _Mapping]] = ...) -> None: ...
