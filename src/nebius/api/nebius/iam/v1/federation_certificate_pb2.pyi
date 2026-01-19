from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class FederationCertificate(_message.Message):
    __slots__ = ["metadata", "spec", "status"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: FederationCertificateSpec
    status: FederationCertificateStatus
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[FederationCertificateSpec, _Mapping]] = ..., status: _Optional[_Union[FederationCertificateStatus, _Mapping]] = ...) -> None: ...

class FederationCertificateSpec(_message.Message):
    __slots__ = ["description", "data"]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    description: str
    data: str
    def __init__(self, description: _Optional[str] = ..., data: _Optional[str] = ...) -> None: ...

class FederationCertificateStatus(_message.Message):
    __slots__ = ["state", "fingerprint", "algorithm", "key_size", "not_before", "not_after"]
    class State(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        STATE_UNSPECIFIED: _ClassVar[FederationCertificateStatus.State]
        ACTIVE: _ClassVar[FederationCertificateStatus.State]
        EXPIRED: _ClassVar[FederationCertificateStatus.State]
    STATE_UNSPECIFIED: FederationCertificateStatus.State
    ACTIVE: FederationCertificateStatus.State
    EXPIRED: FederationCertificateStatus.State
    STATE_FIELD_NUMBER: _ClassVar[int]
    FINGERPRINT_FIELD_NUMBER: _ClassVar[int]
    ALGORITHM_FIELD_NUMBER: _ClassVar[int]
    KEY_SIZE_FIELD_NUMBER: _ClassVar[int]
    NOT_BEFORE_FIELD_NUMBER: _ClassVar[int]
    NOT_AFTER_FIELD_NUMBER: _ClassVar[int]
    state: FederationCertificateStatus.State
    fingerprint: str
    algorithm: str
    key_size: int
    not_before: _timestamp_pb2.Timestamp
    not_after: _timestamp_pb2.Timestamp
    def __init__(self, state: _Optional[_Union[FederationCertificateStatus.State, str]] = ..., fingerprint: _Optional[str] = ..., algorithm: _Optional[str] = ..., key_size: _Optional[int] = ..., not_before: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., not_after: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...
