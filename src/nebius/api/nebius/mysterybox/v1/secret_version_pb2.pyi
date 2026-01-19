from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from nebius.api.nebius.mysterybox.v1 import payload_pb2 as _payload_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class SecretVersion(_message.Message):
    __slots__ = ["metadata", "spec", "status"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: SecretVersionSpec
    status: SecretVersionStatus
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[SecretVersionSpec, _Mapping]] = ..., status: _Optional[_Union[SecretVersionStatus, _Mapping]] = ...) -> None: ...

class SecretVersionSpec(_message.Message):
    __slots__ = ["description", "payload", "set_primary"]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    PAYLOAD_FIELD_NUMBER: _ClassVar[int]
    SET_PRIMARY_FIELD_NUMBER: _ClassVar[int]
    description: str
    payload: _containers.RepeatedCompositeFieldContainer[_payload_pb2.Payload]
    set_primary: bool
    def __init__(self, description: _Optional[str] = ..., payload: _Optional[_Iterable[_Union[_payload_pb2.Payload, _Mapping]]] = ..., set_primary: bool = ...) -> None: ...

class SecretVersionStatus(_message.Message):
    __slots__ = ["state", "deleted_at", "purge_at"]
    class State(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        STATE_UNSPECIFIED: _ClassVar[SecretVersionStatus.State]
        ACTIVE: _ClassVar[SecretVersionStatus.State]
        SCHEDULED_FOR_DELETION: _ClassVar[SecretVersionStatus.State]
    STATE_UNSPECIFIED: SecretVersionStatus.State
    ACTIVE: SecretVersionStatus.State
    SCHEDULED_FOR_DELETION: SecretVersionStatus.State
    STATE_FIELD_NUMBER: _ClassVar[int]
    DELETED_AT_FIELD_NUMBER: _ClassVar[int]
    PURGE_AT_FIELD_NUMBER: _ClassVar[int]
    state: SecretVersionStatus.State
    deleted_at: _timestamp_pb2.Timestamp
    purge_at: _timestamp_pb2.Timestamp
    def __init__(self, state: _Optional[_Union[SecretVersionStatus.State, str]] = ..., deleted_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., purge_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...
