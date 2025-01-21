from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.iam.v1 import access_pb2 as _access_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class AuthPublicKey(_message.Message):
    __slots__ = ["metadata", "spec", "status"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: AuthPublicKeySpec
    status: AuthPublicKeyStatus
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[AuthPublicKeySpec, _Mapping]] = ..., status: _Optional[_Union[AuthPublicKeyStatus, _Mapping]] = ...) -> None: ...

class AuthPublicKeySpec(_message.Message):
    __slots__ = ["account", "expires_at", "description", "data"]
    ACCOUNT_FIELD_NUMBER: _ClassVar[int]
    EXPIRES_AT_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    account: _access_pb2.Account
    expires_at: _timestamp_pb2.Timestamp
    description: str
    data: str
    def __init__(self, account: _Optional[_Union[_access_pb2.Account, _Mapping]] = ..., expires_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., description: _Optional[str] = ..., data: _Optional[str] = ...) -> None: ...

class AuthPublicKeyStatus(_message.Message):
    __slots__ = ["state", "fingerprint", "algorithm", "key_size"]
    class State(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        STATE_UNSPECIFIED: _ClassVar[AuthPublicKeyStatus.State]
        ACTIVE: _ClassVar[AuthPublicKeyStatus.State]
        INACTIVE: _ClassVar[AuthPublicKeyStatus.State]
        EXPIRED: _ClassVar[AuthPublicKeyStatus.State]
        DELETING: _ClassVar[AuthPublicKeyStatus.State]
        DELETED: _ClassVar[AuthPublicKeyStatus.State]
    STATE_UNSPECIFIED: AuthPublicKeyStatus.State
    ACTIVE: AuthPublicKeyStatus.State
    INACTIVE: AuthPublicKeyStatus.State
    EXPIRED: AuthPublicKeyStatus.State
    DELETING: AuthPublicKeyStatus.State
    DELETED: AuthPublicKeyStatus.State
    STATE_FIELD_NUMBER: _ClassVar[int]
    FINGERPRINT_FIELD_NUMBER: _ClassVar[int]
    ALGORITHM_FIELD_NUMBER: _ClassVar[int]
    KEY_SIZE_FIELD_NUMBER: _ClassVar[int]
    state: AuthPublicKeyStatus.State
    fingerprint: str
    algorithm: str
    key_size: int
    def __init__(self, state: _Optional[_Union[AuthPublicKeyStatus.State, str]] = ..., fingerprint: _Optional[str] = ..., algorithm: _Optional[str] = ..., key_size: _Optional[int] = ...) -> None: ...
