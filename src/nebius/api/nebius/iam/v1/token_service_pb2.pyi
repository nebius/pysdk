from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class ExchangeTokenRequest(_message.Message):
    __slots__ = ["grant_type", "requested_token_type", "subject_token", "subject_token_type", "scopes", "audience", "actor_token", "actor_token_type", "resource"]
    GRANT_TYPE_FIELD_NUMBER: _ClassVar[int]
    REQUESTED_TOKEN_TYPE_FIELD_NUMBER: _ClassVar[int]
    SUBJECT_TOKEN_FIELD_NUMBER: _ClassVar[int]
    SUBJECT_TOKEN_TYPE_FIELD_NUMBER: _ClassVar[int]
    SCOPES_FIELD_NUMBER: _ClassVar[int]
    AUDIENCE_FIELD_NUMBER: _ClassVar[int]
    ACTOR_TOKEN_FIELD_NUMBER: _ClassVar[int]
    ACTOR_TOKEN_TYPE_FIELD_NUMBER: _ClassVar[int]
    RESOURCE_FIELD_NUMBER: _ClassVar[int]
    grant_type: str
    requested_token_type: str
    subject_token: str
    subject_token_type: str
    scopes: _containers.RepeatedScalarFieldContainer[str]
    audience: str
    actor_token: str
    actor_token_type: str
    resource: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, grant_type: _Optional[str] = ..., requested_token_type: _Optional[str] = ..., subject_token: _Optional[str] = ..., subject_token_type: _Optional[str] = ..., scopes: _Optional[_Iterable[str]] = ..., audience: _Optional[str] = ..., actor_token: _Optional[str] = ..., actor_token_type: _Optional[str] = ..., resource: _Optional[_Iterable[str]] = ...) -> None: ...

class CreateTokenResponse(_message.Message):
    __slots__ = ["access_token", "issued_token_type", "token_type", "expires_in", "scopes"]
    ACCESS_TOKEN_FIELD_NUMBER: _ClassVar[int]
    ISSUED_TOKEN_TYPE_FIELD_NUMBER: _ClassVar[int]
    TOKEN_TYPE_FIELD_NUMBER: _ClassVar[int]
    EXPIRES_IN_FIELD_NUMBER: _ClassVar[int]
    SCOPES_FIELD_NUMBER: _ClassVar[int]
    access_token: str
    issued_token_type: str
    token_type: str
    expires_in: int
    scopes: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, access_token: _Optional[str] = ..., issued_token_type: _Optional[str] = ..., token_type: _Optional[str] = ..., expires_in: _Optional[int] = ..., scopes: _Optional[_Iterable[str]] = ...) -> None: ...
