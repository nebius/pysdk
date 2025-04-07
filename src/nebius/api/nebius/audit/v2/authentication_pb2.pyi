from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius.audit.v2 import access_token_pb2 as _access_token_pb2
from nebius.api.nebius.audit.v2 import authentication_type_pb2 as _authentication_type_pb2
from nebius.api.nebius.audit.v2 import federation_pb2 as _federation_pb2
from nebius.api.nebius.audit.v2 import static_key_pb2 as _static_key_pb2
from nebius.api.nebius.audit.v2 import subject_pb2 as _subject_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Authentication(_message.Message):
    __slots__ = ["authenticated", "subject", "federation", "authentication_type", "token_credential", "static_key_credential"]
    AUTHENTICATED_FIELD_NUMBER: _ClassVar[int]
    SUBJECT_FIELD_NUMBER: _ClassVar[int]
    FEDERATION_FIELD_NUMBER: _ClassVar[int]
    AUTHENTICATION_TYPE_FIELD_NUMBER: _ClassVar[int]
    TOKEN_CREDENTIAL_FIELD_NUMBER: _ClassVar[int]
    STATIC_KEY_CREDENTIAL_FIELD_NUMBER: _ClassVar[int]
    authenticated: bool
    subject: _subject_pb2.Subject
    federation: _federation_pb2.Federation
    authentication_type: _authentication_type_pb2.AuthenticationType
    token_credential: _access_token_pb2.AccessToken
    static_key_credential: _static_key_pb2.StaticKey
    def __init__(self, authenticated: bool = ..., subject: _Optional[_Union[_subject_pb2.Subject, _Mapping]] = ..., federation: _Optional[_Union[_federation_pb2.Federation, _Mapping]] = ..., authentication_type: _Optional[_Union[_authentication_type_pb2.AuthenticationType, str]] = ..., token_credential: _Optional[_Union[_access_token_pb2.AccessToken, _Mapping]] = ..., static_key_credential: _Optional[_Union[_static_key_pb2.StaticKey, _Mapping]] = ...) -> None: ...
