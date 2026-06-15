from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from nebius.api.nebius.kms.v1 import key_state_pb2 as _key_state_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class AsymmetricAlgorithm(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = []
    ASYMMETRIC_ALGORITHM_UNSPECIFIED: _ClassVar[AsymmetricAlgorithm]
    ECDSA_NIST_P256_SHA_256: _ClassVar[AsymmetricAlgorithm]
    ECDSA_NIST_P384_SHA_384: _ClassVar[AsymmetricAlgorithm]
    RSA_4096_ENC_OAEP_SHA_256: _ClassVar[AsymmetricAlgorithm]
ASYMMETRIC_ALGORITHM_UNSPECIFIED: AsymmetricAlgorithm
ECDSA_NIST_P256_SHA_256: AsymmetricAlgorithm
ECDSA_NIST_P384_SHA_384: AsymmetricAlgorithm
RSA_4096_ENC_OAEP_SHA_256: AsymmetricAlgorithm

class AsymmetricKey(_message.Message):
    __slots__ = ["metadata", "spec", "status"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: AsymmetricKeySpec
    status: AsymmetricKeyStatus
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[AsymmetricKeySpec, _Mapping]] = ..., status: _Optional[_Union[AsymmetricKeyStatus, _Mapping]] = ...) -> None: ...

class AsymmetricKeySpec(_message.Message):
    __slots__ = ["description", "algorithm"]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    ALGORITHM_FIELD_NUMBER: _ClassVar[int]
    description: str
    algorithm: AsymmetricAlgorithm
    def __init__(self, description: _Optional[str] = ..., algorithm: _Optional[_Union[AsymmetricAlgorithm, str]] = ...) -> None: ...

class AsymmetricKeyStatus(_message.Message):
    __slots__ = ["state", "deleted_at", "purge_at"]
    STATE_FIELD_NUMBER: _ClassVar[int]
    DELETED_AT_FIELD_NUMBER: _ClassVar[int]
    PURGE_AT_FIELD_NUMBER: _ClassVar[int]
    state: _key_state_pb2.KeyState
    deleted_at: _timestamp_pb2.Timestamp
    purge_at: _timestamp_pb2.Timestamp
    def __init__(self, state: _Optional[_Union[_key_state_pb2.KeyState, str]] = ..., deleted_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., purge_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...
