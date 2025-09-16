from google.protobuf import timestamp_pb2 as _timestamp_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.mysterybox.v1 import secret_version_pb2 as _secret_version_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Secret(_message.Message):
    __slots__ = ["metadata", "spec", "status"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: SecretSpec
    status: SecretStatus
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[SecretSpec, _Mapping]] = ..., status: _Optional[_Union[SecretStatus, _Mapping]] = ...) -> None: ...

class SecretSpec(_message.Message):
    __slots__ = ["description", "primary_version_id", "secret_version"]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    PRIMARY_VERSION_ID_FIELD_NUMBER: _ClassVar[int]
    SECRET_VERSION_FIELD_NUMBER: _ClassVar[int]
    description: str
    primary_version_id: str
    secret_version: _secret_version_pb2.SecretVersionSpec
    def __init__(self, description: _Optional[str] = ..., primary_version_id: _Optional[str] = ..., secret_version: _Optional[_Union[_secret_version_pb2.SecretVersionSpec, _Mapping]] = ...) -> None: ...

class SecretStatus(_message.Message):
    __slots__ = ["state", "deleted_at", "purge_at", "effective_kms_key_id"]
    class State(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        STATE_UNSPECIFIED: _ClassVar[SecretStatus.State]
        ACTIVE: _ClassVar[SecretStatus.State]
        SCHEDULED_FOR_DELETION: _ClassVar[SecretStatus.State]
    STATE_UNSPECIFIED: SecretStatus.State
    ACTIVE: SecretStatus.State
    SCHEDULED_FOR_DELETION: SecretStatus.State
    STATE_FIELD_NUMBER: _ClassVar[int]
    DELETED_AT_FIELD_NUMBER: _ClassVar[int]
    PURGE_AT_FIELD_NUMBER: _ClassVar[int]
    EFFECTIVE_KMS_KEY_ID_FIELD_NUMBER: _ClassVar[int]
    state: SecretStatus.State
    deleted_at: _timestamp_pb2.Timestamp
    purge_at: _timestamp_pb2.Timestamp
    effective_kms_key_id: str
    def __init__(self, state: _Optional[_Union[SecretStatus.State, str]] = ..., deleted_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., purge_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., effective_kms_key_id: _Optional[str] = ...) -> None: ...
