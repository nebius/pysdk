from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Invitation(_message.Message):
    __slots__ = ["metadata", "spec", "status"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: InvitationSpec
    status: InvitationStatus
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[InvitationSpec, _Mapping]] = ..., status: _Optional[_Union[InvitationStatus, _Mapping]] = ...) -> None: ...

class InvitationSpec(_message.Message):
    __slots__ = ["description", "email"]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    EMAIL_FIELD_NUMBER: _ClassVar[int]
    description: str
    email: str
    def __init__(self, description: _Optional[str] = ..., email: _Optional[str] = ...) -> None: ...

class InvitationStatus(_message.Message):
    __slots__ = ["tenant_user_account_id", "expires_at", "state"]
    class State(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        UNSPECIFIED: _ClassVar[InvitationStatus.State]
        CREATING: _ClassVar[InvitationStatus.State]
        CREATED: _ClassVar[InvitationStatus.State]
        PENDING: _ClassVar[InvitationStatus.State]
        EXPIRED: _ClassVar[InvitationStatus.State]
        ACCEPTED: _ClassVar[InvitationStatus.State]
    UNSPECIFIED: InvitationStatus.State
    CREATING: InvitationStatus.State
    CREATED: InvitationStatus.State
    PENDING: InvitationStatus.State
    EXPIRED: InvitationStatus.State
    ACCEPTED: InvitationStatus.State
    TENANT_USER_ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    EXPIRES_AT_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    tenant_user_account_id: str
    expires_at: _timestamp_pb2.Timestamp
    state: InvitationStatus.State
    def __init__(self, tenant_user_account_id: _Optional[str] = ..., expires_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., state: _Optional[_Union[InvitationStatus.State, str]] = ...) -> None: ...
